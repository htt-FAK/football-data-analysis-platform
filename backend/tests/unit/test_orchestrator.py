"""Orchestrator 单元测试 — 覆盖 B1 并行 / B3 缓存 / C1 日志。

测试目标:
- search_safe_cached: 缓存命中/未命中/TTL 过期/include_images 区分
- _emit_round_log: JSON 结构化日志输出合法 + 防御性不抛异常
- _safe_call: LLM 调用封装（成功/LLMError/异常）
- _coerce_probability / _coerce_int / _normalize_text / _coerce_reasons
- _assess_search_sources: 搜索来源质量评估
- _semantic_issues: 语义完整性检测
- _is_placeholder_text: 占位词检测
- _round_status / _round_record: 轮次状态记录
"""

from __future__ import annotations

import json
import logging
import time
from unittest.mock import MagicMock, patch

import pytest

from app.prediction.orchestrator import (
    _assess_search_sources,
    _coerce_int,
    _coerce_probability,
    _coerce_reasons,
    _emit_round_log,
    _is_placeholder_text,
    _normalize_text,
    _round_record,
    _round_status,
    _safe_call,
    _search_cache,
    _CACHE_TTL_SECONDS,
    search_safe_cached,
)
from app.prediction.llm_client import LLMError, LLMResponse


# ============================================================================
# B3: search_safe_cached 缓存
# ============================================================================


class TestSearchSafeCached:
    """search_safe_cached 进程内缓存行为。"""

    def setup_method(self):
        """每个测试前清空缓存。"""
        _search_cache.clear()

    @patch("app.prediction.orchestrator.search_safe")
    def test_cache_hit_on_same_query(self, mock_search_safe):
        """相同查询第二次命中缓存，不再调用 search_safe。"""
        mock_search_safe.return_value = [{"title": "result"}]

        r1 = search_safe_cached("query A")
        r2 = search_safe_cached("query A")

        assert r1 == r2
        # search_safe 只被调用一次
        assert mock_search_safe.call_count == 1

    @patch("app.prediction.orchestrator.search_safe")
    def test_cache_miss_on_different_query(self, mock_search_safe):
        """不同查询不命中缓存。"""
        mock_search_safe.return_value = [{"title": "result"}]

        search_safe_cached("query A")
        search_safe_cached("query B")

        assert mock_search_safe.call_count == 2

    @patch("app.prediction.orchestrator.time.time")
    @patch("app.prediction.orchestrator.search_safe")
    def test_cache_ttl_expiry(self, mock_search_safe, mock_time):
        """TTL 过期后重新请求。"""
        mock_search_safe.return_value = [{"title": "result"}]
        # search_safe_cached 每次只调用一次 time.time()
        # 第一次调用: now=0.0 → cache miss → search_safe 被调用 → 缓存 (0.0, results)
        # 第二次调用: now=TTL+1 → cache 已过期 → search_safe 再被调用
        mock_time.side_effect = [0.0, float(_CACHE_TTL_SECONDS + 1)]

        search_safe_cached("query A")
        search_safe_cached("query A")

        assert mock_search_safe.call_count == 2

    @patch("app.prediction.orchestrator.search_safe")
    def test_cache_key_distinguishes_include_images(self, mock_search_safe):
        """带图/不带图的缓存 key 不同。"""
        mock_search_safe.return_value = [{"title": "result"}]

        search_safe_cached("query A", include_images=False)
        search_safe_cached("query A", include_images=True)

        assert mock_search_safe.call_count == 2


# ============================================================================
# C1: _emit_round_log 结构化日志
# ============================================================================


