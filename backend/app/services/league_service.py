"""League service helpers aligned with the current league-facing APIs."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.league import League
from app.models.match import Match
from app.models.player_stat import PlayerStat
from app.models.season import Season
from app.models.standings import Standings
from app.models.team import Team
from app.models.team_stat import TeamStat
from app.services.season_resolver import resolve_latest_season


class LeagueService:
    """Reusable league queries for list, standings, schedule, and trends."""

    def get_leagues(self, db: Session, country: str | None = None) -> list[dict]:
        query = db.query(League)
        leagues = query.order_by(League.id.asc()).all()
        payload = [
            self._serialize_league(league)
            for league in leagues
            if self._has_content(db, league.id)
        ]
        if country:
            payload = [league for league in payload if league["country"] == country]
        return payload

    def get_standings(
        self,
        db: Session,
        league_id: int,
        season: str | None = None,
        stage: str | None = None,
        group_name: str | None = None,
    ) -> dict | None:
        season_obj = self._resolve_season(db, league_id, season)
        if not season_obj:
            return None

        rows = (
            db.query(Standings, Team)
            .join(Team, Standings.team_id == Team.id)
            .filter(Standings.season_id == season_obj.id)
        )
        if stage:
            normalized_stage = self._normalize_stage_filter(stage)
            if normalized_stage == "group_stage":
                rows = rows.filter(
                    (Standings.stage.in_(("Group Stage", "First Stage")))
                    | (Standings.stage.is_(None) & Standings.group_name.isnot(None))
                )
            else:
                rows = rows.filter(Standings.stage == stage)
        if group_name:
            rows = rows.filter(Standings.group_name == group_name)

        rows = rows.order_by(Standings.group_name.asc(), Standings.position.asc(), Standings.points.desc()).all()
        return {
            "league_id": league_id,
            "season": season_obj.name,
            "standings": [
                {
                    "position": standing.position,
                    "group": standing.group_name,
                    "stage": standing.stage,
                    "team_id": team.id,
                    "team_name": team.name,
                    "logo_url": team.logo_url,
                    "played": standing.played,
                    "won": standing.won,
                    "drawn": standing.drawn,
                    "lost": standing.lost,
                    "goals_for": standing.goals_for,
                    "goals_against": standing.goals_against,
                    "goal_diff": standing.goal_diff,
                    "points": standing.points,
                    "form": standing.form,
                    "qualification_status": standing.qualification_status,
                }
                for standing, team in rows
            ],
        }

    def get_schedule(
        self,
        db: Session,
        league_id: int,
        season: str | None = None,
        matchday: int | None = None,
        stage: str | None = None,
        group_name: str | None = None,
    ) -> dict | None:
        season_obj = self._resolve_season(db, league_id, season)
        if not season_obj:
            return None

        query = db.query(Match).filter(Match.league_id == league_id, Match.season_id == season_obj.id)
        if matchday is not None:
            query = query.filter(Match.matchday == matchday)
        if stage:
            normalized_stage = self._normalize_stage_filter(stage)
            if normalized_stage == "group_stage":
                query = query.filter(Match.group_name.isnot(None))
            else:
                query = query.filter(Match.stage == stage)
        if group_name:
            query = query.filter(Match.group_name == group_name)

        matches = query.order_by(Match.matchday.asc(), Match.match_date.asc(), Match.id.asc()).all()
        team_ids = {match.home_team_id for match in matches if match.home_team_id}
        team_ids |= {match.away_team_id for match in matches if match.away_team_id}
        teams_map = (
            {team.id: team.name for team in db.query(Team).filter(Team.id.in_(team_ids)).all()}
            if team_ids
            else {}
        )

        return {
            "league_id": league_id,
            "season": season_obj.name,
            "matches": [
                {
                    "id": match.id,
                    "matchday": match.matchday,
                    "match_date": match.match_date.isoformat() if match.match_date else None,
                    "status": match.status,
                    "home_team_id": match.home_team_id,
                    "home_team_name": teams_map.get(match.home_team_id),
                    "away_team_id": match.away_team_id,
                    "away_team_name": teams_map.get(match.away_team_id),
                    "home_score": match.home_score,
                    "away_score": match.away_score,
                    "venue": match.venue,
                    "stage": match.stage,
                    "group": match.group_name,
                }
                for match in matches
            ],
        }

    def get_trends(self, db: Session, league_id: int, season: str | None = None) -> dict | None:
        season_obj = self._resolve_season(db, league_id, season)
        if not season_obj:
            return None

        rows = (
            db.query(Standings, Team)
            .join(Team, Standings.team_id == Team.id)
            .filter(Standings.season_id == season_obj.id)
            .order_by(Standings.position.asc())
            .all()
        )
        standings_map = {
            standing.team_id: (standing, team)
            for standing, team in rows
            if standing.team_id
        }
        team_ids = [team_id for team_id in standings_map.keys() if team_id]
        finished_matches = (
            db.query(Match)
            .filter(
                Match.league_id == league_id,
                Match.season_id == season_obj.id,
                Match.status == "finished",
            )
            .order_by(Match.match_date.asc(), Match.id.asc())
            .all()
        )
        trend_state = defaultdict(
            lambda: {
                "points": 0,
                "goal_diff": 0,
                "goals_for": 0,
                "goals_against": 0,
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "results": [],
                "timeline": [],
            }
        )

        for match in finished_matches:
            home_team_id = match.home_team_id
            away_team_id = match.away_team_id
            if not home_team_id or not away_team_id:
                continue
            if home_team_id not in standings_map and away_team_id not in standings_map:
                continue

            home_score = int(match.home_score or 0)
            away_score = int(match.away_score or 0)
            home_result, away_result = self._result_pair(home_score, away_score)

            if home_team_id in standings_map:
                self._append_trend_snapshot(
                    trend_state,
                    match=match,
                    team_id=home_team_id,
                    opponent_team_id=away_team_id,
                    opponent_team_name=standings_map.get(away_team_id, (None, None))[1].name if away_team_id in standings_map else None,
                    goals_for=home_score,
                    goals_against=away_score,
                    result=home_result,
                )
            if away_team_id in standings_map:
                self._append_trend_snapshot(
                    trend_state,
                    match=match,
                    team_id=away_team_id,
                    opponent_team_id=home_team_id,
                    opponent_team_name=standings_map.get(home_team_id, (None, None))[1].name if home_team_id in standings_map else None,
                    goals_for=away_score,
                    goals_against=home_score,
                    result=away_result,
                )

        note = (
            "已基于已完赛比赛按时间顺序聚合累计积分趋势"
            if finished_matches
            else "当前仅有 standings 快照，待出现已完赛比赛后补齐历史趋势"
        )
        return {
            "league_id": league_id,
            "season": season_obj.name,
            "note": note,
            "trends": [
                {
                    "team_id": team.id,
                    "team_name": team.name,
                    "current_points": standing.points,
                    "position": standing.position,
                    "form": standing.form,
                    "played": standing.played,
                    "won": standing.won,
                    "drawn": standing.drawn,
                    "lost": standing.lost,
                    "goals_for": standing.goals_for,
                    "goals_against": standing.goals_against,
                    "goal_diff": standing.goal_diff,
                    "group": standing.group_name,
                    "timeline": trend_state[team.id]["timeline"],
                    "points_timeline": [
                        {
                            "match_id": item["match_id"],
                            "matchday": item["matchday"],
                            "match_date": item["match_date"],
                            "points": item["points"],
                        }
                        for item in trend_state[team.id]["timeline"]
                    ],
                }
                for standing, team in rows
            ],
        }

    @staticmethod
    def _resolve_season(db: Session, league_id: int, season_name: str | None):
        return resolve_latest_season(db, league_id=league_id, season_name=season_name)

    @staticmethod
    def _has_content(db: Session, league_id: int) -> bool:
        if db.query(Match.id).filter(Match.league_id == league_id).first():
            return True

        season_ids = [
            season_id
            for (season_id,) in db.query(Season.id).filter(Season.league_id == league_id).all()
        ]
        if not season_ids:
            return False

        if db.query(Standings.id).filter(Standings.season_id.in_(season_ids)).first():
            return True
        if db.query(PlayerStat.id).filter(PlayerStat.season_id.in_(season_ids)).first():
            return True
        if db.query(TeamStat.id).filter(TeamStat.season_id.in_(season_ids)).first():
            return True
        return False

    @staticmethod
    def _serialize_league(league: League) -> dict:
        return {
            "id": league.id,
            "name": league.name,
            "country": league.country or LeagueService._infer_country(league.name),
            "logo_url": league.logo_url,
            "type": league.type,
        }

    @staticmethod
    def _infer_country(name: str | None) -> str | None:
        normalized = (name or "").strip().lower()
        if normalized in {"世界杯", "fifa world cup", "fifa world cup™", "world cup", "wc"}:
            return "World"
        if normalized in {"英超", "premier league", "epl", "pl"}:
            return "England"
        return None

    @staticmethod
    def _normalize_stage_filter(stage: str | None) -> str:
        normalized = (stage or "").strip().lower().replace("-", " ")
        normalized = " ".join(normalized.split())
        if normalized in {"group stage", "groupstage", "first stage", "firststage"}:
            return "group_stage"
        return normalized

    @staticmethod
    def _result_pair(home_score: int, away_score: int) -> tuple[str, str]:
        if home_score > away_score:
            return "W", "L"
        if home_score < away_score:
            return "L", "W"
        return "D", "D"

    @staticmethod
    def _append_trend_snapshot(
        trend_state: dict,
        *,
        match: Match,
        team_id: int,
        opponent_team_id: int,
        opponent_team_name: str | None,
        goals_for: int,
        goals_against: int,
        result: str,
    ) -> None:
        state = trend_state[team_id]
        state["played"] += 1
        state["goals_for"] += goals_for
        state["goals_against"] += goals_against
        state["goal_diff"] += goals_for - goals_against
        state["results"].append(result)
        if result == "W":
            state["wins"] += 1
            state["points"] += 3
        elif result == "D":
            state["draws"] += 1
            state["points"] += 1
        else:
            state["losses"] += 1

        state["timeline"].append(
            {
                "match_id": match.id,
                "matchday": match.matchday,
                "match_date": match.match_date.isoformat() if match.match_date else None,
                "stage": match.stage,
                "group": match.group_name,
                "opponent_team_id": opponent_team_id,
                "opponent_team_name": opponent_team_name,
                "goals_for": goals_for,
                "goals_against": goals_against,
                "result": result,
                "points": state["points"],
                "goal_diff": state["goal_diff"],
                "played": state["played"],
            }
        )
