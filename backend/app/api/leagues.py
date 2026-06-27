"""联赛接口 — 联赛列表、积分榜、赛程、积分趋势"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.league import League
from app.models.season import Season
from app.models.standings import Standings
from app.models.team import Team
from app.models.match import Match

router = APIRouter(prefix="/leagues", tags=["联赛"])


@router.get("/")
def list_leagues(
    country: str | None = Query(None, description="按国家筛选"),
    db: Session = Depends(get_db),
):
    """获取联赛列表（可选 ?country= 参数）"""
    query = db.query(League)
    if country:
        query = query.filter(League.country == country)
    leagues = query.order_by(League.id).all()
    return [
        {
            "id": lg.id,
            "name": lg.name,
            "country": lg.country,
            "logo_url": lg.logo_url,
            "type": lg.type,
        }
        for lg in leagues
    ]


@router.get("/{league_id}/standings")
def get_standings(
    league_id: int,
    season: str | None = Query(None, description="赛季名称，默认最新赛季"),
    db: Session = Depends(get_db),
):
    """获取指定联赛的积分榜"""
    season_obj = _resolve_season(db, league_id, season)
    if not season_obj:
        raise HTTPException(status_code=404, detail="未找到该联赛的赛季数据")

    rows = (
        db.query(Standings, Team)
        .join(Team, Standings.team_id == Team.id)
        .filter(Standings.season_id == season_obj.id)
        .order_by(Standings.position.asc(), Standings.points.desc())
        .all()
    )
    return {
        "league_id": league_id,
        "season": season_obj.name,
        "standings": [
            {
                "position": s.position,
                "team_id": t.id,
                "team_name": t.name,
                "logo_url": t.logo_url,
                "played": s.played,
                "won": s.won,
                "drawn": s.drawn,
                "lost": s.lost,
                "goals_for": s.goals_for,
                "goals_against": s.goals_against,
                "goal_diff": s.goal_diff,
                "points": s.points,
                "form": s.form,
            }
            for s, t in rows
        ],
    }


@router.get("/{league_id}/schedule")
def get_schedule(
    league_id: int,
    matchday: int | None = Query(None, description="按轮次筛选"),
    season: str | None = Query(None, description="赛季名称，默认最新赛季"),
    db: Session = Depends(get_db),
):
    """获取指定联赛的赛程（可选 ?matchday=, ?season= 参数）"""
    season_obj = _resolve_season(db, league_id, season)
    if not season_obj:
        raise HTTPException(status_code=404, detail="未找到该联赛的赛季数据")

    query = db.query(Match).filter(Match.league_id == league_id, Match.season_id == season_obj.id)
    if matchday is not None:
        query = query.filter(Match.matchday == matchday)
    matches = query.order_by(Match.matchday.asc(), Match.match_date.asc()).all()

    # 预加载球队名，避免 N+1
    team_ids = {m.home_team_id for m in matches} | {m.away_team_id for m in matches}
    teams_map = {t.id: t.name for t in db.query(Team).filter(Team.id.in_(team_ids)).all()} if team_ids else {}

    return {
        "league_id": league_id,
        "season": season_obj.name,
        "matches": [
            {
                "id": m.id,
                "matchday": m.matchday,
                "match_date": m.match_date.isoformat() if m.match_date else None,
                "status": m.status,
                "home_team_id": m.home_team_id,
                "home_team_name": teams_map.get(m.home_team_id),
                "away_team_id": m.away_team_id,
                "away_team_name": teams_map.get(m.away_team_id),
                "home_score": m.home_score,
                "away_score": m.away_score,
                "venue": m.venue,
            }
            for m in matches
        ],
    }


@router.get("/{league_id}/trends")
def get_trends(
    league_id: int,
    season: str | None = Query(None, description="赛季名称，默认最新赛季"),
    db: Session = Depends(get_db),
):
    """获取指定联赛的积分趋势

    说明：当前版本基于现有积分榜返回单点快照（每队当前积分 + 近期战绩 form）。
    完整的历史多轮趋势需要 standings 历史快照表（按轮次记录），后续迭代补齐。
    """
    season_obj = _resolve_season(db, league_id, season)
    if not season_obj:
        raise HTTPException(status_code=404, detail="未找到该联赛的赛季数据")

    rows = (
        db.query(Standings, Team)
        .join(Team, Standings.team_id == Team.id)
        .filter(Standings.season_id == season_obj.id)
        .order_by(Standings.position.asc())
        .all()
    )
    return {
        "league_id": league_id,
        "season": season_obj.name,
        "note": "当前为单点快照，多轮历史趋势待 standings 历史快照表补齐",
        "trends": [
            {
                "team_id": t.id,
                "team_name": t.name,
                "current_points": s.points,
                "position": s.position,
                "form": s.form,  # 近 N 场战绩字符串，如 "WWDLW"
            }
            for s, t in rows
        ],
    }


def _resolve_season(db: Session, league_id: int, season_name: str | None):
    """解析赛季：指定名称则按名称查，否则取该联赛最新的赛季"""
    query = db.query(Season).filter(Season.league_id == league_id)
    if season_name:
        query = query.filter(Season.name == season_name)
    return query.order_by(Season.id.desc()).first()
