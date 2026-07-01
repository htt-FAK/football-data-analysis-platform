"""独立联网搜索模块 —— 作为实时情报来源，喂给 LLM 做赛前分析。

为什么独立：阶跃 step-3.7-flash 的原生 web_search 工具依赖账号开通，
不一定可用。这里用独立的搜索 API（Tavily/Serper）先搜出实时新闻，
再把结果作为 context 注入 prompt，保证「实时场外情报」这条链路稳定。

provider 通过 WEB_SEARCH_PROVIDER 切换：tavily / serper / none。
"""

from __future__ import annotations

import logging
from typing import Protocol

import requests

from app.config import (
    SERPER_API_KEY,
    SERPER_BASE_URL,
    TAVILY_API_KEY,
    TAVILY_BASE_URL,
    WEB_SEARCH_MAX_RESULTS,
    WEB_SEARCH_PROVIDER,
    WEB_SEARCH_TIMEOUT,
)

logger = logging.getLogger(__name__)


class SearchError(Exception):
    """联网搜索异常。"""


class SearchResult(dict):
    """统一搜索结果：{title, url, content, images}。

    images 为可选字段，列表元素形如 {"url": ..., "description": ...}。
    """

    @property
    def title(self) -> str:
        return self.get("title", "")

    @property
    def url(self) -> str:
        return self.get("url", "")

    @property
    def content(self) -> str:
        return self.get("content", "")

    @property
    def images(self) -> list[dict]:
        return self.get("images", []) or []


class WebSearchProvider(Protocol):
    """搜索 provider 接口。"""

    def search(self, query: str, max_results: int = WEB_SEARCH_MAX_RESULTS, include_images: bool = False) -> list[SearchResult]:
        ...


