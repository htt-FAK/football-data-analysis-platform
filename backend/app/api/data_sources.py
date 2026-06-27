from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import get_db

router = APIRouter(prefix="/data-sources", tags=["data_sources"])


@router.get("/health")
def get_sources_health(db=Depends(get_db)):
    """获取各数据源健康状态"""
    # TODO: 查询各数据源的健康状态
    return []


@router.get("/logs")
def get_crawl_logs(
    source_id: int | None = Query(None, description="按数据源筛选"),
    limit: int | None = Query(None, description="返回条数"),
    db=Depends(get_db),
):
    """获取近期抓取日志（可选 ?source_id=, ?limit= 参数）"""
    # TODO: 查询近期的抓取日志，支持按数据源筛选和限制条数
    return []
