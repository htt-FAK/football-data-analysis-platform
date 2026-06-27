from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import get_db

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/")
def list_matches(
    league_id: int | None = Query(None, description="按联赛筛选"),
    matchday: int | None = Query(None, description="按轮次筛选"),
    status: str | None = Query(None, description="按状态筛选"),
    date: str | None = Query(None, description="按日期筛选"),
    db=Depends(get_db),
):
    """获取比赛列表（可选 ?league_id=, ?matchday=, ?status=, ?date= 参数）"""
    # TODO: 查询比赛列表，支持按联赛、轮次、状态、日期筛选
    return []


@router.get("/{match_id}")
def get_match(match_id: int, db=Depends(get_db)):
    """获取比赛详情"""
    # TODO: 查询指定比赛的基本信息
    return {}


@router.get("/{match_id}/events")
def get_match_events(match_id: int, db=Depends(get_db)):
    """获取比赛事件"""
    # TODO: 查询指定比赛的事件列表
    return []


@router.get("/{match_id}/xg-timeline")
def get_match_xg_timeline(match_id: int, db=Depends(get_db)):
    """获取 xG 时间线"""
    # TODO: 查询指定比赛的 xG 时间线数据
    return []


@router.get("/{match_id}/shots")
def get_match_shots(match_id: int, db=Depends(get_db)):
    """获取比赛射门数据"""
    # TODO: 查询指定比赛的射门数据
    return []


@router.get("/{match_id}/report")
def get_match_report(match_id: int, db=Depends(get_db)):
    """获取比赛复盘报告"""
    # TODO: 查询指定比赛的复盘报告
    return {}