class TestEmitRoundLog:
    """_emit_round_log 输出合法 JSON 且不抛异常。"""

    def test_emit_round_log_outputs_valid_json(self, caplog):
        """输出是合法的 JSON 字符串。"""
        record = {
            "round": 1,
            "status": "completed",
            "cost_ms": 2000,
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "tokens": 1500,
            "model": "step-3.7-flash",
            "focus": "战术视角",
            "error": None,
            "repaired_json": False,
            "semantic_issues": [],
        }
        with caplog.at_level(logging.INFO, logger="app.prediction.orchestrator"):
            _emit_round_log(record)

        # 找到包含 event=round_completed 的日志行
        json_lines = [
            line for line in caplog.text.splitlines()
            if '"event": "round_completed"' in line or '"event":"round_completed"' in line
        ]
        assert len(json_lines) >= 1
        # 尝试解析 JSON（日志行可能包含 timestamp 前缀，提取 JSON 部分）
        for line in json_lines:
            # 找到第一个 { 的位置
            json_start = line.index("{")
            parsed = json.loads(line[json_start:])
            assert parsed["event"] == "round_completed"
            assert parsed["round"] == 1
            break

    def test_emit_round_log_never_raises(self):
        """任何输入都不抛异常（防御性测试）。"""
        # 正常输入
        _emit_round_log({})
        # 异常输入
        _emit_round_log({"round": None, "status": None, "cost_ms": "not_int"})
        _emit_round_log({"round": object()})  # 不可序列化的对象
        # 不应抛异常即通过

    def test_emit_round_log_handles_missing_fields(self):
        """缺失字段不抛异常。"""
        _emit_round_log({"round": 1})  # 缺少大部分字段
        _emit_round_log({})


# ============================================================================
# _safe_call
# ============================================================================


class TestSafeCall:
    """_safe_call 异常封装。"""

    def test_safe_call_success(self):
        """正常调用返回 (result, None)。"""
        fn = MagicMock(return_value=42)
        result, error = _safe_call(fn, 1, 2, key="val")
        assert result == 42
        assert error is None
        fn.assert_called_once_with(1, 2, key="val")

    def test_safe_call_llm_error(self):
        """LLMError 被捕获返回 (None, error_msg)。"""
        fn = MagicMock(side_effect=LLMError("api failed"))
        result, error = _safe_call(fn)
        assert result is None
        assert "api failed" in error

    def test_safe_call_generic_exception(self):
        """通用异常被捕获。"""
        fn = MagicMock(side_effect=ValueError("oops"))
        result, error = _safe_call(fn)
        assert result is None
        assert "ValueError" in error
        assert "oops" in error


# ============================================================================
# 辅助函数
# ============================================================================


class TestCoerceHelpers:
    """数据转换辅助函数。"""

    def test_coerce_probability_normal(self):
        """正常值在 [0, 100] 范围内。"""
        assert _coerce_probability(50, 33.3) == 50.0
        assert _coerce_probability(0, 33.3) == 0.0
        assert _coerce_probability(100, 33.3) == 100.0

    def test_coerce_probability_clamp(self):
        """超出范围的值被 clamp。"""
        assert _coerce_probability(150, 33.3) == 100.0
        assert _coerce_probability(-10, 33.3) == 0.0

    def test_coerce_probability_invalid(self):
        """无效值返回 fallback。"""
        assert _coerce_probability("abc", 33.3) == 33.3
        assert _coerce_probability(None, 33.3) == 33.3

    def test_coerce_int_normal(self):
        """正常转换。"""
        assert _coerce_int(3.7, 1) == 4
        assert _coerce_int("5", 1) == 5
        assert _coerce_int(0, 1) == 0

    def test_coerce_int_invalid(self):
        """无效值返回 fallback。"""
        assert _coerce_int("abc", 1) == 1
        assert _coerce_int(None, 1) == 1

    def test_normalize_text(self):
        """文本标准化。"""
        assert _normalize_text("  hello  ") == "hello"
        assert _normalize_text(None) == ""
        assert _normalize_text("") == ""
        assert _normalize_text(123) == "123"

    def test_coerce_reasons_list(self):
        """列表输入：过滤空项，限制 8 条。"""
        reasons = _coerce_reasons(["a", "", "b", "  ", "c"])
        assert reasons == ["a", "b", "c"]

    def test_coerce_reasons_string(self):
        """字符串输入：按行拆分。"""
        reasons = _coerce_reasons("reason1\nreason2\nreason3")
        assert len(reasons) == 3

    def test_coerce_reasons_none(self):
        """None 返回空列表。"""
        assert _coerce_reasons(None) == []


