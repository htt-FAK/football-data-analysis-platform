"""数据源监控接口 — 健康状态、抓取日志"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.data_source import DataSource
from app.models.crawl_log import CrawlLog

router = APIRouter(prefix="/data-sources", tags=["数据源"])


@router.get("/health")
def get_sources_health(db: Session = Depends(get_db)):
    """获取各数据源健康状态（供监控看板展示）"""
    sources = db.query(DataSource).order_by(DataSource.priority.asc()).all()

    result = []
    for s in sources:
        # 取最近一次抓取记录
        last_log = (
            db.query(CrawlLog)
            .filter(CrawlLog.source_id == s.id)
            .order_by(CrawlLog.id.desc())
            .first()
        )
        # 计算健康度：最近成功=健康，连续失败=告警，长期未抓取=离线
        health = _compute_health(s, last_log)
        result.append({
            "id": s.id,
            "source_code": s.source_code,
            "name": s.name,
            "type": s.type,
            "priority": s.priority,
            "enabled": s.enabled,
            "status": s.status,
            "error_count": s.error_count,
            "last_crawl_at": s.last_crawl_at.isoformat() if s.last_crawl_at else None,
            "health": health,
            "last_log": {
                "target": last_log.target if last_log else None,
                "fetched": last_log.fetched if last_log else 0,
                "updated": last_log.updated if last_log else 0,
                "failed": last_log.failed if last_log else 0,
                "cost_ms": last_log.cost_ms if last_log else 0,
                "status": last_log.status if last_log else None,
            } if last_log else None,
        })
    return result


@router.get("/logs")
def get_crawl_logs(
    source_id: int | None = Query(None, description="按数据源筛选"),
    limit: int = Query(50, description="返回条数", le=500),
    db: Session = Depends(get_db),
):
    """获取近期抓取日志（可选 ?source_id=, ?limit= 参数）"""
    query = db.query(CrawlLog)
    if source_id:
        query = query.filter(CrawlLog.source_id == source_id)
    logs = query.order_by(CrawlLog.id.desc()).limit(limit).all()

    # 预加载数据源名称
    source_ids = {l.source_id for l in logs}
    sources_map = (
        {s.id: (s.source_code, s.name) for s in db.query(DataSource).filter(DataSource.id.in_(source_ids)).all()}
        if source_ids else {}
    )

    return [
        {
            "id": l.id,
            "source_id": l.source_id,
            "source_code": sources_map.get(l.source_id, (None, None))[0],
            "source_name": sources_map.get(l.source_id, (None, None))[1],
            "target": l.target,
            "start_time": l.start_time.isoformat() if l.start_time else None,
            "end_time": l.end_time.isoformat() if l.end_time else None,
            "fetched": l.fetched,
            "updated": l.updated,
            "failed": l.failed,
            "cost_ms": l.cost_ms,
            "status": l.status,
            "error_msg": l.error_msg,
        }
        for l in logs
    ]


def _compute_health(source: DataSource, last_log: CrawlLog | None) -> str:
    """计算数据源健康度：healthy / warning / offline"""
    if not source.enabled:
        return "disabled"
    if source.error_count >= 5:
        return "error"
    if last_log and last_log.status == "failed":
        return "warning"
    if last_log and last_log.status == "success":
        return "healthy"
    return "idle"
