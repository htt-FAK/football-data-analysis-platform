"""Prediction orchestrator for multi-round AI match analysis."""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlparse
from typing import Any

from sqlalchemy.orm import Session

from app.config import ENABLE_VISION_INTEL
from app.models.match_prediction import MatchPrediction
from app.prediction.context_builder import build_match_context
from app.prediction.llm_client import (
    DeepSeekClient,
    LLMError,
    LLMResponse,
    StepFunClient,
    _candidate_json_texts,
    _cleanup_json_candidate,
    _close_json_candidate,
    _message_text,
    extract_mermaid_block,
)
from app.prediction.prompts import (
    SKILL_SYSTEM_PROMPT,
    build_arbiter_prompt,
    build_context_block,
    build_contextual_prompt,
    build_reasoning_prompt,
    build_tactical_prompt,
)
from app.prediction.media import (
    analyze_images,
    build_vision_block,
    extract_image_urls,
)
from app.prediction.web_search import SearchResult, build_intel_block, is_available as web_search_available, search_safe

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Firecrawl 搜索进程内缓存 (B3 优化)
# ---------------------------------------------------------------------------
_search_cache: dict = {}
_CACHE_TTL_SECONDS = 300  # 5 分钟 TTL


def search_safe_cached(query: str, **kwargs) -> list:
    """search_safe 的带缓存版本。同一进程内 5 分钟内的重复查询直接返回缓存。"""
    key = (query, kwargs.get("max_results"), kwargs.get("include_images"))
    now = time.time()
    if key in _search_cache:
        ts, results = _search_cache[key]
        if now - ts < _CACHE_TTL_SECONDS:
            logger.info("search cache HIT: query=%s", query[:60])
            return results
    results = search_safe(query, **kwargs)
    _search_cache[key] = (now, results)
    # 定期清理过期项，防内存泄漏
    if len(_search_cache) > 200:
        cutoff = now - _CACHE_TTL_SECONDS
        expired_keys = [k for k, (ts, _) in _search_cache.items() if ts < cutoff]
        for k in expired_keys:
            del _search_cache[k]
    return results

PLACEHOLDER_PHRASES = {
    "结论待补充",
    "激进结论待补充",
    "待补充",
    "tbd",
    "todo",
    "暂无",
    "无",
}


