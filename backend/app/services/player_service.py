"""Player service layer built on the current player endpoint helpers."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.api import players as players_api
from app.models.player import Player
from app.models.team import Team


class PlayerService:
    """Service wrapper around player-related query and degradation logic."""

    def get_players(
        self,
        db: Session,
        team_id: int = None,
        league_id: int | None = None,
        season: str | None = None,
        position: str = None,
        name: str = None,
        limit: int = 100,
    ) -> list:
        query = db.query(Player)
        if team_id:
            query = query.filter(Player.team_id == team_id)
        if position:
            query = query.filter(Player.position == position)
        if name:
            query = query.filter(Player.name.like(f"%{name}%"))
        if league_id:
            season_obj = players_api._resolve_league_season(db, league_id, season)
            if season_obj:
                player_ids = [
                    player_id
                    for (player_id,) in (
                        db.query(players_api.PlayerStat.player_id)
                        .filter(players_api.PlayerStat.season_id == season_obj.id)
                        .distinct()
                        .all()
                    )
                ]
                query = query.filter(Player.id.in_(player_ids or [-1]))
            else:
                query = query.filter(Player.id == -1)

        players = query.order_by(Player.name).limit(limit).all()
        team_ids = {player.team_id for player in players if player.team_id}
        teams_map = (
            {team.id: team.name for team in db.query(Team).filter(Team.id.in_(team_ids)).all()}
            if team_ids
            else {}
        )
        return [
            {
                "id": player.id,
                "name": player.name,
                "position": player.position,
                "team_id": player.team_id,
                "team_name": teams_map.get(player.team_id),
                "nationality": player.nationality,
                "photo_url": player.photo_url,
                "overall_rating": player.overall_rating,
                "data_source": player.data_source,
            }
            for player in players
        ]

    def get_player_detail(self, db: Session, player_id: int) -> dict:
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            return {}
        team_name = None
        if player.team_id:
            team = db.query(Team).filter(Team.id == player.team_id).first()
            team_name = team.name if team else None
        return {
            "id": player.id,
            "name": player.name,
            "position": player.position,
            "shirt_number": player.shirt_number,
            "nationality": player.nationality,
            "birth_date": player.birth_date.isoformat() if player.birth_date else None,
            "height": player.height,
            "weight": player.weight,
            "photo_url": player.photo_url,
            "team_id": player.team_id,
            "team_name": team_name,
            "overall_rating": player.overall_rating,
            "data_source": player.data_source,
        }

    def get_player_stats(self, db: Session, player_id: int, season: str | None = None) -> dict:
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            return {}
        season_obj = players_api._resolve_player_stat_season(db, player_id, season)
        stat = players_api._get_stat_model(player_id, season_obj, db)
        return {
            "player_id": player_id,
            "season": season_obj.name if season_obj else None,
            "stats": players_api._serialize_stat(stat),
            "completeness": players_api._calculate_player_completeness(
                player,
                stat,
                players_api._count_key_events(player_id, db, season_obj),
                season_obj,
                db,
            ),
        }

    def get_player_radar(self, db: Session, player_id: int, position: str = None, season: str | None = None) -> dict:
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            return {}
        season_obj = players_api._resolve_player_stat_season(db, player_id, season)
        return players_api._build_radar_for(player, position or player.position, season_obj, db)

    def get_top_scorers(self, db: Session, limit: int = 10, season: str | None = None) -> list:
        season_obj = players_api._resolve_player_stats_season(db, season)
        if not season_obj:
            return []
        rows = (
            db.query(players_api.PlayerStat, Player)
            .join(Player, players_api.PlayerStat.player_id == Player.id)
            .filter(players_api.PlayerStat.season_id == season_obj.id, players_api.PlayerStat.goals > 0)
            .order_by(players_api.PlayerStat.goals.desc(), players_api.PlayerStat.xg.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "player_id": player.id,
                "name": player.name,
                "team_id": player.team_id,
                "goals": stat.goals,
                "assists": stat.assists,
                "xg": stat.xg,
                "appearances": stat.appearances,
                "minutes_played": stat.minutes_played,
            }
            for stat, player in rows
        ]

    def compare_players(self, db: Session, player_a: int, player_b: int, season: str | None = None) -> dict:
        left = db.query(Player).filter(Player.id == player_a).first()
        right = db.query(Player).filter(Player.id == player_b).first()
        if not left or not right:
            return {}
        season_obj = players_api._resolve_compare_season(db, left.id, right.id, season)
        left_stat = players_api._get_stat_model(left.id, season_obj, db)
        right_stat = players_api._get_stat_model(right.id, season_obj, db)
        left_events = players_api._key_events(left.id, db, season_obj=season_obj)
        right_events = players_api._key_events(right.id, db, season_obj=season_obj)
        left_completeness = players_api._calculate_player_completeness(left, left_stat, len(left_events), season_obj, db)
        right_completeness = players_api._calculate_player_completeness(right, right_stat, len(right_events), season_obj, db)
        return {
            "player_a": {"id": left.id, "name": left.name, "position": left.position, "team_id": left.team_id},
            "player_b": {"id": right.id, "name": right.name, "position": right.position, "team_id": right.team_id},
            "same_position": left.position == right.position,
            "radar": {
                "player_a": players_api._build_radar_for(left, left.position, season_obj, db),
                "player_b": players_api._build_radar_for(right, right.position, season_obj, db),
            },
            "season_stats": {
                "player_a": players_api._serialize_stat(left_stat),
                "player_b": players_api._serialize_stat(right_stat),
            },
            "position_rank": {
                "player_a": players_api._position_rank(left, db, season_obj, strict_season=season is not None),
                "player_b": players_api._position_rank(right, db, season_obj, strict_season=season is not None),
            },
            "key_events": {
                "player_a": left_events,
                "player_b": right_events,
            },
            "completeness": {
                "player_a": left_completeness,
                "player_b": right_completeness,
            },
            "recommended_visualization": players_api._resolve_compare_visualization(left_completeness, right_completeness),
        }

    def get_position_stats(self, db: Session, position: str, season: str | None = None) -> dict:
        return players_api.get_position_stats(position=position, season=season, db=db)

    def get_position_rank(self, db: Session, player_id: int, season: str | None = None) -> dict:
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            return {"position": None, "rank": None, "total": 0}
        season_obj = players_api._resolve_player_stat_season(db, player_id, season)
        return players_api._position_rank(player, db, season_obj, strict_season=bool(season))
