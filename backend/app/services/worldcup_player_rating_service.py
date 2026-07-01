"""World Cup player dimension rating backfill service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.analysis.player_rating import PlayerRating
from app.models.league import League
from app.models.player import Player
from app.models.player_stat import PlayerStat
from app.services.ingest_service import FIFA_DEFAULT_LEAGUE_NAME, FIFA_DEFAULT_SEASON_NAME
from app.services.season_resolver import resolve_latest_season


class WorldCupPlayerRatingService:
    """Calculate and persist dimension scores for World Cup players."""

    def __init__(self) -> None:
        self.rating = PlayerRating()

    def refresh(self, db: Session, season_name: str = FIFA_DEFAULT_SEASON_NAME) -> dict[str, int]:
        league = (
            db.query(League)
            .filter(League.name == FIFA_DEFAULT_LEAGUE_NAME)
            .order_by(League.id.desc())
            .first()
        )
        season = resolve_latest_season(
            db,
            league_id=league.id if league else None,
            season_name=season_name,
        )
        if not season:
            return {"updated": 0, "skipped": 0}

        rows = (
            db.query(PlayerStat, Player)
            .join(Player, PlayerStat.player_id == Player.id)
            .filter(PlayerStat.season_id == season.id)
            .all()
        )

        updated = 0
        skipped = 0
        for stat, player in rows:
            stats = {
                "appearances": stat.appearances,
                "goals": stat.goals,
                "assists": stat.assists,
                "yellow_cards": stat.yellow_cards,
                "red_cards": stat.red_cards,
                "minutes_played": stat.minutes_played,
                "shots": stat.shots,
                "shots_on_target": stat.shots_on_target,
                "xg": stat.xg,
                "xa": stat.xa,
                "passes": stat.passes,
                "pass_accuracy": stat.pass_accuracy,
                "tackles": stat.tackles,
                "interceptions": stat.interceptions,
                "rating": stat.rating,
                "saves": player.saves,
                "save_rate": player.save_rate,
                "xcs": player.xcs,
                "sweeper_actions": player.sweeper_actions,
            }
            scores = self.rating.calculate_dimension_scores(player.position, stats)
            overall = self.rating.calculate_overall(player.position, scores)

            before = (
                float(player.atk_score or 0),
                float(player.org_score or 0),
                float(player.def_score or 0),
                float(player.gk_score or 0),
                float(player.phy_score or 0),
                float(player.dis_score or 0),
                float(player.overall_rating or 0),
            )
            after = (
                scores["atk"],
                scores["org"],
                scores["def"],
                scores["gk"],
                scores["phy"],
                scores["dis"],
                overall,
            )
            if before == after:
                skipped += 1
                continue

            player.atk_score = scores["atk"]
            player.org_score = scores["org"]
            player.def_score = scores["def"]
            player.gk_score = scores["gk"]
            player.phy_score = scores["phy"]
            player.dis_score = scores["dis"]
            player.overall_rating = overall
            updated += 1

        db.commit()
        return {"updated": updated, "skipped": skipped}
