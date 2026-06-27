from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import get_db

router = APIRouter(prefix="/players", tags=["players"])


@router.get("/")
def list_players(
    team_id: int | None = Query(None, description="按球队筛选"),
    position: str | None = Query(None, description="按位置筛选"),
    db=Depends(get_db),
):
    """获取球员列表（可选 ?team_id=, ?position= 参数）"""
    # TODO: 查询球员列表，支持按球队和位置筛选
    return []


@router.get("/top-scorers")
def get_top_scorers(
    limit: int | None = Query(None, description="返回条数"),
    db=Depends(get_db),
):
    """获取射手榜（可选 ?limit= 参数）"""
    # TODO: 查询射手榜，支持限制返回条数
    return []


@router.get("/compare")
def compare_players(
    player_a: int = Query(..., description="球员 A 的 ID"),
    player_b: int = Query(..., description="球员 B 的 ID"),
    db=Depends(get_db),
):
    """球员对比（?player_a=&player_b=）"""
    # TODO: 查询并对比两名球员的数据
    return {}


@router.get("/position-stats")
def get_position_stats(
    position: str = Query(..., description="位置，如 FW"),
    db=Depends(get_db),
):
    """同位置球员分布（?position=FW）"""
    # TODO: 查询指定位置球员的分布统计
    return {}


@router.get("/{player_id}")
def get_player(player_id: int, db=Depends(get_db)):
    """获取球员详情"""
    # TODO: 查询指定球员的基本信息
    return {}


@router.get("/{player_id}/stats")
def get_player_stats(player_id: int, db=Depends(get_db)):
    """获取球员统计"""
    # TODO: 查询指定球员的统计数据
    return {}


@router.get("/{player_id}/radar")
def get_player_radar(
    player_id: int,
    position: str | None = Query(None, description="按位置筛选雷达维度"),
    db=Depends(get_db),
):
    """获取球员能力雷达（可选 ?position= 参数）"""
    # TODO: 查询指定球员的能力雷达数据
    return {}


@router.get("/{player_id}/position-rank")
def get_player_position_rank(player_id: int, db=Depends(get_db)):
    """获取位置排名"""
    # TODO: 查询指定球员在其位置上的排名
    return {}
