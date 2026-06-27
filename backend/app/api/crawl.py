"""爬虫触发接口 — 手动触发指定数据源的采集任务"""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.data_source import DataSource
from app.models.crawl_log import CrawlLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/crawl", tags=["爬虫"])


class CrawlTrigger(BaseModel):
    """触发采集的请求体"""
    source: str = "dongqiudi"  # 数据源编码，如 dongqiudi/fbref/api_football
    target: str = "schedule"   # 采集目标，如 schedule/standings/players
    league_id: int | None = None  # 可选，指定联赛


@router.post("/trigger")
def trigger_crawl(body: CrawlTrigger, db: Session = Depends(get_db)):
    """手动触发采集任务

    body: {"source": "dongqiudi", "target": "schedule", "league_id": 39}
    """
    # 校验数据源是否存在且启用
    source = db.query(DataSource).filter(DataSource.source_code == body.source).first()
    if not source:
        raise HTTPException(status_code=404, detail=f"数据源不存在: {body.source}")
    if not source.enabled:
        raise HTTPException(status_code=400, detail=f"数据源已禁用: {body.source}")

    # 记录抓取日志（运行中）
    log = CrawlLog(
        source_id=source.id,
        target=body.target,
        start_time=time.strftime("%Y-%m-%d %H:%M:%S"),
        status="running",
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    # 异步触发采集（这里仅创建任务记录，实际采集由调度器/后台执行）
    # 完整实现需结合具体爬虫模块，当前返回任务 ID 供前端轮询状态
    logger.info("触发采集: source=%s target=%s log_id=%d", body.source, body.target, log.id)

    return {
        "message": "采集任务已创建",
        "log_id": log.id,
        "source": body.source,
        "target": body.target,
        "status": "running",
        "note": "可通过 GET /api/v1/data-sources/logs 查询执行状态",
    }
