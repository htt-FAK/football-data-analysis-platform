"""Team service helpers reused by team-facing APIs."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.season import Season
from app.models.shot import Shot
from app.models.standings import Standings
from app.models.team import Team
from app.models.team_stat import TeamStat
from app.services.season_resolver import resolve_latest_season, season_sort_key
from app.services.shot_utils import serialize_shot


class TeamService:
    """Reusable team query and serialization helpers."""

    def get_teams(
        self,
        db: Session,
        league_id: int | None = None,
        season: str | None = None,
        name: str | None = None,
    ) -> list[dict]:
        query = db.query(Team)
        if name:
            query = query.filter(Team.name.like(f"%{name}%"))
        if league_id:
            season_obj = self.resolve_league_season(db, league_id, season)
            if season and season_obj is None:
                return []
            standings_team_ids = set()
            if season_obj:
                standings_team_ids = {
                    team_id
                    for (team_id,) in db.query(Standings.team_id).filter(Standings.season_id == season_obj.id).all()
                    if team_id
                }
            home_match_query = db.query(Match.home_team_id).filter(Match.league_id == league_id)
            away_match_query = db.query(Match.away_team_id).filter(Match.league_id == league_id)
            if season_obj:
                home_match_query = home_match_query.filter(Match.season_id == season_obj.id)
                away_match_query = away_match_query.filter(Match.season_id == season_obj.id)
            match_team_ids = {
                team_id
                for (team_id,) in home_match_query.union(away_match_query)
                .all()
                if team_id
            }
            team_ids = standings_team_ids | match_team_ids
            if team_ids:
                query = query.filter(Team.id.in_(team_ids))
            else:
                query = query.filter(Team.id == -1)

        teams = query.order_by(Team.name).all()
        return [self._serialize_team(team) for team in teams]

    def get_team_detail(self, db: Session, team_id: int) -> dict | None:
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            return None
        return {
            **self._serialize_team(team),
            "venue": team.stadium,
            "founded": team.founded_year,
            "founded_year": team.founded_year,
        }

    def get_team_stats(self, db: Session, team_id: int, season: str | None = None) -> dict | None:
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            return None

        season_obj = self.resolve_team_stat_season(db, team_id, season)
        stat = (
            db.query(TeamStat)
            .filter(TeamStat.team_id == team_id, TeamStat.season_id == season_obj.id if season_obj else False)
            .first()
        ) if season_obj else None

        if not stat:
            return {"team_id": team_id, "season": season_obj.name if season_obj else None, "stats": None}

        flat_stats = {
            "matches_played": stat.matches_played,
            "wins": stat.wins,
            "draws": stat.draws,
            "losses": stat.losses,
            "goals_for": stat.goals_for,
            "goals_against": stat.goals_against,
            "xg": stat.xg_for,
            "xga": stat.xg_against,
            "xg_for": stat.xg_for,
            "xg_against": stat.xg_against,
            "possession": stat.possession,
            "shots": stat.shots_total,
            "shots_total": stat.shots_total,
            "shots_on_target": stat.shots_on_target_total,
            "shots_on_target_total": stat.shots_on_target_total,
            "passes": stat.passes_total,
            "passes_total": stat.passes_total,
            "pass_accuracy": stat.pass_accuracy,
            "corners": stat.corners,
            "fouls": stat.fouls,
            "yellow_cards": 0,
            "red_cards": 0,
            "clean_sheets": stat.clean_sheets,
            "attack_score": stat.attack_rating,
            "defense_score": stat.defense_rating,
            "overall_score": stat.overall_rating,
            "attack_rating": stat.attack_rating,
            "defense_rating": stat.defense_rating,
            "overall_rating": stat.overall_rating,
        }

        return {
            "team_id": team_id,
            "team_name": team.name,
            "season": season_obj.name,
            **flat_stats,
            "stats": flat_stats,
        }

    def get_team_radar(self, db: Session, team_id: int, season: str | None = None) -> dict | None:
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            return None

        season_obj = self.resolve_team_stat_season(db, team_id, season)
        stat = (
            db.query(TeamStat)
            .filter(TeamStat.team_id == team_id, TeamStat.season_id == season_obj.id if season_obj else False)
            .first()
        ) if season_obj else None
        if not stat or not season_obj:
            return None

        season_shot_totals = [
            float(value or 0)
            for (value,) in db.query(TeamStat.shots_total).filter(TeamStat.season_id == season_obj.id).all()
        ]
        shot_max = max(season_shot_totals) if season_shot_totals else 0.0
        shot_min = min(season_shot_totals) if season_shot_totals else 0.0
        current_shots = float(stat.shots_total or 0)
        if shot_max > shot_min:
            shot_score = round(((current_shots - shot_min) / (shot_max - shot_min)) * 100, 2)
        elif shot_max > 0:
            shot_score = 100.0
        else:
            shot_score = 0.0

        return {
            "team_id": team_id,
            "team_name": team.name,
            "season": season_obj.name,
            "dimensions": ["进攻", "防守", "控球", "传球", "射门", "综合"],
            "values": [
                stat.attack_rating or 0,
                stat.defense_rating or 0,
                round(stat.possession or 0, 1),
                round(stat.pass_accuracy or 0, 1),
                shot_score,
                stat.overall_rating or 0,
            ],
        }

    def get_team_shots(
        self,
        db: Session,
        team_id: int,
        season: str | None = None,
        limit: int = 500,
    ) -> dict | None:
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            return None

        season_obj = self.resolve_team_shot_season(db, team_id, season)
        query = db.query(Shot).join(Match, Shot.match_id == Match.id).filter(Shot.team_id == team_id)
        if season_obj:
            query = query.filter(Match.season_id == season_obj.id)
        shots = query.order_by(Match.match_date.desc(), Shot.minute.asc(), Shot.id.asc()).limit(limit).all()
        return {
            "team_id": team_id,
            "team_name": team.name,
            "season": season_obj.name if season_obj else None,
            "total": len(shots),
            "shots": [
                serialize_shot(
                    shot,
                    team_name=team.name,
                )
                for shot in shots
            ],
        }

    @staticmethod
    def resolve_team_shot_season(db: Session, team_id: int, season_name: str | None):
        season_ids = [
            season_id
            for (season_id,) in (
                db.query(Match.season_id)
                .join(Shot, Shot.match_id == Match.id)
                .filter(Shot.team_id == team_id, Match.season_id.isnot(None))
                .distinct()
                .all()
            )
            if season_id
        ]
        if not season_ids:
            return resolve_latest_season(db, season_name=season_name)

        season_rows = db.query(Season).filter(Season.id.in_(season_ids)).all()
        if season_name:
            season_rows = [row for row in season_rows if row.name == season_name]
        if not season_rows:
            return None
        return max(season_rows, key=season_sort_key)

    @staticmethod
    def resolve_season(db: Session, season_name: str | None):
        return resolve_latest_season(db, season_name=season_name)

    @staticmethod
    def resolve_team_stat_season(db: Session, team_id: int, season_name: str | None):
        season_ids = [
            season_id
            for (season_id,) in db.query(TeamStat.season_id).filter(TeamStat.team_id == team_id).distinct().all()
            if season_id
        ]
        if not season_ids:
            return resolve_latest_season(db, season_name=season_name)

        season_rows = db.query(Season).filter(Season.id.in_(season_ids)).all()
        if season_name:
            season_rows = [row for row in season_rows if row.name == season_name]
        if not season_rows:
            return None
        return max(season_rows, key=season_sort_key)

    @staticmethod
    def resolve_league_season(db: Session, league_id: int, season_name: str | None):
        return resolve_latest_season(db, league_id=league_id, season_name=season_name)

    @staticmethod
    def _serialize_team(team: Team) -> dict:
        return {
            "id": team.id,
            "name": team.name,
            "full_name": team.full_name,
            "country": team.country,
            "logo_url": team.logo_url,
            "venue": team.stadium,
            "stadium": team.stadium,
            "coach": team.coach,
            "founded": team.founded_year,
            "founded_year": team.founded_year,
        }
