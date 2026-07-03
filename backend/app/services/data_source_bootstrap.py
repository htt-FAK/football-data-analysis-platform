"""Bootstrap built-in data sources so schedulers have runnable entries."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.crawl_log import CrawlLog
from app.models.data_source import DataSource
from app.services.source_strategy import get_default_priority, get_source_profile


DEFAULT_SOURCE_NAMES: dict[str, str] = {
    "fifa_official": "FIFA Official",
    "api_football": "API-Football",
    "dongqiudi": "Dongqiudi",
    "fbref": "FBref",
    "fotmob": "FotMob",
    "understat": "Understat",
    "statsbomb": "StatsBomb",
    "football_data": "Football-Data.co.uk",
    "thesportsdb": "TheSportsDB",
    "openligadb": "OpenLigaDB",
    "teamrankings": "TeamRankings",
}


def ensure_builtin_data_sources(db: Session) -> int:
    """Insert missing built-ins and normalize stale metadata for existing ones."""
    changed = 0
    for source_code, name in DEFAULT_SOURCE_NAMES.items():
        existing = db.query(DataSource).filter(DataSource.source_code == source_code).first()
        profile = get_source_profile(source_code)
        if existing:
            updated = False
            default_priority = get_default_priority(source_code)
            description = str(profile.get("coverage_note") or "")
            has_logs = db.query(CrawlLog.id).filter(CrawlLog.source_id == existing.id).first() is not None
            if existing.name != name:
                existing.name = name
                updated = True
            if existing.type != "crawler":
                existing.type = "crawler"
                updated = True
            if existing.priority != default_priority:
                existing.priority = default_priority
                updated = True
            if (existing.description or "") != description:
                existing.description = description
                updated = True
            if not has_logs and existing.status == "warning":
                existing.status = "idle"
                existing.error_count = 0
                existing.last_crawl_at = None
                updated = True
            if updated:
                changed += 1
            continue
        db.add(
            DataSource(
                source_code=source_code,
                name=name,
                type="crawler",
                priority=get_default_priority(source_code),
                enabled=True,
                status="idle",
                description=str(profile.get("coverage_note") or ""),
            )
        )
        changed += 1
    if changed:
        db.commit()
    return changed
