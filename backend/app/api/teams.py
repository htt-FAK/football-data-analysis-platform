"""球队接口 — 列表、详情、统计、攻防雷达、射门热图"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.team import Team
from app.models.team_stat import TeamStat
from app.models.shot import Shot
from app.models.season import Season

router = APIRouter(prefix="/teams", tags=["球队"])


@router.get("/")
def list_teams(
    league_id: int | None = Query(None, description="按联赛筛选"),
    name: str | None = Query(None, description="按名称模糊搜索"),
    db: Session = Depends(get_db),
):
    """获取球队列表（可选 ?league_id=, ?name= 参数）"""
    query = db.query(Team)
    if name:
        query = query.filter(Team.name.like(f"%{name}%"))
    teams = query.order_by(Team.name).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "full_name": t.full_name,
            "country": t.country,
            "logo_url": t.logo_url,
            "stadium": t.stadium,
            "coach": t.coach,
        }
        for t in teams
    ]


@router.get("/{team_id}")
def get_team(team_id: int, db: Session = Depends(get_db)):
    """获取球队详情"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="球队不存在")
    return {
        "id": team.id,
        "name": team.name,
        "full_name": team.full_name,
        "country": team.country,
        "logo_url": team.logo_url,
        "stadium": team.stadium,
        "coach": team.coach,
        "founded_year": team.founded_year,
    }


@router.get("/{team_id}/stats")
def get_team_stats(
    team_id: int,
    season: str | None = Query(None, description="赛季名称，默认最新赛季"),
    db: Session = Depends(get_db),
):
    """获取球队赛季统计"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="球队不存在")

    season_obj = _latest_season(db)
    stat = (
        db.query(TeamStat)
        .filter(TeamStat.team_id == team_id, TeamStat.season_id == season_obj.id if season_obj else False)
        .first()
    ) if season_obj else None

    if not stat:
        return {"team_id": team_id, "season": season_obj.name if season_obj else None, "stats": None}

    return {
        "team_id": team_id,
        "team_name": team.name,
        "season": season_obj.name,
        "stats": {
            "goals_for": stat.goals_for,
            "goals_against": stat.goals_against,
            "xg_for": stat.xg_for,
            "xg_against": stat.xg_against,
            "possession": stat.possession,
            "shots_total": stat.shots_total,
            "shots_on_target": stat.shots_on_target,
            "passes_total": stat.passes_total,
            "pass_accuracy": stat.pass_accuracy,
            "corners": stat.corners,
            "fouls": stat.fouls,
            "attack_rating": stat.attack_rating,
            "defense_rating": stat.defense_rating,
            "overall_rating": stat.overall_rating,
        },
    }


@router.get("/{team_id}/radar")
def get_team_radar(
    team_id: int,
    season: str | None = Query(None, description="赛季名称，默认最新赛季"),
    db: Session = Depends(get_db),
):
    """获取球队攻防雷达数据"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="球队不存在")

    season_obj = _latest_season(db)
    stat = (
        db.query(TeamStat)
        .filter(TeamStat.team_id == team_id, TeamStat.season_id == season_obj.id if season_obj else False)
        .first()
    ) if season_obj else None

    if not stat:
        raise HTTPException(status_code=404, detail="无该球队赛季统计数据")

    # 雷达图维度（归一化到 0-100）
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
            min((stat.shots_total or 0) / 25 * 100, 100),  # 射门归一化，基准 25 次
            stat.overall_rating or 0,
        ],
    }


@router.get("/{team_id}/shots")
def get_team_shots(
    team_id: int,
    limit: int = Query(500, description="最多返回条数"),
    db: Session = Depends(get_db),
):
    """获取球队射门数据（用于热图，按坐标返回）"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="球队不存在")

    shots = (
        db.query(Shot)
        .filter(Shot.team_id == team_id)
        .order_by(Shot.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "team_id": team_id,
        "team_name": team.name,
        "total": len(shots),
        "shots": [
            {
                "x": s.x_coord,
                "y": s.y_coord,
                "result": s.result,
                "shot_type": s.shot_type,
                "xg": s.xg,
                "minute": s.minute,
            }
            for s in shots
        ],
    }


def _latest_season(db: Session):
    """取最新的赛季记录（全局，后续可按联赛筛选）"""
    return db.query(Season).order_by(Season.id.desc()).first()
