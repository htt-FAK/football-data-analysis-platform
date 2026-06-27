"""球员接口 — 列表、射手榜、详情、统计、按位置六边图、位置排名、双人对比"""

import statistics

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.player import Player
from app.models.player_stat import PlayerStat
from app.models.team import Team
from app.models.season import Season
from app.models.match_event import MatchEvent

router = APIRouter(prefix="/players", tags=["球员"])


@router.get("/")
def list_players(
    team_id: int | None = Query(None, description="按球队筛选"),
    position: str | None = Query(None, description="按位置筛选（GK/DF/MF/FW）"),
    name: str | None = Query(None, description="按姓名模糊搜索"),
    limit: int = Query(100, description="返回条数", le=500),
    db: Session = Depends(get_db),
):
    """获取球员列表（可选 ?team_id=, ?position=, ?name=, ?limit= 参数）"""
    query = db.query(Player)
    if team_id:
        query = query.filter(Player.team_id == team_id)
    if position:
        query = query.filter(Player.position == position)
    if name:
        query = query.filter(Player.name.like(f"%{name}%"))
    players = query.order_by(Player.name).limit(limit).all()

    team_ids = {p.team_id for p in players if p.team_id}
    teams_map = {t.id: t.name for t in db.query(Team).filter(Team.id.in_(team_ids)).all()} if team_ids else {}

    return [
        {
            "id": p.id,
            "name": p.name,
            "position": p.position,
            "team_id": p.team_id,
            "team_name": teams_map.get(p.team_id),
            "nationality": p.nationality,
            "photo_url": p.photo_url,
            "overall_rating": p.overall_rating,
        }
        for p in players
    ]


@router.get("/top-scorers")
def get_top_scorers(
    limit: int = Query(10, description="返回条数", le=100),
    season: str | None = Query(None, description="赛季名称，默认最新赛季"),
    db: Session = Depends(get_db),
):
    """获取射手榜（可选 ?limit=, ?season= 参数）"""
    season_obj = _resolve_season(db, season)
    if not season_obj:
        return []

    rows = (
        db.query(PlayerStat, Player)
        .join(Player, PlayerStat.player_id == Player.id)
        .filter(PlayerStat.season_id == season_obj.id, PlayerStat.goals > 0)
        .order_by(PlayerStat.goals.desc(), PlayerStat.xg.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "player_id": p.id,
            "name": p.name,
            "team_id": p.team_id,
            "goals": ps.goals,
            "assists": ps.assists,
            "xg": ps.xg,
            "appearances": ps.appearances,
            "minutes_played": ps.minutes_played,
        }
        for ps, p in rows
    ]


@router.get("/compare")
def compare_players(
    player_a: int = Query(..., description="球员 A 的 ID"),
    player_b: int = Query(..., description="球员 B 的 ID"),
    season: str | None = Query(None, description="赛季名称，默认最新赛季"),
    db: Session = Depends(get_db),
):
    """双人对比：雷达 + 赛季数据 + 关键事件 + 同位置排名"""
    pa = db.query(Player).filter(Player.id == player_a).first()
    pb = db.query(Player).filter(Player.id == player_b).first()
    if not pa or not pb:
        raise HTTPException(status_code=404, detail="球员不存在")

    season_obj = _resolve_season(db, season)

    # 雷达数据（按各自位置）
    radar_a = _build_radar(pa, season_obj, db)
    radar_b = _build_radar(pb, season_obj, db)

    # 赛季数据
    stat_a = _get_stat(pa.id, season_obj, db)
    stat_b = _get_stat(pb.id, season_obj, db)

    # 同位置排名
    rank_a = _position_rank(pa, season_obj, db)
    rank_b = _position_rank(pb, season_obj, db)

    # 关键事件（本赛季进球/助攻）
    events_a = _key_events(pa.id, db)
    events_b = _key_events(pb.id, db)

    return {
        "player_a": {"id": pa.id, "name": pa.name, "position": pa.position, "team_id": pa.team_id},
        "player_b": {"id": pb.id, "name": pb.name, "position": pb.position, "team_id": pb.team_id},
        "same_position": pa.position == pb.position,
        "radar": {"player_a": radar_a, "player_b": radar_b},
        "season_stats": {"player_a": stat_a, "player_b": stat_b},
        "position_rank": {"player_a": rank_a, "player_b": rank_b},
        "key_events": {"player_a": events_a, "player_b": events_b},
    }


