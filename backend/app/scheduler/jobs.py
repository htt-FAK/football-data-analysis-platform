"""Scheduled background jobs for crawling and exporting."""

from __future__ import annotations

import logging
import time
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import (
    AI_PREDICTION_SCAN_SECONDS,
    EXPORT_CRON,
    LIVE_CRAWL_INTERVAL,
)
from app.database import SessionLocal
from app.models.crawl_log import CrawlLog
from app.models.data_source import DataSource
from app.models.match import Match
from app.services.data_source_bootstrap import ensure_builtin_data_sources
from app.services.source_strategy import resolve_crawl_target, sort_sources_for_task, supports_task

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()
FIFA_DEFAULT_LEAGUE_NAME = "世界杯"
FIFA_DEFAULT_SEASON_NAME = "2026"
WORLD_CUP_SCHEDULE_REFRESH_SECONDS = 900


def setup_jobs():
    """Register all scheduler jobs."""

    scheduler.add_job(
        crawl_live_matches,
        IntervalTrigger(seconds=LIVE_CRAWL_INTERVAL),
        id="live_crawl",
        name="live-match-crawl",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        daily_full_crawl,
        CronTrigger(hour=6, minute=0),
        id="daily_crawl",
        name="daily-full-crawl",
        replace_existing=True,
    )

    scheduler.add_job(
        refresh_worldcup_schedule,
        IntervalTrigger(seconds=WORLD_CUP_SCHEDULE_REFRESH_SECONDS),
        id="worldcup_schedule_refresh",
        name="worldcup-schedule-refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        export_daily_report,
        CronTrigger.from_crontab(EXPORT_CRON),
        id="daily_export",
        name="daily-export",
        replace_existing=True,
    )

    scheduler.add_job(
        scan_and_predict_matches,
        IntervalTrigger(seconds=AI_PREDICTION_SCAN_SECONDS),
        id="ai_prediction_scan",
        name="ai-prediction-scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    logger.info(
        "Scheduler jobs registered: live(%ss), worldcup schedule(%ss), daily crawl(06:00), export(%s), ai-prediction(%ss)",
        LIVE_CRAWL_INTERVAL,
        WORLD_CUP_SCHEDULE_REFRESH_SECONDS,
        EXPORT_CRON,
        AI_PREDICTION_SCAN_SECONDS,
    )


def start_scheduler():
    """Start the scheduler during FastAPI lifespan."""

    db = SessionLocal()
    try:
        created = ensure_builtin_data_sources(db)
        if created:
            logger.info("Seeded %d built-in data sources before scheduler start", created)
    finally:
        db.close()

    setup_jobs()
    scheduler.start()
    logger.info("APScheduler started")


def shutdown_scheduler():
    """Stop the scheduler."""

    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")


async def crawl_live_matches():
    """Poll live matches using task-specific source ordering."""

    db = SessionLocal()
    try:
        ensure_builtin_data_sources(db)
        sources = (
            db.query(DataSource)
            .filter(DataSource.enabled == True, DataSource.status != "error")
            .order_by(DataSource.priority.asc())
            .all()
        )
        for source in sort_sources_for_task(sources, "live_match"):
            try:
                await _crawl_source_live(source, db)
            except Exception as exc:
                logger.error("Live crawl failed for %s: %s", source.source_code, exc)
                _mark_source_error(source, db)

        # 比赛结束后尽快刷新球员统计（解决"比赛结束但进球数不更新"的问题）。
        # daily 全量刷新要等到次日 6 点，这里在实时轮询里检测刚结束的比赛并立即触发。
        try:
            await refresh_player_stats_for_finished_matches()
        except Exception as exc:  # noqa: BLE001
            logger.error("Post-match player stats refresh failed: %s", exc)
    finally:
        db.close()


# 已刷新过球员统计的比赛 source_id 集合（进程内去重，避免重复刷新）
_REFRESHED_MATCH_SOURCE_IDS: set[str] = set()
# 去重集合上限，避免无限增长
_REFRESH_DEDUP_MAX = 500


