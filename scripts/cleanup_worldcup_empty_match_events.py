"""Delete historical empty World Cup match_events rows for the 2026 dataset."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import and_


WORLD_CUP_LEAGUE_ID = 3
WORLD_CUP_SEASON_ID = 4


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "backend"))

    from app.database import SessionLocal
    from app.models.match import Match
    from app.models.match_event import MatchEvent

    db = SessionLocal()
    try:
        empty_filter = and_(
            MatchEvent.minute.is_(None),
            MatchEvent.event_type.is_(None),
            MatchEvent.team_id.is_(None),
            MatchEvent.player_id.is_(None),
            MatchEvent.detail.is_(None),
        )

        target_ids = [
            event_id
            for (event_id,) in (
                db.query(MatchEvent.id)
                .join(Match, MatchEvent.match_id == Match.id)
                .filter(
                    Match.league_id == WORLD_CUP_LEAGUE_ID,
                    Match.season_id == WORLD_CUP_SEASON_ID,
                )
                .filter(empty_filter)
                .all()
            )
        ]

        before_count = len(target_ids)
        deleted = 0
        if target_ids:
            deleted = (
                db.query(MatchEvent)
                .filter(MatchEvent.id.in_(target_ids))
                .delete(synchronize_session=False)
            )
            db.commit()

        after_count = (
            db.query(MatchEvent)
            .join(Match, MatchEvent.match_id == Match.id)
            .filter(
                Match.league_id == WORLD_CUP_LEAGUE_ID,
                Match.season_id == WORLD_CUP_SEASON_ID,
            )
            .filter(empty_filter)
            .count()
        )
    finally:
        db.close()

    print(
        json.dumps(
            {
                "league_id": WORLD_CUP_LEAGUE_ID,
                "season_id": WORLD_CUP_SEASON_ID,
                "empty_events_before": before_count,
                "deleted": deleted,
                "empty_events_after": after_count,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
