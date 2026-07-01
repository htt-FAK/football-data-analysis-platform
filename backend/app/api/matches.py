"""Match endpoints for list, detail, events, xG timeline, shots, and reports."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.match import Match
from app.models.team import Team
from app.services.match_service import MatchService, refresh_worldcup_matches, resolve_effective_match_status
from app.services.text_repair import repair_payload

router = APIRouter(tags=["matches"])
match_service = MatchService()


def _normalize_stage_filter(stage: str | None) -> str:
    normalized = (stage or "").strip().lower().replace("-", " ")
    normalized = " ".join(normalized.split())
    if normalized in {"group stage", "groupstage", "first stage", "firststage"}:
        return "group_stage"
    return normalized


@router.get("/")
def list_matches(
    league_id: int | None = Query(None, description="Filter by league"),
    matchday: int | None = Query(None, description="Filter by matchday"),
    status: str | None = Query(None, description="Filter by status"),
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
    stage: str | None = Query(None, description="Filter by stage"),
    group_name: str | None = Query(None, alias="group", description="Filter by group"),
    group_name_compat: str | None = Query(None, alias="group_name", include_in_schema=False),
    limit: int = Query(100, description="Maximum rows", le=500),
    db: Session = Depends(get_db),
):
    """Return match rows with compatibility filters for World Cup stages."""
    query = db.query(Match)
    if league_id:
        query = query.filter(Match.league_id == league_id)
    if matchday is not None:
        query = query.filter(Match.matchday == matchday)
    if status:
        query = query.filter(Match.status == status)
    if date:
        query = query.filter(Match.match_date.like(f"{date}%"))
    if stage:
        normalized_stage = _normalize_stage_filter(stage)
        if normalized_stage == "group_stage":
            query = query.filter(Match.group_name.isnot(None))
        else:
            query = query.filter(Match.stage == stage)

    effective_group = group_name or group_name_compat
    if effective_group:
        query = query.filter(Match.group_name == effective_group)

    matches = query.order_by(Match.match_date.asc(), Match.id.asc()).limit(limit).all()
    refresh_worldcup_matches(db, matches)
    matches = query.order_by(Match.match_date.asc(), Match.id.asc()).limit(limit).all()

    team_ids: list[int] = []
    for match in matches:
        team_ids.extend([match.home_team_id, match.away_team_id])

    teams_map = (
        {
            team.id: team.name
            for team in db.query(Team).filter(Team.id.in_([team_id for team_id in team_ids if team_id])).all()
        }
        if team_ids
        else {}
    )

    payload = [
        {
            "id": match.id,
            "league_id": match.league_id,
            "matchday": match.matchday,
            "date_time": match.match_date.isoformat() if match.match_date else None,
            "match_date": match.match_date.isoformat() if match.match_date else None,
            "status": resolve_effective_match_status(match),
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
    ]
    return repair_payload(payload)


@router.get("/{match_id}")
def get_match(match_id: int, db: Session = Depends(get_db)):
    """Return one match detail row."""
    match = match_service.get_match_detail(db, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")
    return repair_payload(match)


@router.get("/{match_id}/events")
def get_match_events(match_id: int, db: Session = Depends(get_db)):
    """Return normalized events for one match."""
    events = match_service.get_match_events(db, match_id)
    if not events:
        raise HTTPException(status_code=404, detail="比赛不存在")
    return repair_payload(events["events"])


@router.get("/{match_id}/xg-timeline")
def get_match_xg_timeline(match_id: int, db: Session = Depends(get_db)):
    """Return the shot-derived xG timeline for one match."""
    timeline = match_service.get_xg_timeline(db, match_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="比赛不存在")
    return repair_payload(timeline)


@router.get("/{match_id}/shots")
def get_match_shots(match_id: int, db: Session = Depends(get_db)):
    """Return shot map data for one match."""
    shots = match_service.get_match_shots(db, match_id)
    if not shots:
        raise HTTPException(status_code=404, detail="比赛不存在")
    return repair_payload(shots["shots"])


@router.get("/{match_id}/report")
def get_match_report(match_id: int, db: Session = Depends(get_db)):
    """Return the aggregated report payload for one match."""
    report = match_service.get_match_report(db, match_id)
    if not report:
        raise HTTPException(status_code=404, detail="比赛不存在")
    return repair_payload(report)
