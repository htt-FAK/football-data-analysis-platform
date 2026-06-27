from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import get_db

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/")
def list_teams(
    league_id: int | None = Query(None, description="按联赛筛选"),
    db=Depends(get_db),
):
    """获取球队列表（可选 ?league_id= 参数）"""
    # TODO: 查询球队列表，支持按联赛筛选
    return []


@router.get("/{team_id}")
def get_team(team_id: int, db=Depends(get_db)):
    """获取球队详情"""
    # TODO: 查询指定球队的基本信息
    return {}


@router.get("/{team_id}/stats")
def get_team_stats(team_id: int, db=Depends(get_db)):
    """获取球队统计"""
    # TODO: 查询指定球队的统计数据
    return {}


@router.get("/{team_id}/radar")
def get_team_radar(team_id: int, db=Depends(get_db)):
    """获取攻防雷达数据"""
    # TODO: 查询指定球队的攻防雷达数据
    return {}


@router.get("/{team_id}/shots")
def get_team_shots(team_id: int, db=Depends(get_db)):
    """获取射门热图数据"""
    # TODO: 查询指定球队的射门热图数据
    return []
