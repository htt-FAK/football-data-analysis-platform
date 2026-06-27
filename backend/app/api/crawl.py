from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import get_db

router = APIRouter(prefix="/crawl", tags=["crawl"])


@router.post("/trigger")
def trigger_crawl(body: dict, db=Depends(get_db)):
    """手动触发采集任务（body: {source: "dongqiudi", target: "schedule"}）"""
    # TODO: 解析 body 中的 source 与 target，触发对应的采集任务
    return {}
