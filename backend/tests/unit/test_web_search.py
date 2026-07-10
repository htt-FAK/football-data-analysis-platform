"""Web Search 单元测试 — 覆盖 Firecrawl 集成 + 搜索安全网 + 格式化。

测试目标:
- FirecrawlProvider.search: 成功/失败/超时/响应映射
- search_safe: 永不抛异常
- get_search_provider: 未知 provider 返回 None
- build_intel_block: markdown 格式化
- is_available: provider 配置检测
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.prediction.web_search import (
    FirecrawlProvider,
    SearchError,
    SearchResult,
    build_intel_block,
    get_search_provider,
    is_available,
    search_safe,
    _PROVIDER_CACHE,
)


# ============================================================================
# FirecrawlProvider
# ============================================================================


class TestFirecrawlProvider:
    """Firecrawl 搜索 provider 行为。"""

    def setup_method(self):
        """每个测试前清空 provider 缓存。"""
        _PROVIDER_CACHE.clear()

    @patch("app.prediction.web_search.requests.post")
    def test_firecrawl_provider_success(self, mock_post):
        """HTTP 200 + 正常返回 → SearchResult 列表。"""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "success": True,
                "data": {
                    "web": [
                        {"title": "News 1", "url": "https://example.com/1", "description": "Summary 1"},
                    ],
                    "images": [],
                },
            }),
        )
        provider = FirecrawlProvider(api_key="test-key", api_base="https://api.firecrawl.dev", timeout=10)
        results = provider.search("test query")

        assert len(results) == 1
        assert results[0].title == "News 1"
        assert results[0].url == "https://example.com/1"
        assert results[0].content == "Summary 1"

    @patch("app.prediction.web_search.requests.post")
    def test_firecrawl_provider_handles_api_error(self, mock_post):
        """HTTP 5xx → SearchError。"""
        mock_post.return_value = MagicMock(status_code=500, text="Internal Server Error")
        provider = FirecrawlProvider(api_key="test-key", api_base="https://api.firecrawl.dev", timeout=10)

        with pytest.raises(SearchError, match="HTTP 500"):
            provider.search("test query")

    @patch("app.prediction.web_search.requests.post")
    def test_firecrawl_provider_handles_timeout(self, mock_post):
        """网络超时 → SearchError。"""
        mock_post.side_effect = requests.Timeout("Connection timed out")
        provider = FirecrawlProvider(api_key="test-key", api_base="https://api.firecrawl.dev", timeout=10)

        with pytest.raises(SearchError, match="请求失败"):
            provider.search("test query")

    @patch("app.prediction.web_search.requests.post")
    def test_firecrawl_maps_response_with_images(self, mock_post):
        """响应含 images 时映射到 SearchResult.images。"""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "success": True,
                "data": {
                    "web": [
                        {"title": "Article", "url": "https://example.com", "markdown": "full text"},
                    ],
                    "images": [
                        {"imageUrl": "https://img.example.com/1.jpg", "title": "Photo 1"},
                    ],
                },
            }),
        )
        provider = FirecrawlProvider(api_key="test-key", api_base="https://api.firecrawl.dev", timeout=10)
        results = provider.search("test query", include_images=True)

        assert len(results) >= 1
        assert len(results[0].images) == 1
        assert results[0].images[0]["url"] == "https://img.example.com/1.jpg"

    @patch("app.prediction.web_search.requests.post")
    def test_firecrawl_news_results_merged(self, mock_post):
        """news 结果合并到返回列表。"""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "success": True,
                "data": {
                    "web": [],
                    "news": [
                        {"title": "Breaking News", "url": "https://news.com/1", "snippet": "News snippet"},
                    ],
                    "images": [],
                },
            }),
        )
        provider = FirecrawlProvider(api_key="test-key", api_base="https://api.firecrawl.dev", timeout=10)
        results = provider.search("test query")

        assert len(results) == 1
        assert results[0].title == "Breaking News"
        assert results[0].content == "News snippet"

    @patch("app.prediction.web_search.requests.post")
    def test_firecrawl_headers_with_key(self, mock_post):
        """有 API key 时 Authorization header 被设置。"""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"success": True, "data": {"web": [], "images": []}}),
        )
        provider = FirecrawlProvider(api_key="my-secret-key", api_base="https://api.firecrawl.dev", timeout=10)
        provider.search("test")

        call_kwargs = mock_post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer my-secret-key"

    @patch("app.prediction.web_search.requests.post")
    def test_firecrawl_headers_without_key(self, mock_post):
        """无 API key 时 Authorization header 不被设置（keyless 免费层）。"""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"success": True, "data": {"web": [], "images": []}}),
        )
        provider = FirecrawlProvider(api_key="", api_base="https://api.firecrawl.dev", timeout=10)
        provider.search("test")

        call_kwargs = mock_post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert "Authorization" not in headers


# ============================================================================
# search_safe / get_search_provider / is_available
# ============================================================================


class TestSearchSafeAndFactory:
    """search_safe 安全网 + provider 工厂。"""

    def setup_method(self):
        """每个测试前清空 provider 缓存。"""
        _PROVIDER_CACHE.clear()

    @patch("app.prediction.web_search.get_search_provider")
    def test_search_safe_returns_empty_on_provider_none(self, mock_get_provider):
        """provider 不可用时返回空列表。"""
        mock_get_provider.return_value = None
        results = search_safe("test query")
        assert results == []

    @patch("app.prediction.web_search.get_search_provider")
    def test_search_safe_returns_empty_on_failure(self, mock_get_provider):
        """搜索失败时返回空列表，不抛异常。"""
        mock_provider = MagicMock()
        mock_provider.search.side_effect = SearchError("failed")
        mock_get_provider.return_value = mock_provider

        results = search_safe("test query")
        assert results == []

    @patch("app.prediction.web_search.WEB_SEARCH_PROVIDER", "none")
    def test_get_search_provider_returns_none_for_disabled(self):
        """WEB_SEARCH_PROVIDER=none 时返回 None。"""
        _PROVIDER_CACHE.clear()
        provider = get_search_provider()
        assert provider is None

    @patch("app.prediction.web_search.WEB_SEARCH_PROVIDER", "unknown_provider")
    def test_get_search_provider_returns_none_for_unknown(self):
        """未知 provider 返回 None。"""
        _PROVIDER_CACHE.clear()
        provider = get_search_provider()
        assert provider is None

    @patch("app.prediction.web_search.get_search_provider")
    def test_is_available_true(self, mock_get_provider):
        """provider 存在时 is_available 返回 True。"""
        mock_get_provider.return_value = MagicMock()
        assert is_available() is True

    @patch("app.prediction.web_search.get_search_provider")
    def test_is_available_false(self, mock_get_provider):
        """provider 不存在时 is_available 返回 False。"""
        mock_get_provider.return_value = None
        assert is_available() is False


# ============================================================================
# build_intel_block
# ============================================================================


class TestBuildIntelBlock:
    """搜索结果 markdown 格式化。"""

    def test_build_intel_block_formats_correctly(self):
        """格式化搜索结果列表为 markdown。"""
        results = [
            SearchResult(title="Match Preview", url="https://example.com/1", content="Preview text"),
            SearchResult(title="Injury Report", url="https://example.com/2", content="Player X injured"),
        ]
        block = build_intel_block(results, heading="实时网络情报")
        assert "# 实时网络情报" in block
        assert "Match Preview" in block
        assert "https://example.com/1" in block
        assert "Injury Report" in block

    def test_build_intel_block_empty_results(self):
        """空列表返回空字符串。"""
        assert build_intel_block([]) == ""

    def test_build_intel_block_truncates_long_content(self):
        """超过 500 字符的 content 被截断。"""
        long_content = "a" * 600
        results = [SearchResult(title="Long", url="", content=long_content)]
        block = build_intel_block(results)
        assert "..." in block
