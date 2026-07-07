"""独立联网搜索模块 —— 作为实时情报来源，喂给 LLM 做赛前分析。

为什么独立：阶跃 step-3.7-flash 的原生 web_search 工具依赖账号开通，
不一定可用。这里用独立的搜索链路（Firecrawl Search API）先搜出实时新闻，
再把结果作为 context 注入 prompt，保证「实时场外情报」这条链路稳定。

provider 通过 WEB_SEARCH_PROVIDER 切换：firecrawl / none。

Firecrawl Search（https://firecrawl.dev，官方，有免费层）：
  - 免 Key：不带 Authorization 直接调 /v2/search（按出口 IP 限流，需 IPv4 且非代理）
  - 有 Key：填 FIRECRAWL_API_KEY（1000 credits/月免费额度），更高限额
返回 {success, data:{web[], images[], news[]}, creditsUsed, id}，
web 项含 {title, url, description, markdown?}，images 项含 {title, imageUrl, url}。
"""

from __future__ import annotations

import logging
from typing import Protocol

import requests

from app.config import (
    FIRECRAWL_API_BASE,
    FIRECRAWL_API_KEY,
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
# Firecrawl Search（REST /v2/search，官方，有免费层）
# ─────────────────────────────────────────────────────────────────────────────
class FirecrawlProvider:
    """Firecrawl Search provider（直连 /v2/search）。

    有 Key 用 Key（1000 credits/月免费额度，更高限额）；无 Key 走 keyless
    免费层（不带 Authorization，按出口 IP 限流，需 IPv4 且非代理/VPN）。
    返回结构统一 {title, url, content, images}，与调用方契约一致。
    """

    def __init__(self, api_key: str = "", api_base: str = "", timeout: int = 0):
        self.api_key = api_key or FIRECRAWL_API_KEY
        self.api_base = (api_base or FIRECRAWL_API_BASE).rstrip("/")
        self.timeout = timeout or WEB_SEARCH_TIMEOUT

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        # 有 Key 才带 Authorization；无 Key 时不带 → 触发 keyless 免费层
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def search(self, query: str, max_results: int = WEB_SEARCH_MAX_RESULTS, include_images: bool = False) -> list[SearchResult]:
        url = f"{self.api_base}/v2/search"
        sources: list[dict] = [{"type": "web"}]
        if include_images:
            sources.append({"type": "images"})
        body: dict = {"query": query, "limit": max_results, "sources": sources}

        try:
            resp = requests.post(url, headers=self._headers(), json=body, timeout=self.timeout)
        except requests.RequestException as exc:
            raise SearchError(f"Firecrawl 请求失败: {exc}") from exc
        if resp.status_code >= 400:
            raise SearchError(f"Firecrawl 返回 HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise SearchError(f"Firecrawl 响应非 JSON: {exc}") from exc
        if not payload.get("success", True):
            raise SearchError(f"Firecrawl 搜索失败: {payload.get('error') or payload}")

        results = self._build_results(payload, max_results, include_images)
        logger.info(
            "Firecrawl 搜索 '%s' 命中 %d 条%s",
            query, len(results),
            "，含图片" if include_images else "",
        )
        return results

    @staticmethod
    def _build_results(payload: dict, max_results: int, include_images: bool) -> list[SearchResult]:
        data = payload.get("data") or {}
        results: list[SearchResult] = []

        for item in (data.get("web") or [])[:max_results]:
            results.append(SearchResult(
                title=item.get("title") or "",
                url=item.get("url") or "",
                # 带 scrapeOptions 时才有 markdown；否则用 description 摘要
                content=item.get("markdown") or item.get("description") or "",
                images=[],
            ))

        # news 结果并入（部分查询 Firecrawl 会返回新闻）
        for item in (data.get("news") or [])[:max_results]:
            results.append(SearchResult(
                title=item.get("title") or "",
                url=item.get("url") or "",
                content=item.get("snippet") or item.get("description") or item.get("date") or "",
                images=[],
            ))

        # 图片结果：转成 {url, description} 挂到第一条结果的 images 上，
        # 与 media.extract_image_urls 读取的字段格式保持一致
        if include_images:
            imgs: list[dict] = []
            for img in (data.get("images") or []):
                img_url = img.get("imageUrl") or img.get("url") or ""
                if not img_url:
                    continue
                imgs.append({"url": img_url, "description": img.get("title") or ""})
            if imgs:
                if results:
                    first = dict(results[0])
                    first["images"] = list(first.get("images") or []) + imgs
                    results[0] = SearchResult(first)
                else:
                    results.append(SearchResult(title="", url="", content="", images=imgs))

        return results


# ─────────────────────────────────────────────────────────────────────────────
# 工厂
# ─────────────────────────────────────────────────────────────────────────────
_PROVIDER_CACHE: dict[str, WebSearchProvider | None] = {}


def get_search_provider(provider: str = "") -> WebSearchProvider | None:
    """按 WEB_SEARCH_PROVIDER 获取已配置的 provider；未配置或 none 返回 None。

    结果缓存：同一进程内只初始化一次。Firecrawl 免 Key 版无需任何密钥即可用。
    """
    name = (provider or WEB_SEARCH_PROVIDER).lower()
    if name in {"", "none", "disabled", "off"}:
        return None
    if name in _PROVIDER_CACHE:
        return _PROVIDER_CACHE[name]
    try:
        if name == "firecrawl":
            provider_obj: WebSearchProvider = FirecrawlProvider()
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
    """联网搜索是否可用（provider 已配置）。"""
    return get_search_provider() is not None