# ─────────────────────────────────────────────────────────────────────────────
# Tavily
# ─────────────────────────────────────────────────────────────────────────────
class TavilyProvider:
    """Tavily 搜索（专为 LLM 设计，返回结构化 title/url/content）。"""

    def __init__(self, api_key: str = "", base_url: str = "", timeout: int = 0):
        self.api_key = api_key or TAVILY_API_KEY
        self.base_url = (base_url or TAVILY_BASE_URL).rstrip("/")
        self.timeout = timeout or WEB_SEARCH_TIMEOUT
        if not self.api_key:
            raise SearchError("TAVILY_API_KEY 未配置")

    def search(self, query: str, max_results: int = WEB_SEARCH_MAX_RESULTS, include_images: bool = False) -> list[SearchResult]:
        url = f"{self.base_url}/search"
        # Tavily 用 Bearer token
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        body: dict = {
            "query": query,
            "max_results": max_results,
            # include_raw_content 太长，用 content 摘要即可
            "search_depth": "basic",
            "topic": "general",
        }
        if include_images:
            body["include_images"] = True
            body["include_image_descriptions"] = True
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=self.timeout)
        except requests.RequestException as exc:
            raise SearchError(f"Tavily 请求失败: {exc}") from exc
        if resp.status_code >= 400:
            raise SearchError(f"Tavily 返回 HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise SearchError(f"Tavily 响应非 JSON: {exc}") from exc

        # 顶层 images 数组（每项含 url + description）
        top_images: list[dict] = []
        if include_images:
            for img in (payload.get("images") or []):
                if isinstance(img, str):
                    top_images.append({"url": img, "description": ""})
                elif isinstance(img, dict):
                    top_images.append({
                        "url": img.get("url") or "",
                        "description": img.get("description") or "",
                    })

        results: list[SearchResult] = []
        for item in (payload.get("results") or [])[:max_results]:
            # 每个 result 可能也带 images 数组
            item_images: list[dict] = []
            if include_images:
                for img in (item.get("images") or []):
                    if isinstance(img, str):
                        item_images.append({"url": img, "description": ""})
                    elif isinstance(img, dict):
                        item_images.append({
                            "url": img.get("url") or "",
                            "description": img.get("description") or "",
                        })
            results.append(SearchResult(
                title=item.get("title") or "",
                url=item.get("url") or "",
                content=item.get("content") or "",
                images=item_images,
            ))
        # 把顶层图片挂到第一条结果上（便于视觉分析统一收集）
        if top_images and results:
            first = dict(results[0])
            existing = list(first.get("images") or [])
            first["images"] = existing + top_images
            results[0] = SearchResult(first)
        logger.info(
            "Tavily 搜索 '%s' 命中 %d 条%s",
            query, len(results),
            f"，含 {len(top_images)} 张顶层图片" if include_images else "",
        )
        return results


# ─────────────────────────────────────────────────────────────────────────────
# Serper (Google)
# ─────────────────────────────────────────────────────────────────────────────
class SerperProvider:
    """Serper.dev 搜索（Google 结果代理）。"""

    def __init__(self, api_key: str = "", base_url: str = "", timeout: int = 0):
        self.api_key = api_key or SERPER_API_KEY
        self.base_url = (base_url or SERPER_BASE_URL).rstrip("/")
        self.timeout = timeout or WEB_SEARCH_TIMEOUT
        if not self.api_key:
            raise SearchError("SERPER_API_KEY 未配置")

    def search(self, query: str, max_results: int = WEB_SEARCH_MAX_RESULTS, include_images: bool = False) -> list[SearchResult]:
        url = f"{self.base_url}/search"
        headers = {"Content-Type": "application/json", "X-API-KEY": self.api_key}
        body = {"q": query, "num": max_results}
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=self.timeout)
        except requests.RequestException as exc:
            raise SearchError(f"Serper 请求失败: {exc}") from exc
        if resp.status_code >= 400:
            raise SearchError(f"Serper 返回 HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise SearchError(f"Serper 响应非 JSON: {exc}") from exc

        results: list[SearchResult] = []
        # Serper 返回 organic / news / knowledgeGraph 等多种
        for item in (payload.get("organic") or [])[:max_results]:
            results.append(SearchResult(
                title=item.get("title") or "",
                url=item.get("link") or "",
                content=item.get("snippet") or "",
            ))
        for item in (payload.get("news") or [])[:max_results]:
            results.append(SearchResult(
                title=item.get("title") or "",
                url=item.get("link") or "",
                content=item.get("snippet") or item.get("date") or "",
            ))
        logger.info("Serper 搜索 '%s' 命中 %d 条", query, len(results))
        return results


# ─────────────────────────────────────────────────────────────────────────────
# 工厂
# ─────────────────────────────────────────────────────────────────────────────
_PROVIDER_CACHE: dict[str, WebSearchProvider | None] = {}


def get_search_provider(provider: str = "") -> WebSearchProvider | None:
    """按 WEB_SEARCH_PROVIDER 获取已配置的 provider；未配置或 none 返回 None。

    结果缓存：同一进程内只初始化一次。key 缺失时抛 SearchError 由调用方降级。
    """
    name = (provider or WEB_SEARCH_PROVIDER).lower()
    if name in {"", "none", "disabled", "off"}:
        return None
    if name in _PROVIDER_CACHE:
        return _PROVIDER_CACHE[name]
    try:
        if name == "tavily":
            provider_obj: WebSearchProvider = TavilyProvider()
        elif name == "serper":
            provider_obj = SerperProvider()
        else:
            logger.warning("未知 WEB_SEARCH_PROVIDER=%s，联网搜索禁用", name)
            _PROVIDER_CACHE[name] = None
            return None
    except SearchError as exc:
        logger.warning("联网搜索 provider 初始化失败（%s），本次禁用: %s", name, exc)
        _PROVIDER_CACHE[name] = None
        return None
    _PROVIDER_CACHE[name] = provider_obj
    return provider_obj


def search_safe(query: str, max_results: int = WEB_SEARCH_MAX_RESULTS, include_images: bool = False) -> list[SearchResult]:
    """安全搜索：provider 不可用或出错时返回空列表，不抛异常。"""
    provider = get_search_provider()
    if provider is None:
        return []
    try:
        return provider.search(query, max_results=max_results, include_images=include_images)
    except SearchError as exc:
        logger.warning("联网搜索失败（query=%s）: %s", query, exc)
        return []


def build_intel_block(results: list[SearchResult], heading: str = "实时网络情报") -> str:
    """把搜索结果格式化成 markdown 块，供注入 prompt context。"""
    if not results:
        return ""
    lines = [f"\n# {heading}（来自联网搜索）"]
    for i, r in enumerate(results, 1):
        title = r.title.strip() or "(无标题)"
        url = r.url.strip()
        content = r.content.strip()
        lines.append(f"\n{i}. **{title}**")
        if url:
            lines.append(f"   来源: {url}")
        if content:
            # 截断过长的 content，避免撑爆上下文
            preview = content[:500] + ("..." if len(content) > 500 else "")
            lines.append(f"   摘要: {preview}")
    return "\n".join(lines)


def is_available() -> bool:
    """联网搜索是否可用（provider 已配置且 key 存在）。"""
    return get_search_provider() is not None
