"""比赛接口 — 列表、详情、事件、xG 时间线、射门数据、复盘报告"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.match import Match
from app.models.match_event import MatchEvent
from app.models.shot import Shot
from app.models.team import Team
from app.models.player import Player

router = APIRouter(prefix="/matches", tags=["比赛"])


@router.get("/")
def list_matches(
    league_id: int | None = Query(None, description="按联赛筛选"),
    matchday: int | None = Query(None, description="按轮次筛选"),
    status: str | None = Query(None, description="按状态筛选"),
    date: str | None = Query(None, description="按日期筛选 (YYYY-MM-DD)"),
    limit: int = Query(100, description="返回条数", le=500),
    db: Session = Depends(get_db),
):
    """获取比赛列表（可选 ?league_id=, ?matchday=, ?status=, ?date=, ?limit= 参数）"""
    query = db.query(Match)
    if league_id:
        query = query.filter(Match.league_id == league_id)
    if matchday is not None:
        query = query.filter(Match.matchday == matchday)
    if status:
        query = query.filter(Match.status == status)
    if date:
        query = query.filter(Match.match_date.like(f"{date}%"))

    matches = query.order_by(Match.match_date.desc()).limit(limit).all()

    team_ids = set()
    for m in matches:
        if m.home_team_id:
            team_ids.add(m.home_team_id)
        if m.away_team_id:
            team_ids.add(m.away_team_id)
    teams_map = {t.id: t.name for t in db.query(Team).filter(Team.id.in_(team_ids)).all()} if team_ids else {}

    return [
        {
            "id": m.id,
            "league_id": m.league_id,
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
    ]


@router.get("/{match_id}")
def get_match(match_id: int, db: Session = Depends(get_db)):
    """获取比赛详情"""
    m = db.query(Match).filter(Match.id == match_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="比赛不存在")

    teams = db.query(Team).filter(Team.id.in_([m.home_team_id, m.away_team_id])).all() if (m.home_team_id or m.away_team_id) else []
    teams_map = {t.id: t.name for t in teams}

    return {
        "id": m.id,
        "league_id": m.league_id,
        "season_id": m.season_id,
        "matchday": m.matchday,
        "match_date": m.match_date.isoformat() if m.match_date else None,
        "status": m.status,
        "home_team_id": m.home_team_id,
        "home_team_name": teams_map.get(m.home_team_id),
        "away_team_id": m.away_team_id,
        "away_team_name": teams_map.get(m.away_team_id),
        "home_score": m.home_score,
        "away_score": m.away_score,
        "home_score_ht": m.home_score_ht,
        "away_score_ht": m.away_score_ht,
        "venue": m.venue,
    }


@router.get("/{match_id}/events")
def get_match_events(match_id: int, db: Session = Depends(get_db)):
    """获取比赛事件（进球/换人/红黄牌）"""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")

    events = (
        db.query(MatchEvent)
        .filter(MatchEvent.match_id == match_id)
        .order_by(MatchEvent.minute.asc())
        .all()
    )
    # 预加载球员/球队名
    player_ids = {e.player_id for e in events if e.player_id}
    team_ids = {e.team_id for e in events if e.team_id}
    players_map = {p.id: p.name for p in db.query(Player).filter(Player.id.in_(player_ids)).all()} if player_ids else {}
    teams_map = {t.id: t.name for t in db.query(Team).filter(Team.id.in_(team_ids)).all()} if team_ids else {}

    return {
        "match_id": match_id,
        "events": [
            {
                "id": e.id,
                "minute": e.minute,
                "event_type": e.event_type,
                "team_id": e.team_id,
                "team_name": teams_map.get(e.team_id),
                "player_id": e.player_id,
                "player_name": players_map.get(e.player_id),
                "detail": e.detail,
            }
            for e in events
        ],
    }


@router.get("/{match_id}/xg-timeline")
def get_match_xg_timeline(match_id: int, db: Session = Depends(get_db)):
    """获取比赛 xG 时间线（按射门累计 xG）"""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")

    shots = (
        db.query(Shot)
        .filter(Shot.match_id == match_id)
        .order_by(Shot.minute.asc())
        .all()
    )
    # 按球队分组，累计 xG
    teams_map = {}
    if match.home_team_id or match.away_team_id:
        ts = db.query(Team).filter(Team.id.in_([match.home_team_id, match.away_team_id])).all()
        teams_map = {t.id: t.name for t in ts}

    timeline = {"home": [], "away": []}
    home_cum, away_cum = 0.0, 0.0
    for s in shots:
        point = {"minute": s.minute, "xg": round(s.xg or 0, 3), "result": s.result, "cumulative": 0}
        if s.team_id == match.home_team_id:
            home_cum += s.xg or 0
            point["cumulative"] = round(home_cum, 3)
            timeline["home"].append(point)
        elif s.team_id == match.away_team_id:
            away_cum += s.xg or 0
            point["cumulative"] = round(away_cum, 3)
            timeline["away"].append(point)

    return {
        "match_id": match_id,
        "home_team": {"id": match.home_team_id, "name": teams_map.get(match.home_team_id), "final_xg": round(home_cum, 3)},
        "away_team": {"id": match.away_team_id, "name": teams_map.get(match.away_team_id), "final_xg": round(away_cum, 3)},
        "timeline": timeline,
    }


@router.get("/{match_id}/shots")
def get_match_shots(match_id: int, db: Session = Depends(get_db)):
    """获取比赛射门数据（用于射门位置图）"""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")

    shots = (
        db.query(Shot)
        .filter(Shot.match_id == match_id)
        .order_by(Shot.minute.asc())
        .all()
    )
    return {
        "match_id": match_id,
        "home_team_id": match.home_team_id,
        "away_team_id": match.away_team_id,
        "total": len(shots),
        "shots": [
            {
                "id": s.id,
                "minute": s.minute,
                "team_id": s.team_id,
                "player_id": s.player_id,
                "x_coord": s.x_coord,
                "y_coord": s.y_coord,
                "result": s.result,
                "shot_type": s.shot_type,
                "situation": s.situation,
                "xg": s.xg,
            }
            for s in shots
        ],
    }


@router.get("/{match_id}/report")
def get_match_report(match_id: int, db: Session = Depends(get_db)):
    """获取比赛复盘报告（聚合：详情 + 事件 + xG 时间线 + 射门）"""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")

    # 复用各子查询逻辑（直接调函数）
    events_data = get_match_events(match_id, db)
    xg_data = get_match_xg_timeline(match_id, db)
    shots_data = get_match_shots(match_id, db)

    teams = db.query(Team).filter(Team.id.in_([match.home_team_id, match.away_team_id])).all() if (match.home_team_id or match.away_team_id) else []
    teams_map = {t.id: t.name for t in teams}

    return {
        "match": {
            "id": match.id,
            "match_date": match.match_date.isoformat() if match.match_date else None,
            "status": match.status,
            "home_team": {"id": match.home_team_id, "name": teams_map.get(match.home_team_id)},
            "away_team": {"id": match.away_team_id, "name": teams_map.get(match.away_team_id)},
            "home_score": match.home_score,
            "away_score": match.away_score,
            "home_score_ht": match.home_score_ht,
            "away_score_ht": match.away_score_ht,
            "venue": match.venue,
        },
        "events": events_data["events"],
        "xg_timeline": xg_data,
        "shots": shots_data,
    }