# ============================================================================
# _assess_search_sources / _semantic_issues / _is_placeholder_text
# ============================================================================


class TestSourceAndSemantic:
    """搜索来源评估与语义完整性检测。"""

    def test_assess_search_sources_strong(self):
        """高质量搜索结果评级为 strong。"""
        results = [
            {"title": "News 1", "url": "https://bbc.com/1"},
            {"title": "News 2", "url": "https://sky.com/2"},
            {"title": "News 3", "url": "https://guardian.com/3"},
        ]
        assessment = _assess_search_sources(results)
        assert assessment["level"] == "strong"
        assert assessment["score"] == 3
        assert assessment["confidence_penalty"] == 0

    def test_assess_search_sources_missing(self):
        """无搜索结果评级为 missing。"""
        assessment = _assess_search_sources([])
        assert assessment["level"] == "missing"
        assert assessment["confidence_penalty"] == 20

    def test_assess_search_sources_query_echo(self):
        """全是搜索回显的结果评级为 missing。"""
        results = [
            {"title": "搜索: test query", "url": ""},
            {"title": "搜索: test query", "url": ""},
        ]
        assessment = _assess_search_sources(results)
        assert assessment["score"] == 0
        assert assessment["level"] == "missing"

    def test_is_placeholder_text(self):
        """占位词检测。"""
        assert _is_placeholder_text("结论待补充") is True
        assert _is_placeholder_text("tbd") is True
        assert _is_placeholder_text("TODO") is True
        assert _is_placeholder_text("") is True
        assert _is_placeholder_text("  ") is True
        assert _is_placeholder_text("实际结论") is False

    def test_semantic_issues_missing_payload(self):
        """空 payload 检测到 issue。"""
        from app.prediction.orchestrator import _semantic_issues
        issues = _semantic_issues(None)
        assert "missing_payload" in issues

    def test_semantic_issues_placeholder_verdicts(self):
        """占位词 verdict 被检测出。"""
        from app.prediction.orchestrator import _semantic_issues
        payload = {
            "conservative_verdict": "结论待补充",
            "aggressive_verdict": "tbd",
            "key_reasons": ["only one"],
        }
        issues = _semantic_issues(payload)
        assert "missing_conservative_verdict" in issues
        assert "missing_aggressive_verdict" in issues
        assert "insufficient_key_reasons" in issues


# ============================================================================
# _round_status / _round_record
# ============================================================================


class TestRoundInfrastructure:
    """轮次状态判定与记录构造。"""

    def test_round_status_completed(self):
        """有 parsed、无 semantic issues、source 质量 good → completed。"""
        status = _round_status(1, {"a": 1}, None, MagicMock(), [], {"level": "strong"})
        assert status == "completed"

    def test_round_status_failed(self):
        """无 parsed + 有 error → failed。"""
        status = _round_status(1, None, "some error", MagicMock(), [], None)
        assert status == "failed"

    def test_round_status_no_json(self):
        """无 parsed + 无 error → no_json。"""
        status = _round_status(1, None, None, MagicMock(), [], None)
        assert status == "no_json"

    def test_round_status_partial(self):
        """有 parsed + 有 semantic issues → partial。"""
        status = _round_status(1, {"a": 1}, None, MagicMock(), ["issue1"], None)
        assert status == "partial"

    def test_round_status_vision_round(self):
        """round 0 (视觉轮)：有 content → completed。"""
        resp = MagicMock()
        resp.content = "analysis text"
        status = _round_status(0, None, None, resp, [], None)
        assert status == "completed"

    def test_round_record_structure(self):
        """_round_record 生成正确的 dict 结构。"""
        record = _round_record(
            round_idx=1,
            focus="战术视角",
            model="step-3.7-flash",
            resp=None,
            parsed={"home_win_prob": 60},
            error=None,
        )
        assert record["round"] == 1
        assert record["focus"] == "战术视角"
        assert record["model"] == "step-3.7-flash"
        assert record["home_win_prob"] == 60
