"""Manual backfill entrypoint for finished 2026 World Cup match events."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill finished 2026 World Cup match events")
    parser.add_argument("--season", default="2026", help="Season name to backfill, defaults to 2026")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of finished matches to scan")
    parser.add_argument(
        "--match-id",
        dest="match_ids",
        type=int,
        action="append",
        default=None,
        help="Backfill a specific match id. May be provided multiple times.",
    )
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Process matches even if real events already exist",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "backend"))

    from app.database import SessionLocal
    from app.services.worldcup_match_event_service import WorldCupMatchEventBackfillService

    db = SessionLocal()
    try:
        service = WorldCupMatchEventBackfillService()
        result = service.backfill_finished_match_events(
            db,
            season_name=args.season,
            limit=args.limit,
            match_ids=args.match_ids,
            skip_existing=not args.include_existing,
        )
    finally:
        db.close()

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
