"""共享测试 fixtures — 所有测试文件的公共依赖。

策略：
- DB Session 用 MagicMock，不连接真实数据库
- HTTP 用 patch('requests.post') 返回预设 response
- LLM 调用返回 mock LLMResponse
- Firecrawl 用 patch
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# 让测试能找到 app.* 模块（backend/ 根目录加入 sys.path）
_backend_root = str(Path(__file__).resolve().parents[1])
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)


# ── 通用 fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_db_session():
    """模拟 SQLAlchemy Session，隔离数据库依赖。"""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.refresh = MagicMock()
    return session


@pytest.fixture
def fake_llm_response():
    """构造一个典型的 LLMResponse mock，包含合法 JSON content。"""
    from app.prediction.llm_client import LLMResponse

    return LLMResponse(
        content='{"home_win_prob": 60, "draw_prob": 25, "away_win_prob": 15}',
        reasoning="",
        search_results=[],
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500,
        cost_ms=2000,
        raw={"choices": [{"message": {"content": "..."}}]},
    )


@pytest.fixture
def fake_http_200():
    """构造一个 requests.Response mock，状态码 200。"""
    resp = MagicMock()
    resp.status_code = 200
    resp.text = '{"choices": [{"message": {"content": "{}", "reasoning_content": ""}}], "usage": {}}'
    resp.json.return_value = {
        "choices": [{"message": {"content": "{}", "reasoning_content": ""}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }
    return resp
