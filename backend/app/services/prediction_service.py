"""Prediction service helpers for query, trigger, and scheduler flows."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.analysis.prediction_accuracy import assess_accuracy, summarize_accuracy
from app.config import AI_PREDICTION_HOURS_BEFORE, AI_PREDICTION_WINDOW_TOLERANCE_HOURS
from app.models.match import Match
from app.models.match_prediction import MatchPrediction
from app.services.match_service import (
    get_worldcup_reference_now,
    refresh_worldcup_matches,
    resolve_effective_match_status as resolve_worldcup_match_status,
)
from app.services.text_repair import repair_payload

logger = logging.getLogger(__name__)
PREDICTION_CLOSE_BUFFER_HOURS = 4
PREDICTION_PLACEHOLDER_SNIPPETS = (
    "结构化结论损坏",
    "等待下一轮或裁决轮",
    "未获得完整 json 结论",
    "未获得完整 json",
    "已提取 mermaid 导图",
    "裁决轮失败",
    "回退到最近一轮",
)


def resolve_effective_match_status(match: Match | None) -> str | None:
    """Return a refreshed, user-facing match status for prediction views."""
    return resolve_worldcup_match_status(match)


def _build_accuracy_payload(pred: MatchPrediction | None, match: Match | None) -> dict | None:
    """根据真实比分判定预测命中等级；比赛未结束或无预测比分时返回 None。"""
    if not pred or not match:
        return None
    effective_status = resolve_worldcup_match_status(match)
    # 只有已结束的比赛才结算命中（live/scheduled 不结算）
    if effective_status != "finished":
        return None
    return assess_accuracy(
        pred.predicted_home_score,
        pred.predicted_away_score,
        match.home_score,
        match.away_score,
    )


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _looks_like_placeholder_text(value: object) -> bool:
    text = _normalize_text(value)
    if not text:
        return True

    lowered = text.lower()
    return any(snippet in lowered for snippet in PREDICTION_PLACEHOLDER_SNIPPETS)


def _build_prediction_reason_fallback(payload: dict) -> list[str]:
    reasons: list[str] = []
    home_score = payload.get("predicted_home_score")
    away_score = payload.get("predicted_away_score")
    if home_score is not None and away_score is not None:
        reasons.append(f"历史记录仍保留了预测比分 {home_score}:{away_score}。")

    home_win_prob = payload.get("home_win_prob")
    draw_prob = payload.get("draw_prob")
    away_win_prob = payload.get("away_win_prob")
    if home_win_prob is not None and draw_prob is not None and away_win_prob is not None:
        reasons.append("历史记录仍保留了胜平负概率，可结合比分一起参考。")

    if _normalize_text(payload.get("mermaid_mindmap")):
        reasons.append("已保留思维导图，可继续查看当时的判断路径。")

    reasons.append("该场历史预测的部分长文本未完整落库，当前优先展示仍可信的结构化结果。")
    return reasons


def _sanitize_rounds(rounds: object) -> list[dict]:
    if not isinstance(rounds, list):
        return []

    sanitized: list[dict] = []
    for item in rounds:
        if not isinstance(item, dict):
            continue

        round_item = dict(item)
        round_item = repair_payload(round_item)

        conclusion = round_item.get("conclusion")
        if isinstance(conclusion, dict):
            clean_conclusion = dict(conclusion)
            if _looks_like_placeholder_text(clean_conclusion.get("conservative_verdict")):
                clean_conclusion["conservative_verdict"] = "该轮保守结论未完整保存。"
            if _looks_like_placeholder_text(clean_conclusion.get("aggressive_verdict")):
                clean_conclusion["aggressive_verdict"] = "该轮激进结论未完整保存。"

            reasons = clean_conclusion.get("key_reasons")
            if isinstance(reasons, list):
                clean_reasons = [
                    _normalize_text(reason)
                    for reason in reasons
                    if _normalize_text(reason) and not _looks_like_placeholder_text(reason)
                ]
                if clean_reasons:
                    clean_conclusion["key_reasons"] = clean_reasons[:6]
            round_item["conclusion"] = clean_conclusion

        if _looks_like_placeholder_text(round_item.get("error")):
            round_item["error"] = "该轮结构化解析未完整成功，当前保留了可用内容。"

        current_status = _normalize_text(round_item.get("status")).lower()
        if current_status == "completed":
            has_placeholder_conclusion = isinstance(conclusion, dict) and (
                _looks_like_placeholder_text(conclusion.get("conservative_verdict"))
                or _looks_like_placeholder_text(conclusion.get("aggressive_verdict"))
            )
            if has_placeholder_conclusion:
                round_item["status"] = "partial"

        sanitized.append(round_item)

    return sanitized


def _sanitize_prediction_payload(payload: dict | None, *, preserve_missing_fields: bool = False) -> dict | None:
    if not payload:
        return payload

    cleaned = repair_payload(payload)
    if not isinstance(cleaned, dict):
        return payload

    if "conservative_verdict" in cleaned and _looks_like_placeholder_text(cleaned.get("conservative_verdict")):
        cleaned["conservative_verdict"] = "历史预测结论保留不完整，请优先参考比分概率和关键依据。"

    if "aggressive_verdict" in cleaned and _looks_like_placeholder_text(cleaned.get("aggressive_verdict")):
        cleaned["aggressive_verdict"] = "该场历史预测的激进结论未完整保存。"

    key_reasons = cleaned.get("key_reasons")
    if isinstance(key_reasons, list):
        filtered_reasons = [
            _normalize_text(reason)
            for reason in key_reasons
            if _normalize_text(reason) and not _looks_like_placeholder_text(reason)
        ]
    else:
        filtered_reasons = []

    if not filtered_reasons and (not preserve_missing_fields or "key_reasons" in cleaned):
        filtered_reasons = _build_prediction_reason_fallback(cleaned)
    if "key_reasons" in cleaned or filtered_reasons:
        cleaned["key_reasons"] = filtered_reasons[:6]

    if "final_summary" in cleaned and _looks_like_placeholder_text(cleaned.get("final_summary")):
        cleaned["final_summary"] = "历史预测文本保留不完整，已优先展示仍可参考的结构化结果。"

    if "error_msg" in cleaned and _looks_like_placeholder_text(cleaned.get("error_msg")):
        cleaned["error_msg"] = "该场历史预测曾出现结构化解析问题，但可用结果已保留。"

    if "rounds" in cleaned:
        cleaned["rounds"] = _sanitize_rounds(cleaned.get("rounds"))
    return cleaned


def serialize_prediction(pred: MatchPrediction | None, db: Session | None = None) -> dict | None:
    """Serialize a MatchPrediction row for API responses."""
    if not pred:
        return None

    match = db.get(Match, pred.match_id) if db else None
    if db and match:
        refresh_worldcup_matches(db, [match])
        match = db.get(Match, pred.match_id)
    home_team = match.home_team if match else None
    away_team = match.away_team if match else None

    payload = {
        "id": pred.id,
        "match_id": pred.match_id,
        "status": pred.status,
        "home_team": {
            "id": home_team.id if home_team else None,
            "name": home_team.name if home_team else None,
            "country": home_team.country if home_team else None,
        },
        "away_team": {
            "id": away_team.id if away_team else None,
            "name": away_team.name if away_team else None,
            "country": away_team.country if away_team else None,
        },
        "kickoff": match.match_date.isoformat() if match and match.match_date else None,
        "stage": match.stage if match else None,
        "group": match.group_name if match else None,
        "venue": match.venue if match else None,
        "match_status": resolve_effective_match_status(match),
        "home_win_prob": pred.home_win_prob,
        "draw_prob": pred.draw_prob,
        "away_win_prob": pred.away_win_prob,
        "predicted_home_score": pred.predicted_home_score,
        "predicted_away_score": pred.predicted_away_score,
        "real_home_score": match.home_score if match else None,
        "real_away_score": match.away_score if match else None,
        "accuracy": _build_accuracy_payload(pred, match),
        "conservative_verdict": pred.conservative_verdict,
        "aggressive_verdict": pred.aggressive_verdict,
        "key_reasons": pred.key_reasons or [],
        "confidence": pred.confidence,
        "mermaid_mindmap": pred.mermaid_mindmap,
        "rounds": pred.rounds or [],
        "final_summary": pred.final_summary,
        "total_tokens": pred.total_tokens,
        "total_cost_ms": pred.total_cost_ms,
        "error_msg": pred.error_msg,
        "generated_at": pred.generated_at.isoformat() if pred.generated_at else None,
    }
    return _sanitize_prediction_payload(payload)


def get_prediction(db: Session, match_id: int) -> dict | None:
    pred = db.query(MatchPrediction).filter(MatchPrediction.match_id == match_id).first()
    return serialize_prediction(pred, db)


def list_predicted_matches(db: Session, limit: int = 50) -> list[dict]:
    preds = (
        db.query(MatchPrediction)
        .order_by(
            case((MatchPrediction.generated_at.is_(None), 1), else_=0),
            MatchPrediction.generated_at.desc(),
        )
        .limit(limit)
        .all()
    )

    match_ids = [pred.match_id for pred in preds]
    matches = db.query(Match).filter(Match.id.in_(match_ids or [-1])).all()
    refresh_worldcup_matches(db, matches)
    match_map = {match.id: match for match in db.query(Match).filter(Match.id.in_(match_ids or [-1])).all()}

    result: list[dict] = []
    for pred in preds:
        match = match_map.get(pred.match_id)
        full_payload = serialize_prediction(pred, db) or {}
        row = {
            "match_id": pred.match_id,
            "status": pred.status,
            "predicted_home_score": pred.predicted_home_score,
            "predicted_away_score": pred.predicted_away_score,
            "confidence": pred.confidence,
            "home_team_name": match.home_team.name if match and match.home_team else None,
            "away_team_name": match.away_team.name if match and match.away_team else None,
            "kickoff": match.match_date.isoformat() if match and match.match_date else None,
            "stage": match.stage if match else None,
            "match_status": resolve_effective_match_status(match),
            "real_home_score": match.home_score if match else None,
            "real_away_score": match.away_score if match else None,
            "accuracy": summarize_accuracy(full_payload.get("accuracy")) if isinstance(full_payload.get("accuracy"), dict) else None,
            "generated_at": pred.generated_at.isoformat() if pred.generated_at else None,
            "conservative_verdict": full_payload.get("conservative_verdict"),
        }
        sanitized = _sanitize_prediction_payload(row, preserve_missing_fields=True) or row
        result.append(sanitized)
    return result


def get_matches_due_for_prediction(
    db: Session, hours_before: float | None = None, tolerance: float | None = None
) -> list[Match]:
    hours_before = hours_before if hours_before is not None else AI_PREDICTION_HOURS_BEFORE
    tolerance = tolerance if tolerance is not None else AI_PREDICTION_WINDOW_TOLERANCE_HOURS
    now = get_worldcup_reference_now()
    window_start = now + timedelta(hours=hours_before - tolerance)
    window_end = now + timedelta(hours=hours_before + tolerance)

    return (
        db.query(Match)
        .filter(
            Match.match_date.isnot(None),
            Match.match_date >= window_start,
            Match.match_date <= window_end,
            Match.status == "scheduled",
            Match.home_team_id.isnot(None),
            Match.away_team_id.isnot(None),
            ~Match.id.in_(select(MatchPrediction.match_id).where(MatchPrediction.status == "completed")),
        )
        .order_by(Match.match_date.asc())
        .all()
    )


def trigger_prediction_now(db: Session, match_id: int) -> dict:
    """Trigger one prediction immediately and return the serialized result."""
    from app.prediction.orchestrator import PredictionOrchestrator

    match = db.get(Match, match_id)
    if not match:
        return {"match_id": match_id, "status": "failed", "error": "未找到该比赛"}

    refresh_worldcup_matches(db, [match])
    match = db.get(Match, match_id)
    effective_status = resolve_effective_match_status(match)
    if effective_status == "finished":
        existing = db.query(MatchPrediction).filter(MatchPrediction.match_id == match_id).first()
        if existing:
            payload = serialize_prediction(existing, db) or {}
            payload["message"] = "比赛已结束，仅展示历史预测结果"
            return payload
        return {
            "match_id": match_id,
            "status": "rejected",
            "error": "比赛已结束，不支持重新预测",
        }

    if not match.home_team_id or not match.away_team_id:
        return {"match_id": match_id, "status": "failed", "error": "比赛队伍信息不完整"}

    orchestrator = PredictionOrchestrator()
    pred = orchestrator.run_full_prediction(db, match_id)
    return serialize_prediction(pred, db) or {
        "match_id": match_id,
        "status": "failed",
        "error": "预测执行失败",
    }


def scan_and_predict(db: Session) -> dict:
    due = get_matches_due_for_prediction(db)
    if not due:
        return {"scanned": 0, "predicted": 0, "failed": 0, "details": []}

    from app.prediction.orchestrator import PredictionOrchestrator

    orchestrator = PredictionOrchestrator()
    predicted = 0
    failed = 0
    details = []
    for match in due:
        try:
            pred = orchestrator.run_full_prediction(db, match.id)
            ok = pred.status == "completed"
            if ok:
                predicted += 1
            else:
                failed += 1
            details.append({"match_id": match.id, "status": pred.status, "error": pred.error_msg})
        except Exception as exc:  # noqa: BLE001
            logger.exception("prediction failed for match %s: %s", match.id, exc)
            failed += 1
            details.append({"match_id": match.id, "status": "error", "error": str(exc)})

    return {"scanned": len(due), "predicted": predicted, "failed": failed, "details": details}


async def scan_and_predict_async(db: Session) -> dict:
    return await asyncio.to_thread(scan_and_predict, db)


async def trigger_prediction_now_async(db: Session, match_id: int) -> dict:
    return await asyncio.to_thread(trigger_prediction_now, db, match_id)
