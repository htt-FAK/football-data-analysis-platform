"""Run FIFA World Cup ingest into MySQL and verify key API-ready counts."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.leagues import get_schedule, get_standings  # noqa: E402
from app.api.players import list_players  # noqa: E402
from app.crawlers.fifa_official import FIFAOfficialCrawler  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.league import League  # noqa: E402
from app.models.season import Season  # noqa: E402
from app.services.ingest_service import (  # noqa: E402
    FIFA_DEFAULT_LEAGUE_NAME,
    FIFA_DEFAULT_SEASON_NAME,
    ingest_matches,
    ingest_player_stats,
    ingest_standings,
    ingest_team_stats,
)
from app.services.worldcup_player_rating_service import WorldCupPlayerRatingService  # noqa: E402


def ensure_worldcup_schema(db) -> None:
    patches = {
        "matches": {
            "stage": "ALTER TABLE matches ADD COLUMN stage VARCHAR(50) COMMENT '比赛阶段'",
            "group_name": "ALTER TABLE matches ADD COLUMN group_name VARCHAR(50) COMMENT '小组名称'",
        },
        "standings": {
            "group_name": "ALTER TABLE standings ADD COLUMN group_name VARCHAR(50) COMMENT '小组名称'",
            "stage": "ALTER TABLE standings ADD COLUMN stage VARCHAR(50) COMMENT '比赛阶段'",
            "qualification_status": "ALTER TABLE standings ADD COLUMN qualification_status VARCHAR(50) COMMENT '出线状态'",
        },
    }
    for table, columns in patches.items():
        existing = {
            row[0]
            for row in db.execute(text(f"SHOW COLUMNS FROM {table}")).fetchall()
        }
        for column, sql in columns.items():
            if column not in existing:
                db.execute(text(sql))
    db.commit()


def main() -> int:
    db = SessionLocal()
    try:
        ensure_worldcup_schema(db)

        crawler = FIFAOfficialCrawler()
        schedule_raw = crawler.crawl("schedule")
        standings_raw = crawler.crawl("standings")
        players_raw = crawler.crawl("players")
        statistics_raw = crawler.crawl("statistics")

        schedule_stats = ingest_matches(
            db,
            schedule_raw,
            source="fifa_official",
            league_name=FIFA_DEFAULT_LEAGUE_NAME,
            season_name=FIFA_DEFAULT_SEASON_NAME,
        )
        standings_stats = ingest_standings(
            db,
            standings_raw,
            source="fifa_official",
            league_name=FIFA_DEFAULT_LEAGUE_NAME,
            season_name=FIFA_DEFAULT_SEASON_NAME,
        )
        player_stats = ingest_player_stats(
            db,
            players_raw,
            source="fifa_official",
            league_name=FIFA_DEFAULT_LEAGUE_NAME,
            season_name=FIFA_DEFAULT_SEASON_NAME,
        )
        team_stats = ingest_team_stats(
            db,
            statistics_raw,
            source="fifa_official",
            league_name=FIFA_DEFAULT_LEAGUE_NAME,
            season_name=FIFA_DEFAULT_SEASON_NAME,
        )
        rating_refresh = WorldCupPlayerRatingService().refresh(db, season_name=FIFA_DEFAULT_SEASON_NAME)

        league = db.query(League).filter(League.name == FIFA_DEFAULT_LEAGUE_NAME).first()
        season = (
            db.query(Season)
            .filter(Season.league_id == league.id, Season.name == FIFA_DEFAULT_SEASON_NAME)
            .first()
            if league
            else None
        )

        print(f"SCHEDULE_INGEST={schedule_stats}")
        print(f"STANDINGS_INGEST={standings_stats}")
        print(f"PLAYER_STATS_INGEST={player_stats}")
        print(f"TEAM_STATS_INGEST={team_stats}")
        print(f"PLAYER_RATING_REFRESH={rating_refresh}")
        print(f"LEAGUE_ID={league.id if league else None}")
        print(f"SEASON_ID={season.id if season else None}")

        if league:
            standings_payload = get_standings(
                league.id,
                season=FIFA_DEFAULT_SEASON_NAME,
                stage=None,
                group_name=None,
                db=db,
            )
            schedule_payload = get_schedule(
                league.id,
                matchday=None,
                season=FIFA_DEFAULT_SEASON_NAME,
                stage=None,
                group_name=None,
                db=db,
            )
            players_payload = list_players(
                team_id=None,
                league_id=league.id,
                season=FIFA_DEFAULT_SEASON_NAME,
                position=None,
                name=None,
                limit=10,
                db=db,
            )
            print(f"API_STANDINGS_ROWS={len(standings_payload['standings'])}")
            print(f"API_SCHEDULE_ROWS={len(schedule_payload['matches'])}")
            print(f"API_PLAYERS_SAMPLE={len(players_payload)}")
            if standings_payload["standings"]:
                print(f"API_STANDINGS_SAMPLE={standings_payload['standings'][0]}")
            if schedule_payload["matches"]:
                print(f"API_SCHEDULE_SAMPLE={schedule_payload['matches'][0]}")
            if players_payload:
                print(f"API_PLAYERS_SAMPLE_ROW={players_payload[0]}")

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
