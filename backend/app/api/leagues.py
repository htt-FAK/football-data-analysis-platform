from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import get_db

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get("/")
def list_leagues(
    country: str | None = Query(None, description="按国家筛选"),
    db=Depends(get_db),
):
    """获取联赛列表（可选 ?country= 参数）"""
    # TODO: 查询联赛列表，支持按国家筛选
    return []


@router.get("/{league_id}/standings")
def get_standings(league_id: int, db=Depends(get_db)):
    """获取积分榜"""
    # TODO: 查询指定联赛的积分榜
    return {}


@router.get("/{league_id}/schedule")
def get_schedule(
    league_id: int,
    matchday: int | None = Query(None, description="按轮次筛选"),
    db=Depends(get_db),
):
    """获取赛程（可选 ?matchday= 参数）"""
    # TODO: 查询指定联赛的赛程，支持按轮次筛选
    return []


@router.get("/{league_id}/trends")
def get_trends(league_id: int, db=Depends(get_db)):
    """获取积分趋势"""
    # TODO: 查询指定联赛的积分变化趋势
    return []