async def refresh_player_stats_for_finished_matches():
    """检测刚结束的世界杯比赛，立即刷新球员统计（进球/助攻等）。

    实时比分任务每 30s 跑一次，这里扫描赛程里 status=finished 且还没刷新过球员的比赛，
    触发一次 FIFA 球员数据全量采集（含 FDH 逐场累加覆盖），让姆巴佩这类球员的进球数
    在比赛结束后几分钟内就更新，而不必等到次日 6 点的 daily crawl。
    """
    db = SessionLocal()
    try:
        from app.crawlers.fifa_official import FIFAOfficialCrawler
        from app.services.ingest_service import ingest_player_stats
        from app.services.worldcup_player_rating_service import WorldCupPlayerRatingService

        crawler = FIFAOfficialCrawler()
        try:
            schedule = crawler.crawl(target="schedule")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Player stats refresh skipped: schedule crawl failed: %s", exc)
            return
        if not schedule:
            return

        # 找出刚结束、且尚未刷新球员的比赛（用 source_id 去重）
        newly_finished = []
        for match in schedule:
            if match.get("status") != "finished":
                continue
            source_id = str(match.get("match_id") or "")
            if not source_id or source_id in _REFRESHED_MATCH_SOURCE_IDS:
                continue
            newly_finished.append(match)

        if not newly_finished:
            return

        # 有刚结束的比赛 → 触发一次全量球员采集（_crawl_players 内部已启用 FDH 逐场累加覆盖）
        try:
            records = crawler.crawl(target="players")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Player stats refresh skipped: players crawl failed: %s", exc)
            return
        if not records:
            return

        ingest_stats = ingest_player_stats(
            db,
            records,
            source="fifa_official",
            league_name=FIFA_DEFAULT_LEAGUE_NAME,
            season_name=FIFA_DEFAULT_SEASON_NAME,
        )
        updated = ingest_stats.get("created", 0) + ingest_stats.get("updated", 0)

        # 重算球员评分（依赖最新进球数据）
        try:
            rating_result = WorldCupPlayerRatingService().refresh(
                db, season_name=FIFA_DEFAULT_SEASON_NAME
            )
            logger.info(
                "Post-match player ratings refreshed: %s",
                rating_result,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Post-match player rating refresh failed: %s", exc)

        # 标记这些比赛已刷新过球员，避免重复触发
        for match in newly_finished:
            source_id = str(match.get("match_id") or "")
            _REFRESHED_MATCH_SOURCE_IDS.add(source_id)

        # 控制去重集合大小：超过上限清掉最早的一半
        if len(_REFRESHED_MATCH_SOURCE_IDS) > _REFRESH_DEDUP_MAX:
            keep = list(_REFRESHED_MATCH_SOURCE_IDS)[-_REFRESH_DEDUP_MAX // 2:]
            _REFRESHED_MATCH_SOURCE_IDS.clear()
            _REFRESHED_MATCH_SOURCE_IDS.update(keep)

        logger.info(
            "Post-match player stats refreshed for %d finished match(es): %d player rows updated",
            len(newly_finished),
            updated,
        )
    finally:
        db.close()


async def _crawl_source_live(source: DataSource, db):
    """Run one live crawl source and broadcast updates."""

    from app.services.ingest_service import ingest_matches, push_live_update

    log = CrawlLog(
        source_id=source.id,
        target="live",
        start_time=datetime.now(),
        status="running",
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    fetched = 0
    updated_count = 0
    failed = 0
    start = time.time()
    try:
        data = await _dispatch_crawl(source, "live")
        fetched = len(data) if data else 0
        if data:
            ingest_stats = ingest_matches(
                db,
                data,
                source=source.source_code,
                **_ingest_context(source.source_code),
            )
            updated_count = ingest_stats.get("created", 0) + ingest_stats.get("updated", 0)
            failed = ingest_stats.get("failed", 0)

            source_match_ids = [str(item.get("match_id")) for item in data if item.get("match_id")]
            live_matches = (
                db.query(Match).filter(Match.source_id.in_(source_match_ids)).all()
                if source_match_ids
                else []
            )
            match_by_source_id = {str(match.source_id): match for match in live_matches if match.source_id}

            for item in data:
                match = match_by_source_id.get(str(item.get("match_id")))
                if not match or not match.league_id:
                    continue
                await push_live_update(
                    match.id,
                    match.league_id,
                    {
                        "source": source.source_code,
                        "match_id": match.id,
                        "source_match_id": match.source_id,
                        "home_score": match.home_score,
                        "away_score": match.away_score,
                        "status": match.status,
                        "match_date": match.match_date.isoformat() if match.match_date else None,
                        "stage": match.stage,
                        "group": match.group_name,
                    },
                )

        log.fetched = fetched
        log.updated = updated_count
        log.failed = failed
        log.cost_ms = int((time.time() - start) * 1000)
        log.end_time = datetime.now()
        log.status = _derive_crawl_status(fetched, updated_count, failed)
        source.status = _derive_source_status(log.status)
        source.last_crawl_at = datetime.now()
        if log.status == "success":
            source.error_count = 0
        db.commit()
    except Exception as exc:
        log.status = "failed"
        log.error_msg = str(exc)
        log.end_time = datetime.now()
        log.cost_ms = int((time.time() - start) * 1000)
        db.commit()
        raise


async def daily_full_crawl():
    """Run full daily crawl using task-specific source ordering."""

    db = SessionLocal()
    try:
        ensure_builtin_data_sources(db)
        sources = (
            db.query(DataSource)
            .filter(DataSource.enabled == True)
            .order_by(DataSource.priority.asc())
            .all()
        )

        from app.services.ingest_service import (
            ingest_matches,
            ingest_player_stats,
            ingest_standings,
            ingest_team_stats,
        )
        from app.services.worldcup_player_rating_service import WorldCupPlayerRatingService

        target_pipeline = [
            ("schedule", "schedule", ingest_matches, "match_catalog"),
            ("standings", "standings", ingest_standings, "match_catalog"),
            ("players", "player_stats", ingest_player_stats, "player_basic"),
        ]

        for target, crawl_target, ingest_fn, task in target_pipeline:
            eligible_sources = [source for source in sources if supports_task(source.source_code, task)]
            for source in sort_sources_for_task(eligible_sources, task):
                try:
                    await _crawl_source_target(source, db, target, crawl_target, ingest_fn)
                    if source.source_code == "fifa_official" and target == "players":
                        rating_result = WorldCupPlayerRatingService().refresh(
                            db,
                            season_name=FIFA_DEFAULT_SEASON_NAME,
                        )
                        logger.info(
                            "World Cup player ratings refreshed after scheduled FIFA crawl: %s",
                            rating_result,
                        )
                except Exception as exc:
                    logger.error("Daily crawl failed for %s target=%s: %s", source.source_code, target, exc)
                    _mark_source_error(source, db)

        fifa_source = next((source for source in sources if source.source_code == "fifa_official" and source.enabled), None)
        if fifa_source:
            try:
                await _crawl_source_target(
                    fifa_source,
                    db,
                    "statistics",
                    "statistics",
                    ingest_team_stats,
                )
            except Exception as exc:
                logger.error("Daily crawl failed for fifa_official target=statistics: %s", exc)
                _mark_source_error(fifa_source, db)
    finally:
        db.close()


async def refresh_worldcup_schedule():
    """Refresh FIFA World Cup schedule frequently during the tournament."""

    db = SessionLocal()
    source = None
    try:
        ensure_builtin_data_sources(db)
        source = (
            db.query(DataSource)
            .filter(DataSource.source_code == "fifa_official", DataSource.enabled == True)
            .first()
        )
        if not source:
            logger.info("Skipping world cup schedule refresh: fifa_official source not available")
            return

        from app.services.ingest_service import ingest_matches

        await _crawl_source_target(source, db, "worldcup_schedule", "schedule", ingest_matches)
    except Exception as exc:
        logger.error("World Cup schedule refresh failed: %s", exc)
        if source:
            _mark_source_error(source, db)
    finally:
        db.close()


async def _crawl_source_target(source: DataSource, db, target: str, crawl_target: str, ingest_fn):
    """Run one scheduled target for one source."""
    concrete_target = resolve_crawl_target(source.source_code, crawl_target)
    if concrete_target is None:
        logger.info(
            "Skipping source=%s target=%s because no concrete crawler target is supported",
            source.source_code,
            crawl_target,
        )
        return

    log = CrawlLog(
        source_id=source.id,
        target=target,
        start_time=datetime.now(),
        status="running",
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    start = time.time()

    try:
        data = await _dispatch_crawl(source, concrete_target)
        fetched = len(data) if data else 0
        updated_count = 0
        failed_count = 0

        if data:
            ingest_stats = ingest_fn(db, data, source=source.source_code, **_ingest_context(source.source_code))
            updated_count = ingest_stats.get("created", 0) + ingest_stats.get("updated", 0)
            failed_count = ingest_stats.get("failed", 0)

        log.fetched = fetched
        log.updated = updated_count
        log.failed = failed_count
        log.cost_ms = int((time.time() - start) * 1000)
        log.end_time = datetime.now()
        log.status = _derive_crawl_status(fetched, updated_count, failed_count)
        source.status = _derive_source_status(log.status)
        source.last_crawl_at = datetime.now()
        if log.status == "success":
            source.error_count = 0
        db.commit()
    except Exception as exc:
        log.status = "failed"
        log.error_msg = str(exc)
        log.end_time = datetime.now()
        log.cost_ms = int((time.time() - start) * 1000)
        db.commit()
        raise


async def _dispatch_crawl(source: DataSource, target: str) -> list:
    """Dispatch to the concrete crawler by source code."""

    code = source.source_code
    if code == "fifa_official":
        from app.crawlers.fifa_official import FIFAOfficialCrawler

        return FIFAOfficialCrawler().crawl(target=target) or []
    if code == "dongqiudi":
        from app.crawlers.dongqiudi import DongqiudiCrawler

        return DongqiudiCrawler().crawl(target=target) or []
    if code == "fbref":
        from app.crawlers.fbref import FBrefCrawler

        return FBrefCrawler().crawl(target=target) or []
    if code == "understat":
        from app.crawlers.understat import UnderstatCrawler

        return UnderstatCrawler().crawl(target=target) or []
    if code == "api_football":
        from app.crawlers.api_football import APIFootballCrawler

        crawl_target = "fixtures" if target == "live" else target
        return APIFootballCrawler().crawl(target=crawl_target) or []
    if code == "thesportsdb":
        from app.crawlers.thesportsdb import TheSportsDBCrawler

        return TheSportsDBCrawler().crawl(target=target) or []
    if code == "openligadb":
        from app.crawlers.openligadb import OpenLigaDBCrawler

        return OpenLigaDBCrawler().crawl(target=target) or []
    if code == "teamrankings":
        from app.crawlers.teamrankings import TeamRankingsCrawler

        return TeamRankingsCrawler().crawl(target=target) or []
    if code == "statsbomb":
        from app.crawlers.statsbomb import StatsBombCrawler

        return StatsBombCrawler().crawl(target=target) or []
    if code == "football_data":
        from app.crawlers.football_data import FootballDataCrawler

        return FootballDataCrawler().crawl(target=target) or []

    logger.warning("Unknown source code: %s", code)
    return []


async def export_daily_report():
    """Export the daily Excel report."""

    db = SessionLocal()
    try:
        from app.config import EXPORT_DIR
        from app.export.excel_exporter import ExcelExporter

        exporter = ExcelExporter(db=db, export_dir=EXPORT_DIR)
        path = exporter.export_all()
        logger.info("Daily report exported: %s", path)
    except Exception as exc:
        logger.error("Daily report export failed: %s", exc)
    finally:
        db.close()


async def scan_and_predict_matches():
    """扫描赛前触发窗口内待预测的比赛并逐场执行 AI 预测。

    每隔 AI_PREDICTION_SCAN_SECONDS（默认 900s）运行一次。对处于
    [现在 + (H-tol), 现在 + (H+tol)] 窗口内、status=scheduled、主客队齐全、
    且尚无 completed 预测记录的比赛，调用多模型编排器生成预测并落库。
    """
    from app.config import ENABLE_AI_PREDICTION
    from app.services.prediction_service import scan_and_predict_async

    if not ENABLE_AI_PREDICTION:
        return

    db = SessionLocal()
    try:
        result = await scan_and_predict_async(db)
        if result.get("scanned", 0) > 0:
            logger.info(
                "AI prediction scan: scanned=%d predicted=%d failed=%d details=%s",
                result["scanned"], result["predicted"], result["failed"], result["details"],
            )
    except Exception as exc:
        logger.error("AI prediction scan failed: %s", exc)
    finally:
        db.close()


def _mark_source_error(source: DataSource, db):
    """Increment source error counters."""

    source.error_count = (source.error_count or 0) + 1
    source.status = "error" if source.error_count >= 5 else "warning"
    db.commit()


def _ingest_context(source_code: str) -> dict:
    if source_code != "fifa_official":
        return {}
    return {
        "league_name": FIFA_DEFAULT_LEAGUE_NAME,
        "season_name": FIFA_DEFAULT_SEASON_NAME,
    }


def _derive_crawl_status(fetched: int, updated: int, failed: int) -> str:
    if failed > 0:
        return "partial"
    if fetched <= 0 and updated <= 0:
        return "partial"
    return "success"


def _derive_source_status(crawl_status: str) -> str:
    if crawl_status == "success":
        return "active"
    if crawl_status == "partial":
        return "warning"
    return "idle"
