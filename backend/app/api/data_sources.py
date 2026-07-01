"""Data source monitoring endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.data_source_bootstrap import ensure_builtin_data_sources
from app.services.data_source_service import DataSourceService

router = APIRouter(tags=["data-sources"])
data_source_service = DataSourceService()


@router.get("/health")
def get_sources_health(db: Session = Depends(get_db)):
    """Return health, latest logs, and task strategy for every source."""
    ensure_builtin_data_sources(db)
    return data_source_service.get_health_status(db)


@router.get("/logs")
def get_crawl_logs(
    source_id: int | None = Query(None, description="Filter by source ID"),
    limit: int = Query(50, description="Maximum rows", le=500),
    db: Session = Depends(get_db),
):
    """Return recent crawl logs."""
    return data_source_service.get_crawl_logs(db, source_id=source_id, limit=limit)
