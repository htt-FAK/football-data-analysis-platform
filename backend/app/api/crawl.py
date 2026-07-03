"""Manual crawl trigger endpoints."""

from __future__ import annotations

import importlib
import logging
import time
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.crawl_log import CrawlLog
from app.models.data_source import DataSource
from app.services.data_source_bootstrap import ensure_builtin_data_sources
from app.services.data_source_service import DataSourceService
from app.services.ingest_service import (
    ingest_matches,
    ingest_match_xg,
    ingest_player_stats,
    ingest_shots,
    ingest_standings,
    ingest_team_stats,
)
from app.services.source_strategy import get_default_priority, get_source_profile, resolve_crawl_target
from app.services.worldcup_player_rating_service import WorldCupPlayerRatingService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["crawl"])
data_source_service = DataSourceService()


CRAWLER_REGISTRY = {
    "fifa_official": {"module": "app.crawlers.fifa_official", "class": "FIFAOfficialCrawler", "name": "FIFA Official"},
    "api_football": {"module": "app.crawlers.api_football", "class": "APIFootballCrawler", "name": "API-Football"},
    "football_data": {"module": "app.crawlers.football_data", "class": "FootballDataCrawler", "name": "Football-Data.co.uk"},
    "thesportsdb": {"module": "app.crawlers.thesportsdb", "class": "TheSportsDBCrawler", "name": "TheSportsDB"},
    "openligadb": {"module": "app.crawlers.openligadb", "class": "OpenLigaDBCrawler", "name": "OpenLigaDB"},
    "fbref": {"module": "app.crawlers.fbref", "class": "FBrefCrawler", "name": "FBref"},
    "dongqiudi": {"module": "app.crawlers.dongqiudi", "class": "DongqiudiCrawler", "name": "Dongqiudi"},
    "understat": {"module": "app.crawlers.understat", "class": "UnderstatCrawler", "name": "Understat"},
    "statsbomb": {"module": "app.crawlers.statsbomb", "class": "StatsBombCrawler", "name": "StatsBomb"},
    "teamrankings": {"module": "app.crawlers.teamrankings", "class": "TeamRankingsCrawler", "name": "TeamRankings"},
    "fotmob": {"module": "app.crawlers.fotmob", "class": "FotmobCrawler", "name": "FotMob"},
}

TARGET_INGEST_MAP = {
    "matches": "ingest_matches",
    "schedule": "ingest_matches",
    "player_stats": "ingest_player_stats",
    "team_stats": "ingest_team_stats",
    "statistics": "ingest_team_stats",
    "standings": "ingest_standings",
    "shots": "ingest_shots",
    "match_xg": "ingest_match_xg",
}

LEAGUE_NAME_SOURCES = {"fbref", "understat", "dongqiudi", "fifa_official", "statsbomb", "fotmob"}
FIFA_DEFAULT_LEAGUE_NAME = "世界杯"
FIFA_DEFAULT_SEASON_NAME = "2026"


class CrawlTrigger(BaseModel):
    """Request payload for background crawl execution."""

    source: str = "football_data"
    target: str = "matches"
    league_code: str | None = None
    season: str | None = None
    league_name: str | None = None
    season_name: str | None = None
    league_id: int | None = None


def _instantiate_crawler(source_code: str):
    meta = CRAWLER_REGISTRY.get(source_code)
    if not meta:
        raise ValueError(f"不支持的数据源：{source_code}")
    module = importlib.import_module(meta["module"])
    cls = getattr(module, meta["class"])
    return cls()


def _validate_crawl_request(
    source: str,
    target: str,
    league_code: str | None,
    season: str | None,
    league_name: str | None,
):
    """Best-effort synchronous validation for source/target combinations that are known to be unsupported."""

    if source == "statsbomb" and target == "shots":
        if not (league_name or league_code) or not season:
            raise ValueError(
                "StatsBomb shots requires explicit league and season context; "
                "2026 World Cup shots are not available in StatsBomb open data."
            )
        crawler = _instantiate_crawler(source)
        crawler._parse_comp_season(league_name or league_code, season)
        return
    if source == "understat" and target == "shots":
        crawler = _instantiate_crawler(source)
        crawler._resolve_league_id(league_name or league_code or "")


