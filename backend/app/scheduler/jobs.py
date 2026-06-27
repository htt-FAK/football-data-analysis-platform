"""定时调度任务 — APScheduler

对应方案 4.3 调度策略：
- 实时高频（每 30s）：仅当有比赛进行中时，拉取实时比分 → Redis 缓存 → WebSocket 推送
- 日常全量（每天 06:00）：刷新赛程/积分榜/球员统计
- 日报导出（每天 02:00）：导出 Excel 报告
"""

import asyncio
import logging
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import LIVE_CRAWL_INTERVAL, EXPORT_CRON
from app.database import SessionLocal
from app.models.data_source import DataSource
from app.models.crawl_log import CrawlLog
from app.models.match import Match

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


def setup_jobs():
    """注册所有定时任务"""
    # 实时比赛数据 — 每 30 秒
    scheduler.add_job(
        crawl_live_matches,
        IntervalTrigger(seconds=LIVE_CRAWL_INTERVAL),
        id="live_crawl",
        name="实时比赛抓取",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # 日常全量采集 — 每天 06:00
    scheduler.add_job(
        daily_full_crawl,
        CronTrigger(hour=6, minute=0),
        id="daily_crawl",
        name="日常全量采集",
        replace_existing=True,
    )

    # Excel 报告导出 — 每天凌晨 02:00
    scheduler.add_job(
        export_daily_report,
        CronTrigger.from_crontab(EXPORT_CRON),
        id="daily_export",
        name="日报导出",
        replace_existing=True,
    )

    logger.info("定时任务已注册：实时抓取(%ds) / 日常采集(06:00) / 日报导出(%s)",
                LIVE_CRAWL_INTERVAL, EXPORT_CRON)


def start_scheduler():
    """启动调度器（在 FastAPI lifespan 中调用）"""
    setup_jobs()
    scheduler.start()
    logger.info("APScheduler 已启动")


def shutdown_scheduler():
    """关闭调度器"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler 已关闭")


# ── 任务实现 ──

async def crawl_live_matches():
    """抓取进行中比赛数据

    流程：
    1. 查询 MySQL 中 status='playing' 的比赛
    2. 无进行中比赛则直接返回（降频，节省 API 配额）
    3. 有比赛时，按优先级调用数据源（api_football 优先，dongqiudi 兜底）
    4. upsert 到 MySQL + 写 Redis 缓存
    5. 通过 WebSocket 推送给订阅了对应联赛的前端连接
    """
    db = SessionLocal()
    try:
        # 检查是否有进行中比赛
        playing = db.query(Match).filter(Match.status == "playing").count()
        if playing == 0:
            logger.debug("无进行中比赛，跳过实时抓取")
            return

        logger.info("发现 %d 场进行中比赛，开始实时抓取", playing)

        # 按优先级取启用的实时数据源
        sources = (
            db.query(DataSource)
            .filter(DataSource.enabled == True, DataSource.status != "error")
            .order_by(DataSource.priority.asc())
            .all()
        )
        for source in sources:
            try:
                await _crawl_source_live(source, db)
            except Exception as e:
                logger.error("数据源 %s 实时抓取失败: %s", source.source_code, e)
                _mark_source_error(source, db)
    finally:
        db.close()


async def _crawl_source_live(source: DataSource, db):
    """调用单个数据源的实时抓取并入库 + 推送

    流程：爬虫 crawl() → ingest_service.ingest_matches() → push_live_update()
    """
    from app.services.ingest_service import ingest_matches, push_live_update

    log = CrawlLog(
        source_id=source.id,
        target="live",
        start_time=time.strftime("%Y-%m-%d %H:%M:%S"),
        status="running",
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    fetched, updated_count, failed = 0, 0, 0
    start = time.time()
    try:
        data = await _dispatch_crawl(source, "live")  # 复用派发器
        fetched = len(data) if data else 0

        # 入库（标准化 + 实体解析 + upsert）
        if data:
            ingest_stats = ingest_matches(db, data, source=source.source_code)
            updated_count = ingest_stats.get("created", 0) + ingest_stats.get("updated", 0)
            failed = ingest_stats.get("failed", 0)

            # 对状态为 playing 的比赛推送实时更新
            from app.models.match import Match
            playing = db.query(Match).filter(Match.status == "playing").all()
            for m in playing:
                await push_live_update(m.id, m.league_id, {
                    "home_score": m.home_score,
                    "away_score": m.away_score,
                    "status": m.status,
                })

        log.fetched = fetched
        log.updated = updated_count
        log.failed = failed
        log.cost_ms = int((time.time() - start) * 1000)
        log.end_time = time.strftime("%Y-%m-%d %H:%M:%S")
        log.status = "success"
        source.status = "active"
        source.last_crawl_at = time.strftime("%Y-%m-%d %H:%M:%S")
        db.commit()
    except Exception as e:
        log.status = "failed"
        log.error_msg = str(e)
        log.end_time = time.strftime("%Y-%m-%d %H:%M:%S")
        log.cost_ms = int((time.time() - start) * 1000)
        db.commit()
        raise


async def daily_full_crawl():
    """日常全量采集：遍历所有启用的数据源执行采集"""
    db = SessionLocal()
    try:
        sources = (
            db.query(DataSource)
            .filter(DataSource.enabled == True)
            .order_by(DataSource.priority.asc())
            .all()
        )
        logger.info("日常全量采集开始，共 %d 个数据源", len(sources))
        for source in sources:
            try:
                await _crawl_source_full(source, db)
            except Exception as e:
                logger.error("数据源 %s 全量采集失败: %s", source.source_code, e)
                _mark_source_error(source, db)
        logger.info("日常全量采集完成")
    finally:
        db.close()


async def _crawl_source_full(source: DataSource, db):
    """单个数据源的全量采集（赛程/积分榜/球员统计等），每步入库"""
    from app.services.ingest_service import (
        ingest_matches, ingest_standings, ingest_player_stats,
    )
    # target → (爬虫target, 入库函数) 映射
    target_pipeline = [
        ("schedule", "schedule", ingest_matches),
        ("standings", "standings", ingest_standings),
        ("players", "player_stats", ingest_player_stats),
    ]
    for target, crawl_target, ingest_fn in target_pipeline:
        log = CrawlLog(
            source_id=source.id,
            target=target,
            start_time=time.strftime("%Y-%m-%d %H:%M:%S"),
            status="running",
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        start = time.time()
        try:
            data = await _dispatch_crawl(source, crawl_target)
            fetched = len(data) if data else 0
            updated_count, failed_count = 0, 0

            # 入库
            if data:
                ingest_stats = ingest_fn(db, data, source=source.source_code)
                updated_count = ingest_stats.get("created", 0) + ingest_stats.get("updated", 0)
                failed_count = ingest_stats.get("failed", 0)

            log.fetched = fetched
            log.updated = updated_count
            log.failed = failed_count
            log.cost_ms = int((time.time() - start) * 1000)
            log.end_time = time.strftime("%Y-%m-%d %H:%M:%S")
            log.status = "success"
            db.commit()
        except Exception as e:
            log.status = "failed"
            log.error_msg = str(e)
            log.end_time = time.strftime("%Y-%m-%d %H:%M:%S")
            log.cost_ms = int((time.time() - start) * 1000)
            db.commit()
            logger.warning("数据源 %s 目标 %s 采集失败: %s", source.source_code, target, e)


async def _dispatch_crawl(source: DataSource, target: str) -> list:
    """根据 source_code 派发到对应爬虫，返回原始数据列表

    Args:
        source: 数据源配置
        target: 采集目标（schedule/standings/players/live 等）
    Returns:
        list[dict]: 爬虫返回的原始数据列表，失败返回空列表
    """
    code = source.source_code
    data: list = []
    try:
        # 延迟导入，避免循环依赖
        if code == "dongqiudi":
            from app.crawlers.dongqiudi import DongqiudiCrawler
            data = DongqiudiCrawler().crawl(target=target) or []
        elif code == "fbref":
            from app.crawlers.fbref import FBrefCrawler
            data = FBrefCrawler().crawl(target=target) or []
        elif code == "understat":
            from app.crawlers.understat import UnderstatCrawler
            data = UnderstatCrawler().crawl(target=target) or []
        elif code == "api_football":
            from app.crawlers.api_football import APIFootballCrawler
            # 实时采集用 fixtures 端点
            crawl_target = "fixtures" if target == "live" else target
            data = APIFootballCrawler().crawl(target=crawl_target) or []
        elif code == "thesportsdb":
            from app.crawlers.thesportsdb import TheSportsDBCrawler
            data = TheSportsDBCrawler().crawl(target=target) or []
        elif code == "openligadb":
            from app.crawlers.openligadb import OpenLigaDBCrawler
            data = OpenLigaDBCrawler().crawl(target=target) or []
        elif code == "teamrankings":
            from app.crawlers.teamrankings import TeamRankingsCrawler
            data = TeamRankingsCrawler().crawl(target=target) or []
        elif code == "football_data":
            from app.crawlers.football_data import FootballDataCrawler
            data = FootballDataCrawler().crawl(target=target) or []
        else:
            logger.warning("未知数据源编码: %s", code)
    except Exception as e:
        logger.error("派发爬虫 %s(target=%s) 失败: %s", code, target, e)
    return data


async def export_daily_report():
    """导出每日数据报告（Excel）"""
    db = SessionLocal()
    try:
        from app.config import EXPORT_DIR
        from app.export.excel_exporter import ExcelExporter
        exporter = ExcelExporter(db=db, export_dir=EXPORT_DIR)
        path = exporter.export_all()
        logger.info("日报已导出: %s", path)
    except Exception as e:
        logger.error("日报导出失败: %s", e)
    finally:
        db.close()


def _mark_source_error(source: DataSource, db):
    """标记数据源出错，累加错误计数"""
    source.error_count = (source.error_count or 0) + 1
    if source.error_count >= 5:
        source.status = "error"
    db.commit()
