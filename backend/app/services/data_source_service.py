"""Data source service helpers reused by monitoring APIs."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.crawl_log import CrawlLog
from app.models.data_source import DataSource
from app.services.source_strategy import get_source_profile, resolve_crawl_target, supports_task


TASK_BY_LOG_TARGET: dict[str, str] = {
    "live": "live_match",
    "schedule": "match_catalog",
    "worldcup_schedule": "match_catalog",
    "standings": "match_catalog",
    "players": "player_basic",
    "statistics": "player_basic",
    "shots": "player_advanced",
}

CRAWL_TARGET_BY_LOG_TARGET: dict[str, str] = {
    "live": "live",
    "schedule": "schedule",
    "worldcup_schedule": "schedule",
    "standings": "standings",
    "players": "player_stats",
    "statistics": "statistics",
    "shots": "shots",
}


class DataSourceService:
    """Reusable monitoring and status helpers for crawl sources."""

    @classmethod
    def _should_ignore_legacy_empty_log(cls, source: DataSource, last_log: CrawlLog | None) -> bool:
        """Treat old empty-success logs as ignorable only after an explicit source reset."""

        return bool(
            cls._is_legacy_empty_success(last_log)
            and not source.error_count
            and source.status == "idle"
            and source.last_crawl_at is None
        )

    @classmethod
    def _is_empty_success_log(cls, log: CrawlLog | None) -> bool:
        return bool(
            log
            and log.status == "success"
            and (log.fetched or 0) == 0
            and (log.updated or 0) == 0
            and (log.failed or 0) == 0
        )

    @classmethod
    def _should_ignore_misaligned_empty_log(cls, source: DataSource, log: CrawlLog | None) -> bool:
        """Ignore empty-success logs for targets the source should not meaningfully run.

        This keeps monitoring honest when historical schedulers recorded empty "success"
        rows for sources that were never intended to support that generic target.
        """

        if not cls._is_empty_success_log(log):
            return False

        target = (log.target or "").strip()
        if not target:
            return False

        task = TASK_BY_LOG_TARGET.get(target)
        crawl_target = CRAWL_TARGET_BY_LOG_TARGET.get(target, target)

        if resolve_crawl_target(source.source_code, crawl_target) is None:
            return True
        if task and not supports_task(source.source_code, task):
            return True
        return False

    @classmethod
    def _should_ignore_noop_empty_log(
        cls,
        source: DataSource,
        log: CrawlLog | None,
        older_logs: list[CrawlLog],
    ) -> bool:
        """Ignore suspicious no-op rows that completed instantly with no work done.

        These rows commonly come from older schedulers or broken runtime contexts where
        the crawl layer returned immediately without doing meaningful network or ingest
        work. We keep genuine partial/failed runs visible, but skip empty-success rows
        that also look like a no-op and have better historical evidence behind them.
        """

        if not cls._is_empty_success_log(log):
            return False
        if cls._should_ignore_misaligned_empty_log(source, log):
            return True
        meaningful_older_log_exists = any(
            (older.status in {"partial", "failed"})
            or (older.fetched or 0) > 0
            or (older.updated or 0) > 0
            or (older.failed or 0) > 0
            for older in older_logs
        )

        return bool(
            source.status == "warning"
            and not source.error_count
            and source.last_crawl_at
            and log.end_time
            and source.last_crawl_at <= log.end_time
            and meaningful_older_log_exists
        )

    def _select_health_log(self, db: Session, source: DataSource) -> CrawlLog | None:
        logs = (
            db.query(CrawlLog)
            .filter(CrawlLog.source_id == source.id)
            .order_by(CrawlLog.id.desc())
            .limit(20)
            .all()
        )
        for index, log in enumerate(logs):
            if self._should_ignore_misaligned_empty_log(source, log):
                continue
            if self._should_ignore_noop_empty_log(source, log, logs[index + 1:]):
                continue
            return log
        return None

    def get_health_status(self, db: Session) -> list[dict]:
        sources = db.query(DataSource).order_by(DataSource.priority.asc()).all()
        result: list[dict] = []
        for source in sources:
            last_log = self._select_health_log(db, source)
            effective_status, effective_last_crawl_at = self._derive_effective_source_state(source, last_log)
            result.append(
                {
                    "id": source.id,
                    "source_code": source.source_code,
                    "name": source.name,
                    "type": source.type,
                    "priority": source.priority,
                    "enabled": source.enabled,
                    "status": effective_status,
                    "error_count": source.error_count,
                    "last_crawl_at": effective_last_crawl_at.isoformat() if effective_last_crawl_at else None,
                    "health": self._compute_health(source, last_log, effective_status, effective_last_crawl_at),
                    "last_log": {
                        "target": last_log.target if last_log else None,
                        "fetched": last_log.fetched if last_log else 0,
                        "updated": last_log.updated if last_log else 0,
                        "failed": last_log.failed if last_log else 0,
                        "cost_ms": last_log.cost_ms if last_log else 0,
                        "status": self._display_log_status(last_log) if last_log else None,
                        "raw_status": last_log.status if last_log else None,
                    }
                    if last_log
                    else None,
                    "strategy": get_source_profile(source.source_code),
                }
            )
        return result

    def get_crawl_logs(self, db: Session, source_id: int | None = None, limit: int = 50) -> list[dict]:
        query = db.query(CrawlLog)
        if source_id:
            query = query.filter(CrawlLog.source_id == source_id)
        logs = query.order_by(CrawlLog.id.desc()).limit(limit).all()
        source_ids = {log.source_id for log in logs}
        sources_map = (
            {
                row.id: (row.source_code, row.name)
                for row in db.query(DataSource).filter(DataSource.id.in_(source_ids)).all()
            }
            if source_ids
            else {}
        )
        return [
            {
                "id": log.id,
                "source_id": log.source_id,
                "source_code": sources_map.get(log.source_id, (None, None))[0],
                "source_name": sources_map.get(log.source_id, (None, None))[1],
                "target": log.target,
                "start_time": log.start_time.isoformat() if log.start_time else None,
                "end_time": log.end_time.isoformat() if log.end_time else None,
                "fetched": log.fetched,
                "updated": log.updated,
                "failed": log.failed,
                "cost_ms": log.cost_ms,
                "status": self._display_log_status(log),
                "raw_status": log.status,
                "error_msg": log.error_msg,
            }
            for log in logs
        ]

    def update_source_status(self, db: Session, source_id: int, status: str) -> None:
        source = db.query(DataSource).filter(DataSource.id == source_id).first()
        if not source:
            return
        source.status = status
        db.commit()

    @classmethod
    def _is_legacy_empty_success(cls, log: CrawlLog | None) -> bool:
        return cls._is_empty_success_log(log)

    @staticmethod
    def _compute_health(
        source: DataSource,
        last_log: CrawlLog | None,
        effective_status: str,
        effective_last_crawl_at,
    ) -> str:
        display_status = DataSourceService._display_log_status(last_log)
        if not source.enabled:
            return "disabled"
        if source.error_count >= 5:
            return "error"
        if effective_status == "error":
            return "error"
        if DataSourceService._should_ignore_legacy_empty_log(source, last_log):
            return "idle"
        if (
            effective_status == "idle"
            and not source.error_count
            and effective_last_crawl_at is None
            and last_log
            and last_log.status == "success"
            and (last_log.fetched or 0) == 0
            and (last_log.updated or 0) == 0
            and (last_log.failed or 0) == 0
        ):
            return "idle"
        if display_status in {"failed", "partial"}:
            return "warning"
        if last_log and (last_log.fetched or 0) == 0 and (last_log.updated or 0) == 0:
            return "warning"
        if last_log and display_status == "success":
            return "healthy"
        if effective_status == "warning":
            return "warning"
        if effective_status == "idle" and not source.error_count and effective_last_crawl_at is None:
            return "idle"
        return "idle"

    @classmethod
    def _derive_effective_source_state(cls, source: DataSource, last_log: CrawlLog | None):
        effective_status = source.status
        effective_last_crawl_at = source.last_crawl_at
        display_status = cls._display_log_status(last_log)

        if (
            last_log is None
            and effective_status == "warning"
            and not source.error_count
            and effective_last_crawl_at is not None
        ):
            effective_status = "idle"
            effective_last_crawl_at = None

        if last_log and effective_last_crawl_at is None:
            effective_last_crawl_at = last_log.end_time or last_log.start_time
            if cls._should_ignore_legacy_empty_log(source, last_log):
                effective_status = "idle"
            elif display_status == "success":
                effective_status = "active"
            elif display_status in {"partial", "failed"}:
                effective_status = "warning"

        if cls._should_ignore_legacy_empty_log(source, last_log):
            effective_status = "idle"
        elif display_status == "success" and not source.error_count:
            effective_status = "active"
        elif display_status in {"partial", "failed"}:
            effective_status = "warning"

        if (
            effective_status == "warning"
            and cls._should_ignore_legacy_empty_log(source, last_log)
        ):
            effective_status = "idle"

        return effective_status, effective_last_crawl_at

    @staticmethod
    def _display_log_status(log: CrawlLog | None) -> str | None:
        if not log:
            return None
        if log.status == "success" and (log.fetched or 0) == 0 and (log.updated or 0) == 0 and (log.failed or 0) == 0:
            return "partial"
        return log.status
