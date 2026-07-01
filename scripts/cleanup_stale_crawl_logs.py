"""Mark stale running crawl logs as failed so observability reflects reality."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


STALE_HOURS = 6


def run_cleanup(session_factory=None) -> dict:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "backend"))

    from app.database import SessionLocal
    from app.models.crawl_log import CrawlLog

    session_factory = session_factory or SessionLocal
    db = session_factory()
    try:
        cutoff = datetime.now() - timedelta(hours=STALE_HOURS)
        stale_logs = (
            db.query(CrawlLog)
            .filter(
                CrawlLog.status == "running",
                CrawlLog.end_time.is_(None),
                CrawlLog.start_time.isnot(None),
                CrawlLog.start_time < cutoff,
            )
            .order_by(CrawlLog.id.asc())
            .all()
        )

        stale_before = len(stale_logs)
        updated = 0
        updated_ids: list[int] = []
        now = datetime.now()
        for log in stale_logs:
            log.status = "failed"
            log.end_time = now
            log.error_msg = (log.error_msg or "stale running log auto-closed during maintenance")[:1000]
            updated += 1
            updated_ids.append(log.id)
        if updated:
            db.commit()

        stale_after = (
            db.query(CrawlLog)
            .filter(
                CrawlLog.status == "running",
                CrawlLog.end_time.is_(None),
                CrawlLog.start_time.isnot(None),
                CrawlLog.start_time < cutoff,
            )
            .count()
        )
    finally:
        db.close()

    return {
        "stale_hours": STALE_HOURS,
        "stale_running_before": stale_before,
        "updated": updated,
        "updated_ids": updated_ids,
        "stale_running_after": stale_after,
    }


def main() -> int:
    result = run_cleanup()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