@router.get("/position-stats")
def get_position_stats(
    position: str = Query(..., description="位置，如 FW/MF/DF/GK"),
    season: str | None = Query(None, description="赛季名称，默认最新赛季"),
    db: Session = Depends(get_db),
):
    """同位置球员能力分布（箱线图数据）"""
    season_obj = _resolve_season(db, season)
    if not season_obj:
        return {"position": position, "distributions": {}}

    players = (
        db.query(Player)
        .filter(Player.position == position)
        .all()
    )
    # 收集各评分维度的分布
    dims = ["atk_score", "org_score", "def_score", "phy_score", "dis_score"]
    if position == "GK":
        dims = ["gk_score", "org_score", "phy_score", "dis_score"]

    distributions = {dim: [getattr(p, dim, 0) for p in players] for dim in dims}
    # 计算箱线图统计量
    box_stats = {}
    for dim, values in distributions.items():
        if values:
            sv = sorted(values)
            n = len(sv)
            box_stats[dim] = {
                "min": sv[0],
                "q1": sv[n // 4],
                "median": statistics.median(sv),
                "q3": sv[3 * n // 4],
                "max": sv[-1],
            }
        else:
            box_stats[dim] = {"min": 0, "q1": 0, "median": 0, "q3": 0, "max": 0}

    return {"position": position, "count": len(players), "distributions": box_stats}


@router.get("/{player_id}")
def get_player(player_id: int, db: Session = Depends(get_db)):
    """获取球员详情"""
    p = db.query(Player).filter(Player.id == player_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="球员不存在")
    team_name = None
    if p.team_id:
        team = db.query(Team).filter(Team.id == p.team_id).first()
        team_name = team.name if team else None
    return {
        "id": p.id,
        "name": p.name,
        "position": p.position,
        "shirt_number": p.shirt_number,
        "nationality": p.nationality,
        "birth_date": p.birth_date.isoformat() if p.birth_date else None,
        "height": p.height,
        "weight": p.weight,
        "photo_url": p.photo_url,
        "team_id": p.team_id,
        "team_name": team_name,
        "overall_rating": p.overall_rating,
    }


@router.get("/{player_id}/stats")
def get_player_stats(
    player_id: int,
    season: str | None = Query(None, description="赛季名称，默认最新赛季"),
    db: Session = Depends(get_db),
):
    """获取球员赛季统计"""
    season_obj = _resolve_season(db, season)
    stat = _get_stat(player_id, season_obj, db)
    return {"player_id": player_id, "season": season_obj.name if season_obj else None, "stats": stat}


@router.get("/{player_id}/radar")
def get_player_radar(
    player_id: int,
    position: str | None = Query(None, description="指定位置覆盖球员自身位置"),
    season: str | None = Query(None, description="赛季名称，默认最新赛季"),
    db: Session = Depends(get_db),
):
    """获取球员能力雷达（按位置返回不同维度）"""
    p = db.query(Player).filter(Player.id == player_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="球员不存在")
    season_obj = _resolve_season(db, season)
    pos = position or p.position
    return _build_radar_for(p, pos, season_obj)


@router.get("/{player_id}/position-rank")
def get_player_position_rank(
    player_id: int,
    season: str | None = Query(None, description="赛季名称，默认最新赛季"),
    db: Session = Depends(get_db),
):
    """获取球员在其位置的联赛排名"""
    p = db.query(Player).filter(Player.id == player_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="球员不存在")
    season_obj = _resolve_season(db, season)
    return _position_rank(p, season_obj, db)


# ── 辅助函数 ──

def _resolve_season(db: Session, season_name: str | None):
    query = db.query(Season)
    if season_name:
        query = query.filter(Season.name == season_name)
    return query.order_by(Season.id.desc()).first()


def _get_stat(player_id: int, season_obj, db: Session) -> dict | None:
    if not season_obj:
        return None
    ps = (
        db.query(PlayerStat)
        .filter(PlayerStat.player_id == player_id, PlayerStat.season_id == season_obj.id)
        .first()
    )
    if not ps:
        return None
    return {
        "appearances": ps.appearances,
        "goals": ps.goals,
        "assists": ps.assists,
        "yellow_cards": ps.yellow_cards,
        "red_cards": ps.red_cards,
        "minutes_played": ps.minutes_played,
        "shots": ps.shots,
        "shots_on_target": ps.shots_on_target,
        "xg": ps.xg,
        "xa": ps.xa,
        "passes": ps.passes,
        "pass_accuracy": ps.pass_accuracy,
        "tackles": ps.tackles,
        "interceptions": ps.interceptions,
        "rating": ps.rating,
    }


# 按位置的六边图维度配置（对应方案 7.3）
_RADAR_DIMS = {
    "GK": [("gk_score", "扑救反应"), ("org_score", "出球能力"), ("def_score", "防守站位"),
           ("phy_score", "身体/弹跳"), ("dis_score", "纪律"), ("overall_rating", "稳定性")],
    "DF": [("def_score", "防守抢断"), ("phy_score", "空中对抗"), ("org_score", "出球组织"),
           ("atk_score", "进攻插上"), ("dis_score", "纪律"), ("overall_rating", "综合")],
    "MF": [("org_score", "传球组织"), ("def_score", "防守拦截"), ("atk_score", "进攻创造力"),
           ("phy_score", "跑动覆盖"), ("dis_score", "纪律"), ("overall_rating", "关键传球")],
    "FW": [("atk_score", "射门终结"), ("org_score", "跑位穿插"), ("dis_score", "关键传球"),
           ("phy_score", "身体对抗"), ("overall_rating", "进攻效率"), ("def_score", "纪律")],
}


def _build_radar(player: Player, season_obj, db: Session) -> dict:
    """按球员自身位置构建六边图数据"""
    return _build_radar_for(player, player.position, season_obj)


def _build_radar_for(player: Player, position: str | None, season_obj) -> dict:
    """构建指定位置的六边图数据"""
    pos = position or "MF"
    dims = _RADAR_DIMS.get(pos, _RADAR_DIMS["MF"])
    return {
        "player_id": player.id,
        "name": player.name,
        "position": pos,
        "season": season_obj.name if season_obj else None,
        "dimensions": [label for _, label in dims],
        "values": [getattr(player, attr, 0) for attr, _ in dims],
        "overall": player.overall_rating or 0,
    }


def _position_rank(player: Player, season_obj, db: Session) -> dict:
    """球员在其位置的联赛排名"""
    if not player.position:
        return {"position": None, "rank": None, "total": 0}
    peers = (
        db.query(Player)
        .filter(Player.position == player.position)
        .order_by(Player.overall_rating.desc())
        .all()
    )
    rank = None
    for i, p in enumerate(peers, 1):
        if p.id == player.id:
            rank = i
            break
    return {"position": player.position, "rank": rank, "total": len(peers)}


def _key_events(player_id: int, db: Session, limit: int = 10) -> list:
    """球员近期关键事件（进球/助攻）"""
    events = (
        db.query(MatchEvent)
        .filter(MatchEvent.player_id == player_id, MatchEvent.event_type == "goal")
        .order_by(MatchEvent.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "event_type": e.event_type,
            "minute": e.minute,
            "detail": e.detail,
        }
        for e in events
    ]