def _coerce_probability(value: Any, fallback: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(0.0, min(100.0, result))


def _coerce_int(value: Any, fallback: int) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return fallback


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _coerce_reasons(value: Any) -> list[str]:
    if isinstance(value, list):
        result = [_normalize_text(item) for item in value]
        return [item for item in result if item][:8]
    if isinstance(value, str) and value.strip():
        parts = [part.strip(" -") for part in value.splitlines()]
        return [part for part in parts if part][:8]
    return []


def _is_placeholder_text(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return True
    return normalized in PLACEHOLDER_PHRASES


def _assess_search_sources(search_results: list[dict] | None) -> dict[str, Any]:
    results = search_results or []
    count = len(results)
    valid_url_count = 0
    query_echo_count = 0
    unique_domains: set[str] = set()

    for result in results:
        title = _normalize_text(result.get("title"))
        url = _normalize_text(result.get("url"))
        if title.startswith("搜索:") and not url:
            query_echo_count += 1
        if url.startswith("http://") or url.startswith("https://"):
            valid_url_count += 1
            domain = urlparse(url).netloc.lower()
            if domain:
                unique_domains.add(domain)

    score = 0
    if count >= 3:
        score += 1
    if valid_url_count >= 2:
        score += 1
    if len(unique_domains) >= 2:
        score += 1
    if query_echo_count and query_echo_count == count:
        score = 0

    if score >= 3:
        level = "strong"
        penalty = 0
    elif score == 2:
        level = "medium"
        penalty = 5
    elif score == 1:
        level = "weak"
        penalty = 12
    else:
        level = "missing"
        penalty = 20

    return {
        "level": level,
        "score": score,
        "count": count,
        "valid_url_count": valid_url_count,
        "unique_domains": sorted(unique_domains),
        "query_echo_count": query_echo_count,
        "confidence_penalty": penalty,
    }


def _semantic_issues(payload: dict | None) -> list[str]:
    if not payload:
        return ["missing_payload"]

    issues: list[str] = []
    conservative = _normalize_text(payload.get("conservative_verdict"))
    aggressive = _normalize_text(payload.get("aggressive_verdict"))
    key_reasons = _coerce_reasons(payload.get("key_reasons"))

    if _is_placeholder_text(conservative):
        issues.append("missing_conservative_verdict")
    if _is_placeholder_text(aggressive):
        issues.append("missing_aggressive_verdict")
    if len(key_reasons) < 3:
        issues.append("insufficient_key_reasons")
    return issues


def _build_semantic_repair_prompt(resp: LLMResponse, partial: dict, issues: list[str], include_mermaid: bool) -> str:
    schema_tail = ', "mermaid_mindmap": "```mermaid ... ```"' if include_mermaid else ""
    return f"""请修复下面这个比赛预测 JSON。要求：
1. 保留已有可用数值字段，重点补齐 conservative_verdict、aggressive_verdict、key_reasons、thinking。
2. 不能输出占位词，不能输出“无法联网”“模拟搜索”之类的自我暴露语句。
3. key_reasons 至少补齐 3 条，必须具体。
4. 只输出纯 JSON。

当前语义问题: {issues}

已有 JSON:
{partial}

原始 content:
{resp.content[:3000]}

原始 reasoning:
{resp.reasoning[:3000]}

输出 schema:
{{
  "home_win_prob": number,
  "draw_prob": number,
  "away_win_prob": number,
  "predicted_home_score": integer,
  "predicted_away_score": integer,
  "conservative_verdict": "完整结论",
  "aggressive_verdict": "完整结论",
  "confidence": number,
  "key_reasons": ["至少3条具体依据"],
  "thinking": "修复后的完整推理"{schema_tail}
}}
"""


def _normalize_prediction_payload(
    parsed: dict | None,
    resp: LLMResponse | None,
    *,
    include_mermaid: bool = False,
) -> dict | None:
    if not parsed:
        return None

    home_win_prob = _coerce_probability(parsed.get("home_win_prob"), 33.3)
    draw_prob = _coerce_probability(parsed.get("draw_prob"), 33.3)
    away_win_prob = _coerce_probability(parsed.get("away_win_prob"), 33.4)
    total = home_win_prob + draw_prob + away_win_prob
    if total > 0:
        home_win_prob = round(home_win_prob * 100 / total, 1)
        draw_prob = round(draw_prob * 100 / total, 1)
        away_win_prob = round(100 - home_win_prob - draw_prob, 1)

    content_text = resp.content.strip() if resp else ""
    reasoning_text = resp.reasoning.strip() if resp else ""
    thinking = _normalize_text(parsed.get("thinking")) or reasoning_text or content_text

    normalized = {
        "home_win_prob": home_win_prob,
        "draw_prob": draw_prob,
        "away_win_prob": away_win_prob,
        "predicted_home_score": _coerce_int(parsed.get("predicted_home_score"), 1),
        "predicted_away_score": _coerce_int(parsed.get("predicted_away_score"), 1),
        "conservative_verdict": _normalize_text(parsed.get("conservative_verdict")),
        "aggressive_verdict": _normalize_text(parsed.get("aggressive_verdict")),
        "confidence": _coerce_probability(parsed.get("confidence"), 50.0),
        "key_reasons": _coerce_reasons(parsed.get("key_reasons")),
        "thinking": thinking,
    }

    if include_mermaid:
        mermaid = parsed.get("mermaid_mindmap")
        if not isinstance(mermaid, str) or not mermaid.strip():
            mermaid = extract_mermaid_block(content_text) or extract_mermaid_block(reasoning_text)
        normalized["mermaid_mindmap"] = mermaid

    return normalized


def _round_status(round_idx: int, parsed: dict | None, error: str | None, resp: LLMResponse | None, semantic_issues: list[str], source_quality: dict[str, Any] | None) -> str:
    # 视觉轮（round 0）：输出的是分析正文而非 JSON，按内容有无判定
    if round_idx == 0:
        if resp and (resp.content or "").strip():
            return "completed"
        return "failed" if error else "no_json"
    if parsed is None:
        return "failed" if error else "no_json"
    if semantic_issues:
        return "partial"
    if source_quality and source_quality.get("level") in {"weak", "missing"}:
        return "partial"
    return "completed"


def _round_record(
    round_idx: int,
    focus: str,
    model: str,
    resp: LLMResponse | None,
    parsed: dict | None,
    error: str | None = None,
    repaired: bool = False,
    semantic_issues: list[str] | None = None,
    source_quality: dict[str, Any] | None = None,
) -> dict:
    semantic_issues = semantic_issues or []
    record: dict[str, Any] = {
        "round": round_idx,
        "focus": focus,
        "model": model,
        "status": _round_status(round_idx, parsed, error, resp, semantic_issues, source_quality),
        "reasoning": (resp.reasoning if resp else "") or "",
        "search_results": (resp.search_results if resp else []) or [],
        "conclusion": parsed or {},
        "tokens": (resp.total_tokens if resp else 0) or 0,
        "prompt_tokens": (resp.prompt_tokens if resp else 0) or 0,
        "completion_tokens": (resp.completion_tokens if resp else 0) or 0,
        "cost_ms": (resp.cost_ms if resp else 0) or 0,
        "error": error,
        "repaired_json": repaired,
        "semantic_issues": semantic_issues,
        "source_quality": source_quality,
    }
    if parsed:
        for key in (
            "home_win_prob",
            "draw_prob",
            "away_win_prob",
            "predicted_home_score",
            "predicted_away_score",
            "conservative_verdict",
            "aggressive_verdict",
            "confidence",
            "key_reasons",
            "thinking",
            "mermaid_mindmap",
        ):
            if key in parsed:
                record[key] = parsed[key]
    return record


def _safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except LLMError as exc:
        logger.warning("LLM 调用失败: %s", exc)
        return None, str(exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM 调用异常: %s", exc)
        return None, f"{type(exc).__name__}: {exc}"


def _emit_round_log(round_record: dict) -> None:
    """Emit structured JSON log for a completed round (C1 observability)."""
    try:
        log_entry = {
            "event": "round_completed",
            "round": round_record.get("round"),
            "status": round_record.get("status"),
            "cost_ms": int(round_record.get("cost_ms") or 0),
            "prompt_tokens": int(round_record.get("prompt_tokens") or 0),
            "completion_tokens": int(round_record.get("completion_tokens") or 0),
            "tokens": int(round_record.get("tokens") or 0),
            "model": round_record.get("model"),
            "focus": round_record.get("focus"),
            "error": round_record.get("error"),
            "repaired_json": round_record.get("repaired_json", False),
            "semantic_issues": round_record.get("semantic_issues", []),
        }
        logger.info(json.dumps(log_entry, ensure_ascii=False))
    except Exception:  # noqa: BLE001
        pass  # Never let logging break the prediction flow


class PredictionOrchestrator:
    """Coordinates four prediction rounds and persistence."""

    def __init__(self, db: Session | None = None):
        self.db = db
        self._stepfun: StepFunClient | None = None
        self._deepseek: DeepSeekClient | None = None

    @property
    def stepfun(self) -> StepFunClient:
        if self._stepfun is None:
            self._stepfun = StepFunClient()
        return self._stepfun

    @property
    def deepseek(self) -> DeepSeekClient:
        if self._deepseek is None:
            self._deepseek = DeepSeekClient()
        return self._deepseek

    @property
    def web_search_available(self) -> bool:
        """独立联网搜索（Firecrawl）是否可用。"""
        return web_search_available()

    def _apply_source_quality_penalty(self, parsed: dict | None, resp: LLMResponse | None) -> tuple[dict | None, dict[str, Any] | None]:
        if parsed is None or resp is None:
            return parsed, None

        source_quality = _assess_search_sources(resp.search_results)
        penalty = int(source_quality.get("confidence_penalty", 0))
        parsed["confidence"] = max(0.0, round(float(parsed.get("confidence") or 0) - penalty, 1))
        return parsed, source_quality

    def _attempt_semantic_repair(
        self,
        resp: LLMResponse,
        parsed: dict,
        issues: list[str],
        *,
        include_mermaid: bool = False,
    ) -> tuple[dict | None, str | None, bool]:
        repair_prompt = _build_semantic_repair_prompt(resp, parsed, issues, include_mermaid)
        repair_resp, repair_error = _safe_call(
            self.deepseek.chat,
            SKILL_SYSTEM_PROMPT,
            repair_prompt,
            json_mode=True,
            max_tokens=4096,
        )
        if repair_resp:
            try:
                repaired_payload = _normalize_prediction_payload(
                    repair_resp.parse_json(),
                    repair_resp,
                    include_mermaid=include_mermaid,
                )
            except LLMError as exc:
                repair_error = repair_error or str(exc)
            else:
                repaired_issues = _semantic_issues(repaired_payload)
                if not repaired_issues:
                    return repaired_payload, None, True
                return repaired_payload, f"语义修复后仍不完整: {repaired_issues}", True
        return parsed, repair_error or f"语义修复失败: {issues}", True

    def _parse_with_repair(
        self,
        resp: LLMResponse | None,
        *,
        include_mermaid: bool = False,
        assess_sources: bool = False,
    ) -> tuple[dict | None, str | None, bool, list[str], dict[str, Any] | None]:
        if not resp:
            return None, None, False, ["missing_response"], None

        parsed: dict | None = None
        parse_exc: LLMError | None = None
        try:
            parsed = resp.parse_json()
        except LLMError as exc:
            parse_exc = exc

        # ── Aggressive fallback: search the combined content+reasoning text for
        #    any valid JSON object when the per-source extraction fails.
        if parsed is None and (resp.content or resp.reasoning):
            combined = (resp.content or "") + "\n" + (resp.reasoning or "")
            for candidate in _candidate_json_texts(_message_text(combined)):
                try:
                    parsed = json.loads(candidate)
                    break
                except json.JSONDecodeError:
                    repaired = _cleanup_json_candidate(_close_json_candidate(candidate))
                    if repaired != candidate:
                        try:
                            parsed = json.loads(repaired)
                            break
                        except json.JSONDecodeError:
                            pass

        if parsed is not None:
            try:
                normalized = _normalize_prediction_payload(parsed, resp, include_mermaid=include_mermaid)
            except LLMError as inner_exc:
                parse_exc = parse_exc or inner_exc
                parsed = None
            else:
                issues = _semantic_issues(normalized)
                repaired = False
                error = None
                if issues:
                    normalized, error, repaired = self._attempt_semantic_repair(
                        resp,
                        normalized,
                        issues,
                        include_mermaid=include_mermaid,
                    )
                    issues = _semantic_issues(normalized)

                source_quality = None
                if assess_sources:
                    normalized, source_quality = self._apply_source_quality_penalty(normalized, resp)

                return normalized, error, repaired, issues, source_quality
        else:
            normalized = None

        mermaid = extract_mermaid_block(resp.content) or extract_mermaid_block(resp.reasoning)
        if mermaid:
            fallback = _normalize_prediction_payload(
                {
                    "home_win_prob": 33.3,
                    "draw_prob": 33.3,
                    "away_win_prob": 33.4,
                    "predicted_home_score": 1,
                    "predicted_away_score": 1,
                    "conservative_verdict": "结构化结论损坏，暂按保守平局兜底。",
                    "aggressive_verdict": "等待下一轮或裁决轮给出更明确方向。",
                    "confidence": 35,
                    "key_reasons": ["已提取 Mermaid 导图，但未获得完整 JSON 结论"],
                    "thinking": (resp.reasoning or resp.content or "").strip(),
                    "mermaid_mindmap": mermaid,
                },
                resp,
                include_mermaid=True,
            )
            issues = _semantic_issues(fallback)
            return fallback, f"{parse_exc}（已提取 Mermaid 并做结构化兜底）", True, issues, None
        return None, str(parse_exc) if parse_exc else "json_parse_failed", False, ["json_parse_failed"], None

        issues = _semantic_issues(normalized)
        repaired = False
        error = None
        if issues:
            normalized, error, repaired = self._attempt_semantic_repair(
                resp,
                normalized,
                issues,
                include_mermaid=include_mermaid,
            )
            issues = _semantic_issues(normalized)

        source_quality = None
        if assess_sources:
            normalized, source_quality = self._apply_source_quality_penalty(normalized, resp)

        return normalized, error, repaired, issues, source_quality

    def _round_tactical(self, context_block: str, meta: dict, web_intel: list[SearchResult] | None = None, vision_block: str = "") -> dict:
        has_intel = bool(web_intel)
        intel_block = build_intel_block(web_intel or [], heading="实时网络情报·战术视角") if has_intel else ""
        resp, error = _safe_call(
            self.stepfun.chat,
            SKILL_SYSTEM_PROMPT,
            build_tactical_prompt(context_block, meta, allow_search=False, web_intel_block=intel_block, vision_block=vision_block),
            enable_search=False,
            json_mode=True,
            max_tokens=8192,
        )
        parsed = None
        repaired = False
        semantic_issues: list[str] = []
        source_quality = None
        if resp:
            # 把独立搜索来源挂到 resp 上，供 _parse_with_repair 评估 + 落库展示
            if has_intel:
                resp.search_results = [
                    {"title": r.title, "url": r.url, "snippet": r.content} for r in web_intel  # type: ignore[index]
                ]
            parsed, parse_error, repaired, semantic_issues, source_quality = self._parse_with_repair(resp, assess_sources=has_intel)
            error = error or parse_error
        focus = "战术视角(step-3.7-flash·联网情报)" if has_intel else "战术视角(step-3.7-flash·知识)"
        return _round_record(1, focus, "step-3.7-flash", resp, parsed, error, repaired, semantic_issues, source_quality)

    def _round_contextual(self, context_block: str, meta: dict, web_intel: list[SearchResult] | None = None, vision_block: str = "") -> dict:
        has_intel = bool(web_intel)
        intel_block = build_intel_block(web_intel or [], heading="实时网络情报·场外视角") if has_intel else ""
        resp, error = _safe_call(
            self.stepfun.chat,
            SKILL_SYSTEM_PROMPT,
            build_contextual_prompt(context_block, meta, allow_search=False, web_intel_block=intel_block, vision_block=vision_block),
            enable_search=False,
            json_mode=True,
            max_tokens=8192,
        )
        parsed = None
        repaired = False
        semantic_issues: list[str] = []
        source_quality = None
        if resp:
            if has_intel:
                resp.search_results = [
                    {"title": r.title, "url": r.url, "snippet": r.content} for r in web_intel  # type: ignore[index]
                ]
            parsed, parse_error, repaired, semantic_issues, source_quality = self._parse_with_repair(resp, assess_sources=has_intel)
            error = error or parse_error
        focus = "场外微观(step-3.7-flash·联网情报)" if has_intel else "场外微观(step-3.7-flash·知识)"
        return _round_record(2, focus, "step-3.7-flash", resp, parsed, error, repaired, semantic_issues, source_quality)

    def _round_reasoning(self, context_block: str, meta: dict, prior: list[dict]) -> dict:
        resp, error = _safe_call(
            self.deepseek.chat,
            SKILL_SYSTEM_PROMPT,
            build_reasoning_prompt(context_block, meta, prior),
            json_mode=True,
            max_tokens=8192,
        )
        parsed = None
        repaired = False
        semantic_issues: list[str] = []
        if resp:
            parsed, parse_error, repaired, semantic_issues, _ = self._parse_with_repair(resp)
            error = error or parse_error
        return _round_record(3, "深度推理(deepseek-v4-flash·1M上下文)", "deepseek-v4-flash", resp, parsed, error, repaired, semantic_issues, None)

    def _build_arbiter_fallback(self, usable: list[dict], error: str | None) -> dict:
        fallback = usable[-1]
        return {
            "home_win_prob": fallback.get("home_win_prob", 33.3),
            "draw_prob": fallback.get("draw_prob", 33.3),
            "away_win_prob": fallback.get("away_win_prob", 33.4),
            "predicted_home_score": fallback.get("predicted_home_score", 1),
            "predicted_away_score": fallback.get("predicted_away_score", 1),
            "conservative_verdict": fallback.get("conservative_verdict", "无法裁决，参考最近一轮"),
            "aggressive_verdict": fallback.get("aggressive_verdict", ""),
            "confidence": fallback.get("confidence") or 50,
            "key_reasons": fallback.get("key_reasons") or [],
            "thinking": f"裁决轮失败（{error}），已回退到最近一轮成功分析。",
            "mermaid_mindmap": fallback.get("mermaid_mindmap"),
        }

    def _select_usable_rounds(self, all_rounds: list[dict]) -> list[dict]:
        usable = [round_data for round_data in all_rounds if round_data.get("status") in {"completed", "partial"}]
        for round_data in usable:
            source_quality = round_data.get("source_quality") or {}
            if source_quality.get("level") in {"weak", "missing"}:
                round_data["arbiter_weight"] = 0.6
            elif source_quality.get("level") == "medium":
                round_data["arbiter_weight"] = 0.85
            else:
                round_data["arbiter_weight"] = 1.0
        return usable

    def _arbitrate(self, meta: dict, all_rounds: list[dict]) -> tuple[dict | None, dict]:
        usable = self._select_usable_rounds(all_rounds)
        if not usable:
            return None, _round_record(
                4,
                "综合裁决(deepseek-v4-flash)",
                "deepseek-v4-flash",
                None,
                None,
                error="所有分析轮均失败，无法裁决",
                semantic_issues=["no_usable_rounds"],
                source_quality=None,
            )

        resp, error = _safe_call(
            self.deepseek.chat,
            SKILL_SYSTEM_PROMPT,
            build_arbiter_prompt(meta, usable),
            json_mode=True,
            max_tokens=8192,
        )
        parsed = None
        repaired = False
        semantic_issues: list[str] = []
        if resp:
            parsed, parse_error, repaired, semantic_issues, _ = self._parse_with_repair(resp, include_mermaid=True)
            error = error or parse_error

        if parsed is None:
            logger.warning("裁决轮失败，使用最近一轮成功结果兜底")
            parsed = self._build_arbiter_fallback(usable, error)
            repaired = True
            error = (error or "裁决轮无可用 JSON") + "（已回退到最近一轮成功分析）"
            semantic_issues = _semantic_issues(parsed)

        arbiter_record = _round_record(
            4,
            "综合裁决(deepseek-v4-flash)",
            "deepseek-v4-flash",
            resp,
            parsed,
            error,
            repaired,
            semantic_issues,
            None,
        )
        return parsed, arbiter_record

    def _gather_web_intel(self, meta: dict) -> tuple[list[SearchResult], str | None]:
        """为这场比赛拉取实时网络情报（战术+场外各搜一次，合并去重）。

        返回 (结果列表, 错误信息)。provider 不可用时返回 ([], None)，调用方按知识模式降级。
        """
        if not web_search_available():
            logger.info("联网搜索未配置，本轮采用知识模式")
            return [], None

        home = meta.get("home_name") or "主队"
        away = meta.get("away_name") or "客队"
        # 两个互补查询：一个偏战术/状态，一个偏场外/突发
        # 启用 include_images 以便后续做视觉理解增强
        queries = [
            f"{home} vs {away} 比赛预测 首发 伤停 状态",
            f"{home} {away} 赛前 采访 天气 球迷 突发新闻",
        ]
        merged: list[SearchResult] = []
        seen_urls: set[str] = set()
        for q in queries:
            for r in search_safe_cached(q, include_images=True):
                url = (r.url or "").strip()
                if url and url in seen_urls:
                    continue
                seen_urls.add(url)
                merged.append(r)
        logger.info("联网情报采集完成：%s vs %s，共 %d 条", home, away, len(merged))
        return merged, None

    def _run_vision_analysis(
        self, meta: dict, search_results: list[SearchResult]
    ) -> tuple[str, dict | None]:
        """对阵容/战术图片做视觉分析，返回 (视觉情报markdown块, 视觉轮记录)。

        策略：先用专门的「lineup/formation/squad」英文查询搜高质量阵容图
        （theanalyst/opta 等英文源质量远高于中文查询带回的社交媒体图）；
        再从文字情报结果里补充候选。无图片或功能关闭时返回 ("", None)。
        """
        if not ENABLE_VISION_INTEL:
            return "", None

        home = meta.get("home_name") or "主队"
        away = meta.get("away_name") or "客队"

        # ① 专门的阵容/阵型查图（英文，针对高质量图源）
        lineup_candidates: list[SearchResult] = []
        if web_search_available():
            for q in (
                f"{home} vs {away} predicted lineup formation",
                f"{home} {away} starting eleven squad",
            ):
                lineup_candidates.extend(search_safe_cached(q, include_images=True))
        # ② 补充：文字情报结果里的图片
        all_candidates = lineup_candidates + (search_results or [])

        images = extract_image_urls(all_candidates)
        if not images:
            logger.info("无可用图片，跳过视觉分析")
            return "", None

        logger.info("视觉分析：%d 张图片待分析（优质源优先）", len(images))
        resp, error = analyze_images(self.stepfun, meta, images)
        # 视觉模型偶发 500/超时：失败则降级跳过，不影响整体预测
        vision_block = build_vision_block(resp, images) if resp else ""

        # 构造第 0 轮记录（视觉轮），供前端展示
        search_sources = [
            {"title": img.get("source") or "", "url": img.get("url") or "", "snippet": img.get("description") or ""}
            for img in images
        ]
        record = _round_record(
            0,
            f"视觉情报(step-1o-turbo-vision·{len(images)}图)",
            "step-1o-turbo-vision",
            resp,
            None,
            error=error,
            repaired=False,
            semantic_issues=[],
            source_quality=None,
        )
        # 视觉轮的 reasoning 字段放视觉模型的分析正文（便于前端展示）
        if resp and resp.content:
            record["reasoning"] = resp.content
        record["search_results"] = search_sources
        return vision_block, record

    def run_full_prediction(self, db: Session, match_id: int) -> MatchPrediction:
        start = time.time()
        logger.info("开始预测比赛 match_id=%s", match_id)

        ctx_start = time.time()
        try:
            context = build_match_context(db, match_id)
        except ValueError as exc:
            logger.error("上下文采集失败: %s", exc)
            return self._persist_failure(db, match_id, str(exc))
        ctx_cost_ms = int((time.time() - ctx_start) * 1000)

        meta = context.get("meta", {})
        context_block = build_context_block(context)

        # 独立联网搜索：为这场比赛拉取实时情报，注入 context 喂给 step 两轮分析
        search_start = time.time()
        search_results, search_error = self._gather_web_intel(meta)
        search_cost_ms = int((time.time() - search_start) * 1000)

        # 视觉理解增强：对搜索到的图片做视觉分析，产出额外情报块
        vision_start = time.time()
        vision_block, vision_record = self._run_vision_analysis(meta, search_results)
        vision_cost_ms = int((time.time() - vision_start) * 1000)
        if vision_record:
            _emit_round_log(vision_record)

        # ── B1 优化：R1 (战术) + R2 (场外) 并行执行 ──
        # R3 (深度推理) 依赖 R1+R2 结果 (prior_for_reasoning)，不能并行
        parallel_start = time.time()

        def _safe_round_tactical():
            try:
                return self._round_tactical(context_block, meta, search_results, vision_block)
            except Exception as exc:  # noqa: BLE001
                logger.exception("R1 战术轮异常: %s", exc)
                return _round_record(1, "战术视角(step-3.7-flash)", "step-3.7-flash", None, None, f"{type(exc).__name__}: {exc}")

        def _safe_round_contextual():
            try:
                return self._round_contextual(context_block, meta, search_results, vision_block)
            except Exception as exc:  # noqa: BLE001
                logger.exception("R2 场外轮异常: %s", exc)
                return _round_record(2, "场外微观(step-3.7-flash)", "step-3.7-flash", None, None, f"{type(exc).__name__}: {exc}")

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="pred-r") as pool:
            fut_r1 = pool.submit(_safe_round_tactical)
            fut_r2 = pool.submit(_safe_round_contextual)
            round1 = fut_r1.result()
            round2 = fut_r2.result()

        parallel_cost = int((time.time() - parallel_start) * 1000)
        r1_ms = int(round1.get("cost_ms") or 0)
        r2_ms = int(round2.get("cost_ms") or 0)
        logger.info(
            "R1+R2 并行完成 match_id=%s wall=%dms (R1=%dms R2=%dms 串行估算=%dms 节省=%dms)",
            match_id, parallel_cost, r1_ms, r2_ms, r1_ms + r2_ms,
            (r1_ms + r2_ms) - parallel_cost,
        )
        _emit_round_log(round1)
        _emit_round_log(round2)

        prior_for_reasoning = [round_data for round_data in (round1, round2) if round_data.get("status") in {"completed", "partial"}]
        round3 = self._round_reasoning(context_block, meta, prior_for_reasoning)
        _emit_round_log(round3)
        all_rounds: list[dict] = []
        if vision_record:
            all_rounds.append(vision_record)
        all_rounds.extend([round1, round2, round3])

        final, arbiter_round = self._arbitrate(meta, all_rounds)
        _emit_round_log(arbiter_round)
        all_rounds_with_arbiter = all_rounds + [arbiter_round]

        total_tokens = sum(int(round_data.get("tokens") or 0) for round_data in all_rounds_with_arbiter)
        # total_cost_ms = sum of per-round LLM API latencies so that the reported number
        # is consistent with the per-round "cost_ms" breakdown the frontend displays.
        # (Previously this measured wall-clock, producing a 43.4 s discrepancy vs.
        #  the round sum due to context-building / web-search / vision overhead.)
        total_cost_ms = sum(int(round_data.get("cost_ms") or 0) for round_data in all_rounds_with_arbiter)
        wall_ms = int((time.time() - start) * 1000)
        logger.info(
            "cost breakdown match_id=%s wall=%dms round_total=%dms overhead=%dms (ctx=%d search=%d vision=%d)",
            match_id, wall_ms, total_cost_ms, wall_ms - total_cost_ms,
            ctx_cost_ms, search_cost_ms, vision_cost_ms,
        )
        status = "completed" if final else "failed"
        error_messages = [round_data.get("error") for round_data in all_rounds_with_arbiter if round_data.get("error")]
        error_msg = " ; ".join(error_messages) if error_messages else None

        # ── C1: Structured summary log ──────────────────────────────────────────────
        try:
            summary_entry = {
                "event": "prediction_completed",
                "match_id": match_id,
                "status": status,
                "total_ms": wall_ms,
                "total_cost_ms": total_cost_ms,
                "total_tokens": total_tokens,
                "total_prompt_tokens": sum(int(r.get("prompt_tokens") or 0) for r in all_rounds_with_arbiter),
                "total_completion_tokens": sum(int(r.get("completion_tokens") or 0) for r in all_rounds_with_arbiter),
                "num_rounds": len(all_rounds_with_arbiter),
                "rounds": [
                    {
                        "round": r.get("round"),
                        "focus": r.get("focus"),
                        "model": r.get("model"),
                        "status": r.get("status"),
                        "cost_ms": int(r.get("cost_ms") or 0),
                        "tokens": int(r.get("tokens") or 0),
                        "prompt_tokens": int(r.get("prompt_tokens") or 0),
                        "completion_tokens": int(r.get("completion_tokens") or 0),
                    }
                    for r in all_rounds_with_arbiter
                ],
                "error": error_msg,
            }
            logger.info(json.dumps(summary_entry, ensure_ascii=False))
        except Exception:  # noqa: BLE001
            pass  # Never let logging break persistence

        return self._persist(
            db,
            match_id=match_id,
            final=final,
            rounds=all_rounds_with_arbiter,
            total_tokens=total_tokens,
            total_cost_ms=total_cost_ms,
            status=status,
            error_msg=error_msg,
            final_summary=final.get("thinking") if final else None,
        )

    def _persist(
        self,
        db: Session,
        match_id: int,
        final: dict | None,
        rounds: list[dict],
        total_tokens: int,
        total_cost_ms: int,
        status: str,
        error_msg: str | None,
        final_summary: str | None,
    ) -> MatchPrediction:
        existing = db.query(MatchPrediction).filter(MatchPrediction.match_id == match_id).first()
        now = datetime.now()
        common = dict(
            home_win_prob=final.get("home_win_prob") if final else None,
            draw_prob=final.get("draw_prob") if final else None,
            away_win_prob=final.get("away_win_prob") if final else None,
            predicted_home_score=final.get("predicted_home_score") if final else None,
            predicted_away_score=final.get("predicted_away_score") if final else None,
            conservative_verdict=final.get("conservative_verdict") if final else None,
            aggressive_verdict=final.get("aggressive_verdict") if final else None,
            key_reasons=final.get("key_reasons") if final else None,
            confidence=final.get("confidence") if final else None,
            mermaid_mindmap=final.get("mermaid_mindmap") if final else None,
            rounds=rounds,
            final_summary=final_summary,
            total_tokens=total_tokens,
            total_cost_ms=total_cost_ms,
            status=status,
            error_msg=error_msg,
            generated_at=now,
            last_updated_at=now,
        )
        if existing:
            for key, value in common.items():
                setattr(existing, key, value)
            existing.version = (existing.version or 1) + 1
            obj = existing
        else:
            obj = MatchPrediction(match_id=match_id, version=1, **common)
            db.add(obj)
        db.commit()
        db.refresh(obj)
        logger.info(
            "预测完成 match_id=%s status=%s tokens=%s cost=%sms rounds=%d",
            match_id,
            status,
            total_tokens,
            total_cost_ms,
            len(rounds),
        )
        return obj

    def _persist_failure(self, db: Session, match_id: int, error: str) -> MatchPrediction:
        existing = db.query(MatchPrediction).filter(MatchPrediction.match_id == match_id).first()
        now = datetime.now()
        common = dict(
            rounds=[],
            status="failed",
            error_msg=error,
            generated_at=now,
            last_updated_at=now,
            total_tokens=0,
            total_cost_ms=0,
            home_win_prob=None,
            draw_prob=None,
            away_win_prob=None,
            predicted_home_score=None,
            predicted_away_score=None,
            conservative_verdict=None,
            aggressive_verdict=None,
            key_reasons=None,
            confidence=None,
            mermaid_mindmap=None,
            final_summary=None,
        )
        if existing:
            for key, value in common.items():
                setattr(existing, key, value)
            obj = existing
        else:
            obj = MatchPrediction(match_id=match_id, version=1, **common)
            db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj
