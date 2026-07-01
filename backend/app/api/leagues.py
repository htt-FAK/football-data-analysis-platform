"""League endpoints for list, standings, schedule, and lightweight trends."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.params import Param
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.league import League
from app.models.match import Match
from app.models.standings import Standings
from app.models.team import Team
from app.services.league_service import LeagueService
from app.services.season_resolver import resolve_latest_season

router = APIRouter(tags=["leagues"])
league_service = LeagueService()


@router.get("/")
def list_leagues(
    country: str | None = Query(None, description="Filter by country"),
    db: Session = Depends(get_db),
):
    """Return leagues that currently have real data."""
    return league_service.get_leagues(db, country=country)


@router.get("/{league_id}")
def get_league(league_id: int, db: Session = Depends(get_db)):
    """Return league detail plus the latest resolved season name."""
    league = db.query(League).filter(League.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="未找到该联赛")

    latest_season = _resolve_season(db, league.id, None)
    serialized = league_service._serialize_league(league)
    return {
        **serialized,
        "season": latest_season.name if latest_season else None,
    }


@router.get("/{league_id}/standings")
def get_standings(
    league_id: int,
    season: str | None = Query(None, description="Season name, defaults to latest"),
    stage: str | None = Query(None, description="Filter by stage"),
    group_name: str | None = Query(None, alias="group", description="Filter by group"),
    group_name_compat: str | None = Query(None, alias="group_name", include_in_schema=False),
    db: Session = Depends(get_db),
):
    """Return standings for one league season."""
    season = _coerce_param_value(season)
    stage = _coerce_param_value(stage)
    group_name = _coerce_param_value(group_name)
    group_name_compat = _coerce_param_value(group_name_compat)
    season_obj = _resolve_season(db, league_id, season)
    if not season_obj:
        raise HTTPException(status_code=404, detail="未找到该联赛的赛季数据")

    rows = (
        db.query(Standings, Team)
        .join(Team, Standings.team_id == Team.id)
        .filter(Standings.season_id == season_obj.id)
    )
    if stage:
        normalized_stage = _normalize_stage_filter(stage)
        if normalized_stage == "group_stage":
            rows = rows.filter(
                or_(
                    Standings.stage.in_(("Group Stage", "First Stage")),
                    Standings.stage.is_(None) & Standings.group_name.isnot(None),
                )
            )
        else:
            rows = rows.filter(Standings.stage == stage)

    effective_group = group_name or group_name_compat
    if effective_group:
        rows = rows.filter(Standings.group_name == effective_group)

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


@router.get("/{league_id}/schedule")
def get_schedule(
    league_id: int,
    matchday: int | None = Query(None, description="Filter by matchday"),
    season: str | None = Query(None, description="Season name, defaults to latest"),
    stage: str | None = Query(None, description="Filter by stage"),
    group_name: str | None = Query(None, alias="group", description="Filter by group"),
    group_name_compat: str | None = Query(None, alias="group_name", include_in_schema=False),
    db: Session = Depends(get_db),
):
    """Return schedule rows for one league season."""
    matchday = _coerce_param_value(matchday)
    season = _coerce_param_value(season)
    stage = _coerce_param_value(stage)
    group_name = _coerce_param_value(group_name)
    group_name_compat = _coerce_param_value(group_name_compat)
    season_obj = _resolve_season(db, league_id, season)
    if not season_obj:
        raise HTTPException(status_code=404, detail="未找到该联赛的赛季数据")

    query = db.query(Match).filter(Match.league_id == league_id, Match.season_id == season_obj.id)
    if matchday is not None:
        query = query.filter(Match.matchday == matchday)
    if stage:
        normalized_stage = _normalize_stage_filter(stage)
        if normalized_stage == "group_stage":
            query = query.filter(Match.group_name.isnot(None))
        else:
            query = query.filter(Match.stage == stage)

    effective_group = group_name or group_name_compat
    if effective_group:
        query = query.filter(Match.group_name == effective_group)

    matches = query.order_by(Match.matchday.asc(), Match.match_date.asc()).all()
    team_ids = {match.home_team_id for match in matches} | {match.away_team_id for match in matches}
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


@router.get("/{league_id}/trends")
def get_trends(
    league_id: int,
    season: str | None = Query(None, description="Season name, defaults to latest"),
    db: Session = Depends(get_db),
):
    """Return historical team trends aggregated from finished matches."""
    season = _coerce_param_value(season)
    payload = league_service.get_trends(db, league_id, season=season)
    if not payload:
        raise HTTPException(status_code=404, detail="未找到该联赛的赛季数据")
    return payload


def _resolve_season(db: Session, league_id: int, season_name: str | None):
    """Resolve a league season by name, or fall back to the latest season."""
    return resolve_latest_season(db, league_id=league_id, season_name=season_name)


def _normalize_stage_filter(stage: str | None) -> str:
    normalized = (stage or "").strip().lower().replace("-", " ")
    normalized = " ".join(normalized.split())
    if normalized in {"group stage", "groupstage", "first stage", "firststage"}:
        return "group_stage"
    return normalized


def _coerce_param_value(value):
    """Unwrap FastAPI Param defaults when endpoints are called directly in scripts/tests."""
    if isinstance(value, Param):
        default = value.default
        return None if default is ... else default
    return value
