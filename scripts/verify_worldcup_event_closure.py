"""Verify World Cup 2026 event coverage, cleanup status, and sample API behavior."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import and_


WORLD_CUP_LEAGUE_ID = 3
WORLD_CUP_SEASON_ID = 4
SAMPLE_MATCH_IDS = [1521, 1522, 1523, 1524, 1525]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "backend"))

    from app.api.matches import get_match_events, get_match_report
    from app.api.worldcup import get_worldcup_coverage
    from app.database import SessionLocal
    from app.models.match import Match
    from app.models.match_event import MatchEvent
    from app.models.team import Team

    db = SessionLocal()
    try:
        worldcup_matches = (
            db.query(Match)
            .filter(
                Match.league_id == WORLD_CUP_LEAGUE_ID,
                Match.season_id == WORLD_CUP_SEASON_ID,
                Match.status == "finished",
                Match.group_name.isnot(None),
            )
            .all()
        )
        target_match_ids = [match.id for match in worldcup_matches]

        empty_event_filter = and_(
            MatchEvent.minute.is_(None),
            MatchEvent.event_type.is_(None),
            MatchEvent.team_id.is_(None),
            MatchEvent.player_id.is_(None),
            MatchEvent.detail.is_(None),
        )

        total_event_rows = (
            db.query(MatchEvent)
            .filter(MatchEvent.match_id.in_(target_match_ids or [-1]))
            .count()
        )
        empty_event_rows = (
            db.query(MatchEvent)
            .filter(MatchEvent.match_id.in_(target_match_ids or [-1]))
            .filter(empty_event_filter)
            .count()
        )
        covered_match_count = (
            db.query(MatchEvent.match_id)
            .filter(MatchEvent.match_id.in_(target_match_ids or [-1]))
            .filter(MatchEvent.event_type.isnot(None))
            .distinct()
            .count()
        )

        sample_matches = (
            db.query(Match)
            .filter(Match.id.in_(SAMPLE_MATCH_IDS))
            .order_by(Match.id.asc())
            .all()
        )
        team_ids = {
            team_id
            for match in sample_matches
            for team_id in (match.home_team_id, match.away_team_id)
            if team_id
        }
        teams_map = {team.id: team.name for team in db.query(Team).filter(Team.id.in_(team_ids)).all()} if team_ids else {}

        sample_results = []
        for match in sample_matches:
            events_payload = get_match_events(match.id, db)
            report_payload = get_match_report(match.id, db)
            sample_results.append(
                {
                    "match_id": match.id,
                    "match_date": match.match_date.isoformat() if match.match_date else None,
                    "home_team": teams_map.get(match.home_team_id),
                    "away_team": teams_map.get(match.away_team_id),
                    "group": match.group_name,
                    "events_count": len(events_payload),
                    "report_events_count": len(report_payload["events"]),
                    "first_event": events_payload[0] if events_payload else None,
                }
            )

        coverage_payload = get_worldcup_coverage("2026", db)
    finally:
        db.close()

    print(
        json.dumps(
            {
                "league_id": WORLD_CUP_LEAGUE_ID,
                "season_id": WORLD_CUP_SEASON_ID,
                "finished_group_stage_matches": len(worldcup_matches),
                "covered_matches": covered_match_count,
                "total_event_rows": total_event_rows,
                "empty_event_rows": empty_event_rows,
                "coverage": coverage_payload,
                "sample_matches": sample_results,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
