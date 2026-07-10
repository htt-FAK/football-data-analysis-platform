"""LLM 客户端单元测试 — 覆盖 C2 重试机制 + JSON 解析 + token 提取。

测试目标:
- _call_with_retry: success / fail / retriable codes / timeout
- _extract_all_balanced_json_objects: 多 JSON 块提取
- _close_json_candidate: 截断 JSON 修复
- _cleanup_json_candidate: 尾逗号清理
- LLMResponse.parse_json: 从 content/reasoning 字段解析
- _message_text: 多格式消息展平
- _strip_code_fences / _extract_fenced_blocks: 代码围栏处理
- extract_mermaid_block: Mermaid 提取
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.prediction.llm_client import (
    LLMError,
    LLMResponse,
    _call_with_retry,
    _candidate_json_texts,
    _cleanup_json_candidate,
    _close_json_candidate,
    _extract_all_balanced_json_objects,
    _extract_fenced_blocks,
    _message_text,
    _strip_code_fences,
    extract_mermaid_block,
)


# ============================================================================
# C2: _call_with_retry 重试机制
# ============================================================================


class TestCallWithRetry:
    """_call_with_retry 指数退避重试逻辑。"""

    @patch("app.prediction.llm_client.time.sleep")
    @patch("app.prediction.llm_client.LLM_RETRY_MAX_ATTEMPTS", 3)
    @patch("app.prediction.llm_client.LLM_RETRY_BACKOFF_FACTOR", 1)
    def test_retry_on_500_then_success(self, mock_sleep):
        """首次 500 → 重试成功：返回第二次 response。"""
        resp_fail = MagicMock(status_code=500, text="err")
        resp_ok = MagicMock(status_code=200, text="ok")
        call_fn = MagicMock(side_effect=[resp_fail, resp_ok])

        result = _call_with_retry(call_fn, "TestProvider")

        assert result.status_code == 200
        assert call_fn.call_count == 2
        mock_sleep.assert_called()

    @patch("app.prediction.llm_client.time.sleep")
    @patch("app.prediction.llm_client.LLM_RETRY_MAX_ATTEMPTS", 3)
    @patch("app.prediction.llm_client.LLM_RETRY_BACKOFF_FACTOR", 1)
    def test_retry_on_timeout_then_success(self, mock_sleep):
        """首次 RequestException(超时) → 重试成功。"""
        resp_ok = MagicMock(status_code=200, text="ok")
        call_fn = MagicMock(side_effect=[requests.Timeout("timeout"), resp_ok])

        result = _call_with_retry(call_fn, "TestProvider")

        assert result.status_code == 200
        assert call_fn.call_count == 2

    @patch("app.prediction.llm_client.time.sleep")
    @patch("app.prediction.llm_client.LLM_RETRY_MAX_ATTEMPTS", 3)
    @patch("app.prediction.llm_client.LLM_RETRY_BACKOFF_FACTOR", 1)
    def test_no_retry_on_401(self, mock_sleep):
        """401 Unauthorized 不重试，直接返回。"""
        resp_401 = MagicMock(status_code=401, text="unauthorized")
        call_fn = MagicMock(return_value=resp_401)

        result = _call_with_retry(call_fn, "TestProvider")

        assert result.status_code == 401
        assert call_fn.call_count == 1
        mock_sleep.assert_not_called()

    @patch("app.prediction.llm_client.time.sleep")
    @patch("app.prediction.llm_client.LLM_RETRY_MAX_ATTEMPTS", 3)
    @patch("app.prediction.llm_client.LLM_RETRY_BACKOFF_FACTOR", 1)
    def test_no_retry_on_403(self, mock_sleep):
        """403 Forbidden 不重试。"""
        resp_403 = MagicMock(status_code=403, text="forbidden")
        call_fn = MagicMock(return_value=resp_403)

        result = _call_with_retry(call_fn, "TestProvider")

        assert result.status_code == 403
        assert call_fn.call_count == 1

    @patch("app.prediction.llm_client.time.sleep")
    @patch("app.prediction.llm_client.LLM_RETRY_MAX_ATTEMPTS", 3)
    @patch("app.prediction.llm_client.LLM_RETRY_BACKOFF_FACTOR", 1)
    def test_no_retry_on_400(self, mock_sleep):
        """400 Bad Request 不重试。"""
        resp_400 = MagicMock(status_code=400, text="bad")
        call_fn = MagicMock(return_value=resp_400)

        result = _call_with_retry(call_fn, "TestProvider")

        assert result.status_code == 400
        assert call_fn.call_count == 1

    @patch("app.prediction.llm_client.time.sleep")
    @patch("app.prediction.llm_client.LLM_RETRY_MAX_ATTEMPTS", 3)
    @patch("app.prediction.llm_client.LLM_RETRY_BACKOFF_FACTOR", 1)
    def test_permanent_500_exhausts_retries(self, mock_sleep):
        """持续 500 错误：用完所有重试后返回最后一次 response。"""
        resp_500 = MagicMock(status_code=500, text="server error")
        call_fn = MagicMock(return_value=resp_500)

        result = _call_with_retry(call_fn, "TestProvider")

        assert result.status_code == 500
        assert call_fn.call_count == 3  # 3 attempts total

    @patch("app.prediction.llm_client.time.sleep")
    @patch("app.prediction.llm_client.LLM_RETRY_MAX_ATTEMPTS", 3)
    @patch("app.prediction.llm_client.LLM_RETRY_BACKOFF_FACTOR", 1)
    def test_permanent_timeout_exhausts_retries(self, mock_sleep):
        """持续超时：用完所有重试后抛出 RequestException。"""
        call_fn = MagicMock(side_effect=requests.Timeout("timeout"))

        with pytest.raises(requests.Timeout):
            _call_with_retry(call_fn, "TestProvider")

        assert call_fn.call_count == 3

    @patch("app.prediction.llm_client.time.sleep")
    @patch("app.prediction.llm_client.LLM_RETRY_MAX_ATTEMPTS", 3)
    @patch("app.prediction.llm_client.LLM_RETRY_BACKOFF_FACTOR", 1)
    def test_429_retry_on_rate_limit(self, mock_sleep):
        """429 Too Many Requests 可重试。"""
        resp_429 = MagicMock(status_code=429, text="rate limited")
        resp_ok = MagicMock(status_code=200, text="ok")
        call_fn = MagicMock(side_effect=[resp_429, resp_ok])

        result = _call_with_retry(call_fn, "TestProvider")

        assert result.status_code == 200
        assert call_fn.call_count == 2

    @patch("app.prediction.llm_client.time.sleep")
    @patch("app.prediction.llm_client.LLM_RETRY_MAX_ATTEMPTS", 3)
    @patch("app.prediction.llm_client.LLM_RETRY_BACKOFF_FACTOR", 1)
    def test_408_retry_on_client_timeout(self, mock_sleep):
        """408 Client Timeout 可重试。"""
        resp_408 = MagicMock(status_code=408, text="timeout")
        resp_ok = MagicMock(status_code=200, text="ok")
        call_fn = MagicMock(side_effect=[resp_408, resp_ok])

        result = _call_with_retry(call_fn, "TestProvider")

        assert result.status_code == 200
        assert call_fn.call_count == 2


# ============================================================================
# JSON 解析 helpers
# ============================================================================


class TestJsonParsing:
    """JSON 提取与修复 helpers。"""

    def test_extract_all_balanced_json_objects_single(self):
        """单个 JSON 对象能被正确提取。"""
        text = '{"a": 1, "b": 2}'
        blocks = _extract_all_balanced_json_objects(text)
        assert len(blocks) == 1
        assert json.loads(blocks[0]) == {"a": 1, "b": 2}

    def test_extract_all_balanced_json_objects_multiple(self):
        """多个 JSON 块能被全部提取（长按长度降序排列）。"""
        text = 'prefix {"small": 1} middle {"big": {"nested": true}, "extra": [1,2,3]}'
        blocks = _extract_all_balanced_json_objects(text)
        assert len(blocks) == 2
        # 最长的在前
        assert len(blocks[0]) >= len(blocks[1])

    def test_extract_all_balanced_json_objects_nested(self):
        """嵌套 JSON 能被正确处理。"""
        text = '{"outer": {"inner": {"deep": true}}}'
        blocks = _extract_all_balanced_json_objects(text)
        assert len(blocks) == 1
        parsed = json.loads(blocks[0])
        assert parsed["outer"]["inner"]["deep"] is True

    def test_extract_all_balanced_json_objects_with_strings(self):
        """JSON 字符串内的大括号不被误判。"""
        text = '{"msg": "hello {world}", "val": 1}'
        blocks = _extract_all_balanced_json_objects(text)
        assert len(blocks) == 1
        parsed = json.loads(blocks[0])
        assert parsed["msg"] == "hello {world}"

    def test_extract_all_balanced_json_objects_empty_input(self):
        """空输入返回空列表。"""
        assert _extract_all_balanced_json_objects("") == []
        assert _extract_all_balanced_json_objects("no json here") == []

    def test_close_json_candidate_truncated_object(self):
        """截断的 JSON 对象能被自动闭合。"""
        text = '{"a": 1, "b": "hello"'
        closed = _close_json_candidate(text)
        # 应该能成功解析
        parsed = json.loads(closed)
        assert parsed["a"] == 1
        assert parsed["b"] == "hello"

    def test_close_json_candidate_truncated_nested(self):
        """截断的嵌套对象能被正确闭合。"""
        text = '{"a": {"b": 1}'
        closed = _close_json_candidate(text)
        parsed = json.loads(closed)
        assert parsed["a"]["b"] == 1

    def test_close_json_candidate_with_open_string(self):
        """截断在字符串内部时能正确闭合。"""
        text = '{"a": "hello'
        closed = _close_json_candidate(text)
        parsed = json.loads(closed)
        assert parsed["a"] == "hello"

    def test_close_json_candidate_empty(self):
        """空输入原样返回。"""
        assert _close_json_candidate("") == ""

    def test_cleanup_json_candidate_trailing_comma(self):
        """清除尾逗号。"""
        text = '{"a": 1, "b": 2,}'
        cleaned = _cleanup_json_candidate(text)
        parsed = json.loads(cleaned)
        assert parsed == {"a": 1, "b": 2}

    def test_cleanup_json_candidate_bom(self):
        """清除 BOM 字符。"""
        text = '\ufeff{"a": 1}'
        cleaned = _cleanup_json_candidate(text)
        assert not cleaned.startswith("\ufeff")
        parsed = json.loads(cleaned)
        assert parsed["a"] == 1


# ============================================================================
# LLMResponse.parse_json
# ============================================================================


class TestLLMResponseParseJson:
    """LLMResponse.parse_json 从 content/reasoning 字段解析 JSON。"""

    def test_parse_json_from_content_field(self):
        """正常 JSON 在 content 字段。"""
        resp = LLMResponse(content='{"home_win_prob": 60}')
        parsed = resp.parse_json()
        assert parsed["home_win_prob"] == 60

    def test_parse_json_from_reasoning_field(self):
        """JSON 在 reasoning 字段（content 无 JSON 时回退）。"""
        resp = LLMResponse(content="some thinking text", reasoning='{"home_win_prob": 70}')
        parsed = resp.parse_json()
        assert parsed["home_win_prob"] == 70

    def test_parse_json_with_thinking_tags(self):
        """被 <thinking> 包裹的 JSON 能被提取。"""
        text = '<thinking>let me think...</thinking>\n{"home_win_prob": 55}'
        resp = LLMResponse(content=text)
        parsed = resp.parse_json()
        assert parsed["home_win_prob"] == 55

    def test_parse_json_with_code_fence(self):
        """代码围栏包裹的 JSON 能被提取。"""
        text = '```json\n{"home_win_prob": 80}\n```'
        resp = LLMResponse(content=text)
        parsed = resp.parse_json()
        assert parsed["home_win_prob"] == 80

    def test_repair_truncated_json(self):
        """截断的 JSON 能被修复后解析。"""
        text = '{"home_win_prob": 60, "draw_prob": 25'
        resp = LLMResponse(content=text)
        parsed = resp.parse_json()
        assert parsed["home_win_prob"] == 60

    def test_no_json_found_raises_llmerror(self):
        """完全找不到 JSON 时抛出 LLMError。"""
        resp = LLMResponse(content="no json here at all")
        with pytest.raises(LLMError, match="JSON 解析失败"):
            resp.parse_json()

    def test_empty_content_raises_llmerror(self):
        """空 content 抛出 LLMError。"""
        resp = LLMResponse(content="", reasoning="")
        with pytest.raises(LLMError, match="模型返回内容为空"):
            resp.parse_json()


# ============================================================================
# _message_text / _strip_code_fences / _extract_fenced_blocks
# ============================================================================


class TestHelpers:
    """辅助函数测试。"""

    def test_message_text_string(self):
        """字符串输入原样返回。"""
        assert _message_text("hello") == "hello"

    def test_message_text_none(self):
        """None 返回空字符串。"""
        assert _message_text(None) == ""

    def test_message_text_list_of_strings(self):
        """字符串列表拼接。"""
        assert _message_text(["hello", "world"]) == "hello\nworld"

    def test_message_text_list_of_dicts(self):
        """字典列表提取 text 字段。"""
        items = [{"type": "text", "text": "foo"}, {"type": "text", "text": "bar"}]
        result = _message_text(items)
        assert "foo" in result
        assert "bar" in result

    def test_message_text_dict(self):
        """字典输入取 content/text 字段。"""
        assert _message_text({"text": "hello"}) == "hello"
        assert _message_text({"content": "world"}) == "world"

    def test_strip_code_fences(self):
        """代码围栏标记被移除。"""
        text = '```json\n{"a": 1}\n```'
        result = _strip_code_fences(text)
        assert result == '{"a": 1}'

    def test_strip_code_fences_no_fences(self):
        """无围栏的文本原样返回。"""
        assert _strip_code_fences('{"a": 1}') == '{"a": 1}'

    def test_extract_fenced_blocks(self):
        """提取代码围栏内的内容。"""
        text = 'prefix ```json\n{"a": 1}\n``` suffix ```json\n{"b": 2}\n```'
        blocks = _extract_fenced_blocks(text)
        assert len(blocks) == 2
        assert json.loads(blocks[0]) == {"a": 1}
        assert json.loads(blocks[1]) == {"b": 2}

    def test_extract_mermaid_block_fenced(self):
        """围栏包裹的 mermaid 块。"""
        text = '```mermaid\nmindmap\n  root(A)\n```'
        result = extract_mermaid_block(text)
        assert result is not None
        assert "mindmap" in result
        assert result.startswith("```mermaid")

    def test_extract_mermaid_block_raw(self):
        """未围栏的 raw mermaid 块。"""
        text = 'some text\nmindmap root(A)\n  child(B)'
        result = extract_mermaid_block(text)
        assert result is not None
        assert "mindmap" in result

    def test_extract_mermaid_block_none(self):
        """无 mermaid 返回 None。"""
        assert extract_mermaid_block("no mermaid here") is None
        assert extract_mermaid_block("") is None
        assert extract_mermaid_block(None) is None