def _execute_crawl(
    log_id: int,
    source: str,
    target: str,
    league_code: str | None,
    season: str | None,
    league_name: str | None,
    season_name: str | None,
):
    """Run one crawl task in the background and write back CrawlLog."""

    db = SessionLocal()
    log = db.query(CrawlLog).filter(CrawlLog.id == log_id).first()
    source_row = (
        db.query(DataSource)
        .filter(DataSource.source_code == source)
        .first()
    )
    start = time.time()
    try:
        league_name, season_name = _normalize_crawl_context(source, league_name, season_name)
        normalized_target = _normalize_target(target)
        concrete_target = resolve_crawl_target(source, normalized_target)
        if concrete_target is None:
            raise ValueError(f"数据源 '{source}' 不支持目标 '{normalized_target}'")
        crawler = _instantiate_crawler(source)
        raw = crawler.crawl(**_build_crawl_kwargs(source, concrete_target, league_code, season, league_name))
        ingest_func_name = TARGET_INGEST_MAP.get(normalized_target)
        updated = 0
        failed = 0

        if raw and ingest_func_name:
            common_kwargs = {"source": source, "league_name": league_name, "season_name": season_name}
            if ingest_func_name == "ingest_matches":
                stats = ingest_matches(db, raw, **common_kwargs)
            elif ingest_func_name == "ingest_player_stats":
                stats = ingest_player_stats(
                    db,
                    raw,
                    source=source,
                    season_name=season_name,
                    league_name=league_name,
                )
                if source == "fifa_official":
                    rating_result = WorldCupPlayerRatingService().refresh(
                        db,
                        season_name=season_name or FIFA_DEFAULT_SEASON_NAME,
                    )
                    logger.info("World Cup player ratings refreshed after manual FIFA crawl: %s", rating_result)
            elif ingest_func_name == "ingest_team_stats":
                stats = ingest_team_stats(db, raw, source=source, season_name=season_name, league_name=league_name)
            elif ingest_func_name == "ingest_shots":
                stats = ingest_shots(db, raw, source=source, season_name=season_name, league_name=league_name)
            elif ingest_func_name == "ingest_match_xg":
                stats = ingest_match_xg(db, raw, source=source, season_name=season_name, league_name=league_name)
            elif ingest_func_name == "ingest_standings":
                stats = ingest_standings(db, raw, source=source, league_name=league_name, season_name=season_name)
            else:
                stats = {"failed": 0}
            updated = stats.get("created", 0) + stats.get("updated", 0)
            failed = stats.get("failed", 0)

        log.fetched = len(raw)
        log.updated = updated
        log.failed = failed
        log.end_time = datetime.now()
        log.cost_ms = int((time.time() - start) * 1000)
        log.status = _derive_crawl_status(len(raw), updated, failed)
        if source_row:
            source_row.status = _derive_source_status(log.status)
            source_row.last_crawl_at = datetime.now()
            source_row.error_count = 0 if log.status == "success" else (source_row.error_count or 0)
        logger.info(
            "Crawl finished log_id=%s source=%s fetched=%d updated=%d failed=%d",
            log_id,
            source,
            log.fetched,
            updated,
            failed,
        )
    except Exception as exc:
        log.status = "failed"
        log.error_msg = str(exc)[:1000]
        log.end_time = datetime.now()
        log.cost_ms = int((time.time() - start) * 1000)
        if source_row:
            source_row.error_count = (source_row.error_count or 0) + 1
            source_row.status = "error" if source_row.error_count >= 5 else "warning"
        logger.exception("Crawl failed log_id=%s", log_id)
    finally:
        db.commit()
        db.close()


@router.post("/trigger")
def trigger_crawl(body: CrawlTrigger, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Trigger one background crawl job."""

    if body.source not in CRAWLER_REGISTRY:
        raise HTTPException(status_code=400, detail=f"不支持的数据源：{body.source}")
    normalized_target = _normalize_target(body.target)
    concrete_target = resolve_crawl_target(body.source, normalized_target)
    if concrete_target is None:
        raise HTTPException(
            status_code=400,
            detail=f"数据源 '{body.source}' 不支持目标 '{normalized_target}'",
        )
    try:
        _validate_crawl_request(
            body.source,
            normalized_target,
            body.league_code,
            body.season,
            body.league_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ensure_builtin_data_sources(db)
    source = db.query(DataSource).filter(DataSource.source_code == body.source).first()
    if not source:
        meta = CRAWLER_REGISTRY[body.source]
        strategy = get_source_profile(body.source)
        source = DataSource(
            source_code=body.source,
            name=meta["name"],
            type="crawler",
            priority=get_default_priority(body.source),
            enabled=True,
            status="idle",
            description=strategy.get("coverage_note"),
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        logger.info("Registered data source %s (id=%d)", body.source, source.id)

    if not source.enabled:
        raise HTTPException(status_code=400, detail=f"数据源已禁用：{body.source}")

    log = CrawlLog(
        source_id=source.id,
        target=normalized_target,
        start_time=datetime.now(),
        status="running",
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    background_tasks.add_task(
        _execute_crawl,
        log_id=log.id,
        source=body.source,
        target=normalized_target,
        league_code=body.league_code,
        season=body.season,
        league_name=body.league_name,
        season_name=body.season_name,
    )

    return {
        "message": "采集任务已创建",
        "log_id": log.id,
        "source": body.source,
        "target": normalized_target,
        "status": "running",
    }


def _normalize_crawl_context(
    source: str,
    league_name: str | None,
    season_name: str | None,
) -> tuple[str | None, str | None]:
    if source != "fifa_official":
        return league_name, season_name
    return league_name or FIFA_DEFAULT_LEAGUE_NAME, season_name or FIFA_DEFAULT_SEASON_NAME


def _normalize_target(target: str) -> str:
    if target == "team_stats":
        return "statistics"
    return target


def _build_crawl_kwargs(
    source: str,
    target: str,
    league_code: str | None,
    season: str | None,
    league_name: str | None,
) -> dict:
    kwargs: dict[str, object] = {"target": target}
    if season is not None:
        kwargs["season"] = season

    if source in LEAGUE_NAME_SOURCES:
        if league_name:
            kwargs["league"] = league_name
        return kwargs

    if source == "api_football":
        if league_code is not None:
            try:
                kwargs["league_id"] = int(league_code)
            except (TypeError, ValueError):
                kwargs["league_id"] = league_code
        return kwargs

    if source == "thesportsdb":
        if league_code is not None:
            kwargs["league_id"] = league_code
        return kwargs

    if league_code is not None:
        kwargs["league"] = league_code
    return kwargs


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


@router.get("/{log_id}")
def get_crawl_status(log_id: int, db: Session = Depends(get_db)):
    """Fetch one crawl task status."""

    log = db.query(CrawlLog).filter(CrawlLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="未找到采集日志")
    return {
        "log_id": log.id,
        "source_id": log.source_id,
        "target": log.target,
        "status": data_source_service._display_log_status(log),
        "raw_status": log.status,
        "fetched": log.fetched,
        "updated": log.updated,
        "failed": log.failed,
        "cost_ms": log.cost_ms,
        "error_msg": log.error_msg,
        "start_time": log.start_time,
        "end_time": log.end_time,
    }
