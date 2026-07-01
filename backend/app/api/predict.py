"""AI prediction API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import DEEPSEEK_API_KEY, ENABLE_AI_PREDICTION, STEPFUN_API_KEY
from app.database import get_db
from app.models.match import Match
from app.services.match_service import refresh_worldcup_matches
from app.services.prediction_service import (
    get_prediction,
    list_predicted_matches,
    resolve_effective_match_status,
    trigger_prediction_now_async,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["prediction"])


@router.get("/status")
def prediction_status():
    """Return prediction module readiness without exposing secrets."""
    return {
        "enabled": ENABLE_AI_PREDICTION,
        "stepfun_configured": bool(STEPFUN_API_KEY),
        "deepseek_configured": bool(DEEPSEEK_API_KEY),
        "ready": bool(ENABLE_AI_PREDICTION and STEPFUN_API_KEY and DEEPSEEK_API_KEY),
    }


@router.get("/matches/{match_id}")
def get_match_prediction(match_id: int, db: Session = Depends(get_db)):
    """Return one match prediction with rounds and sources."""
    result = get_prediction(db, match_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"比赛 {match_id} 暂无预测记录")
    return result


@router.get("/matches")
def list_matches_with_prediction(
    limit: int = Query(50, ge=1, le=200, description="Maximum number of rows to return"),
    db: Session = Depends(get_db),
):
    """List matches that already have prediction records."""
    return {"matches": list_predicted_matches(db, limit=limit)}


@router.post("/matches/{match_id}/trigger")
async def trigger_match_prediction(
    match_id: int,
    background_tasks: BackgroundTasks,
    sync: bool = Query(False, description="True waits for the result; false queues a background task"),
    db: Session = Depends(get_db),
):
    """Trigger a prediction job for one match."""
    if not ENABLE_AI_PREDICTION:
        raise HTTPException(status_code=503, detail="AI 预测功能当前未启用")
    if not (STEPFUN_API_KEY and DEEPSEEK_API_KEY):
        raise HTTPException(status_code=503, detail="AI 预测所需的接口密钥尚未配置")

    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail=f"未找到比赛 {match_id}")

    refresh_worldcup_matches(db, [match])
    match = db.get(Match, match_id)
    if resolve_effective_match_status(match) == "finished":
        existing = get_prediction(db, match_id)
        if existing:
            existing["message"] = "比赛已经结束，仅展示历史预测结果。"
            return existing
        return {
            "match_id": match_id,
            "status": "rejected",
            "error": "比赛已经结束，不支持重新预测。",
        }

    if sync:
        return await trigger_prediction_now_async(db, match_id)

    from app.database import SessionLocal
    from app.services.prediction_service import trigger_prediction_now

    def _run():
        task_db = SessionLocal()
        try:
            trigger_prediction_now(task_db, match_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("background prediction task failed for match_id=%s: %s", match_id, exc)
        finally:
            task_db.close()

    background_tasks.add_task(_run)
    return {
        "match_id": match_id,
        "status": "accepted",
        "message": "预测任务已提交，请稍后轮询结果。",
    }
