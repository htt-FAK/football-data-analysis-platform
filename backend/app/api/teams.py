"""Team endpoints for list, detail, stats, radar, and shots."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.team import Team
from app.services.team_service import TeamService
from app.services.text_repair import repair_payload

router = APIRouter(tags=["teams"])
team_service = TeamService()


@router.get("/")
def list_teams(
    league_id: int | None = Query(None, description="Filter by league"),
    season: str | None = Query(None, description="Season name, defaults to latest"),
    name: str | None = Query(None, description="Fuzzy search by team name"),
    db: Session = Depends(get_db),
):
    """Return teams, optionally filtered by league, season, or name."""
    return repair_payload(team_service.get_teams(db, league_id=league_id, season=season, name=name))


@router.get("/{team_id}")
def get_team(team_id: int, db: Session = Depends(get_db)):
    """Return one team detail row."""
    team = team_service.get_team_detail(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="球队不存在")
    return repair_payload(team)


@router.get("/{team_id}/stats")
def get_team_stats(
    team_id: int,
    season: str | None = Query(None, description="Season name, defaults to latest"),
    db: Session = Depends(get_db),
):
    """Return season stats for one team."""
    stats = team_service.get_team_stats(db, team_id, season=season)
    if stats is None:
        raise HTTPException(status_code=404, detail="球队不存在")
    return repair_payload(stats)


@router.get("/{team_id}/radar")
def get_team_radar(
    team_id: int,
    season: str | None = Query(None, description="Season name, defaults to latest"),
    db: Session = Depends(get_db),
):
    """Return radar metrics for one team."""
    radar = team_service.get_team_radar(db, team_id, season=season)
    if db.query(Team).filter(Team.id == team_id).first() is None:
        raise HTTPException(status_code=404, detail="球队不存在")
    if radar is None:
        raise HTTPException(status_code=404, detail="没有该球队的赛季统计数据")
    return repair_payload(radar)


@router.get("/{team_id}/shots")
def get_team_shots(
    team_id: int,
    season: str | None = Query(None, description="Season name, defaults to latest available shot season"),
    limit: int = Query(500, description="Maximum rows"),
    db: Session = Depends(get_db),
):
    """Return shot map data for one team."""
    shots = team_service.get_team_shots(db, team_id, season=season, limit=limit)
    if shots is None:
        raise HTTPException(status_code=404, detail="球队不存在")
    return repair_payload(shots["shots"])
