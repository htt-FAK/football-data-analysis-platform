"""LLM clients for AI match prediction."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import requests

from app.config import (
    AI_REASONING_EFFORT,
    AI_REQUEST_TIMEOUT,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    STEPFUN_API_KEY,
    STEPFUN_BASE_URL,
    STEPFUN_MODEL,
    STEPFUN_VISION_MODEL,
)

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when an LLM request or response cannot be used safely."""


def _message_text(value: Any) -> str:
    """Flatten OpenAI-compatible message content into plain text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))
                elif "text" in item:
                    parts.append(str(item.get("text") or ""))
                elif "content" in item:
                    parts.append(str(item.get("content") or ""))
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        return str(value.get("text") or value.get("content") or "")
    return str(value)


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        stripped = re.sub(r"^```[A-Za-z0-9_-]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _extract_fenced_blocks(text: str) -> list[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(r"```(?:json|JSON)?\s*(.*?)```", text, re.DOTALL)
        if match.group(1).strip()
    ]


def _extract_balanced_json(text: str) -> str:
    start = text.find("{")
    if start < 0:
        return ""

    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        char = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]

    return text[start:].strip()


def _cleanup_json_candidate(text: str) -> str:
    cleaned = text.strip().lstrip("\ufeff")
    cleaned = cleaned.replace("\r\n", "\n")
    cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
    return cleaned.strip()


def _close_json_candidate(text: str) -> str:
    """Try to close a truncated JSON object or array."""
    chars = list(text.rstrip())
    if not chars:
        return text

    stack: list[str] = []
    in_string = False
    escaped = False
    for char in chars:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            stack.append("}")
        elif char == "[":
            stack.append("]")
        elif char in "}]":
            if stack and stack[-1] == char:
                stack.pop()

    repaired = "".join(chars)
    if in_string:
        repaired += '"'
    while stack:
        repaired += stack.pop()
    return repaired


def _candidate_json_texts(text: str) -> list[str]:
    seen: set[str] = set()
    candidates: list[str] = []

    def add(value: str) -> None:
        normalized = _cleanup_json_candidate(_strip_code_fences(value))
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        candidates.append(normalized)

    add(text)
    for block in _extract_fenced_blocks(text):
        add(block)
    balanced = _extract_balanced_json(text)
    if balanced:
        add(balanced)
    return candidates


def extract_mermaid_block(text: str) -> str | None:
    match = re.search(r"```mermaid\s*(.*?)```", text or "", re.DOTALL | re.IGNORECASE)
    if match:
        body = match.group(1).strip()
        return f"```mermaid\n{body}\n```"

    raw_match = re.search(r"(mindmap\s+root\(.*)", text or "", re.DOTALL | re.IGNORECASE)
    if raw_match:
        body = raw_match.group(1).strip()
        return f"```mermaid\n{body}\n```"
    return None


class LLMResponse:
    """Normalized LLM response wrapper."""

    def __init__(
        self,
        content: str,
        reasoning: str = "",
        search_results: list[dict] | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        cost_ms: int = 0,
        raw: dict | None = None,
    ):
        self.content = content
        self.reasoning = reasoning
        self.search_results = search_results or []
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.cost_ms = cost_ms
        self.raw = raw

    def parse_json(self) -> dict:
        """Extract and parse the most likely JSON payload from content or reasoning."""
        sources = [
            ("content", _message_text(self.content)),
            ("reasoning", _message_text(self.reasoning)),
        ]
        errors: list[str] = []

        for source_name, raw_text in sources:
            if not raw_text.strip():
                continue
            for candidate in _candidate_json_texts(raw_text):
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError as exc:
                    repaired = _cleanup_json_candidate(_close_json_candidate(candidate))
                    if repaired != candidate:
                        try:
                            return json.loads(repaired)
                        except json.JSONDecodeError:
                            pass
                    errors.append(f"{source_name}: {exc}; snippet={candidate[:220]}")

        preview = (_message_text(self.content).strip() or _message_text(self.reasoning).strip())[:220]
        if not preview:
            raise LLMError("模型返回内容为空，无法解析 JSON")
        raise LLMError("JSON 解析失败: " + " | ".join(errors[:3]))


def _extract_search_results(payload: dict) -> list[dict]:
    """Extract search citations from a StepFun response if available."""
    results: list[dict] = []
    try:
        choices = payload.get("choices") or []
        if not choices:
            return results
        message = choices[0].get("message") or {}
        for key in ("search_results", "annotations", "citations"):
            items = message.get(key)
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        results.append(
                            {
                                "title": item.get("title") or item.get("text") or "",
                                "url": item.get("url") or item.get("link") or item.get("cite") or "",
                                "snippet": item.get("snippet") or item.get("content") or "",
                            }
                        )

        for tool_call in message.get("tool_calls") or []:
            if not isinstance(tool_call, dict):
                continue
            func = tool_call.get("function") or {}
            # 官方结构：function.results 是数组，每项含 url/title/summary
            raw_results = func.get("results")
            if isinstance(raw_results, list):
                for item in raw_results:
                    if isinstance(item, dict):
                        results.append(
                            {
                                "title": item.get("title") or "",
                                "url": item.get("url") or item.get("link") or "",
                                "snippet": item.get("summary") or item.get("snippet") or item.get("content") or "",
                            }
                        )
            # 兜底：从 arguments（含 keyword）补一条搜索意图记录
            args = func.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = None
            if isinstance(args, dict) and args.get("keyword") and not raw_results:
                results.append({"title": f"搜索: {args['keyword']}", "url": "", "snippet": ""})
    except Exception as exc:  # noqa: BLE001
        logger.debug("提取搜索结果失败: %s", exc)

    deduped: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for result in results:
        key = (result.get("title") or "", result.get("url") or "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


class StepFunClient:
    """StepFun chat client with optional web_search support."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        reasoning_effort: str = "",
        timeout: int = 0,
    ):
        self.api_key = api_key or STEPFUN_API_KEY
        self.base_url = (base_url or STEPFUN_BASE_URL).rstrip("/")
        self.model = model or STEPFUN_MODEL
        self.reasoning_effort = reasoning_effort or AI_REASONING_EFFORT
        self.timeout = timeout or AI_REQUEST_TIMEOUT
        if not self.api_key:
            raise LLMError("STEPFUN_API_KEY 未配置，无法调用 StepFun 模型")

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        enable_search: bool = True,
        json_mode: bool = False,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        # reasoning_effort=none 时不传该字段（官方 web_search 示例即不传）
        if self.reasoning_effort and self.reasoning_effort.lower() != "none":
            body["reasoning_effort"] = self.reasoning_effort
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if enable_search:
            body["tools"] = [
                {
                    "type": "web_search",
                    "function": {
                        "description": "搜索足球比赛实时情报、新闻、采访、天气、阵容、伤病等信息"
                    },
                }
            ]
            body["tool_choice"] = "auto"
        return self._post(body, enable_search=enable_search, provider_name="StepFun")

    def chat_multimodal(
        self,
        system_prompt: str,
        user_prompt: str,
        image_urls: list[str] | None = None,
        video_urls: list[str] | None = None,
        vision_model: str = "",
        detail: str = "high",
        enable_search: bool = False,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """调用多模态模型理解图片/视频。

        - 图片：用 step-1o-turbo-vision（视觉强项），content 用 image_url 类型
        - 视频：用 step-3.7-flash（原生支持 video_url），content 用 video_url 类型
        二者可同时传入（混排）。detail=high 获取更完整信息（token 消耗更大）。
        """
        model = vision_model or STEPFUN_VISION_MODEL
        # 有视频时强制用 step-3.7-flash（原生 video_url 支持）
        if video_urls:
            model = "step-3.7-flash"

        content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
        for url in image_urls or []:
            content.append({"type": "image_url", "image_url": {"url": url, "detail": detail}})
        for url in video_urls or []:
            content.append({"type": "video_url", "video_url": {"url": url}})

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ]
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        # reasoning_effort=none 时不传该字段
        if self.reasoning_effort and self.reasoning_effort.lower() != "none":
            body["reasoning_effort"] = self.reasoning_effort
        if enable_search:
            body["tools"] = [
                {
                    "type": "web_search",
                    "function": {
                        "description": "搜索与图片/视频相关的足球比赛背景情报"
                    },
                }
            ]
            body["tool_choice"] = "auto"
        return self._post(body, enable_search=enable_search, provider_name=f"StepFun({model})")

    def _post(self, body: dict, enable_search: bool, provider_name: str) -> LLMResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        start = time.time()
        try:
            response = requests.post(url, headers=headers, json=body, timeout=self.timeout)
        except requests.RequestException as exc:
            raise LLMError(f"{provider_name} 请求失败: {exc}") from exc

        cost_ms = int((time.time() - start) * 1000)
        if response.status_code >= 400:
            raise LLMError(f"{provider_name} 返回 HTTP {response.status_code}: {response.text[:500]}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise LLMError(f"{provider_name} 响应不是 JSON: {exc}") from exc

        try:
            message = payload["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"{provider_name} 响应结构异常: {payload}") from exc

        usage = payload.get("usage") or {}
        return LLMResponse(
            content=_message_text(message.get("content")),
            reasoning=_message_text(message.get("reasoning_content")) or _message_text(message.get("reasoning")),
            search_results=_extract_search_results(payload) if enable_search else [],
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            cost_ms=cost_ms,
            raw=payload,
        )


class DeepSeekClient:
    """DeepSeek chat client."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        reasoning_effort: str = "",
        timeout: int = 0,
    ):
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.base_url = (base_url or DEEPSEEK_BASE_URL).rstrip("/")
        self.model = model or DEEPSEEK_MODEL
        self.reasoning_effort = reasoning_effort or AI_REASONING_EFFORT
        self.timeout = timeout or AI_REQUEST_TIMEOUT
        if not self.api_key:
            raise LLMError("DEEPSEEK_API_KEY 未配置，无法调用 DeepSeek 模型")

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "reasoning_effort": self.reasoning_effort,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        start = time.time()
        try:
            response = requests.post(url, headers=headers, json=body, timeout=self.timeout)
        except requests.RequestException as exc:
            raise LLMError(f"DeepSeek 请求失败: {exc}") from exc

        cost_ms = int((time.time() - start) * 1000)
        if response.status_code >= 400:
            raise LLMError(f"DeepSeek 返回 HTTP {response.status_code}: {response.text[:500]}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise LLMError(f"DeepSeek 响应不是 JSON: {exc}") from exc

        try:
            message = payload["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"DeepSeek 响应结构异常: {payload}") from exc

        usage = payload.get("usage") or {}
        return LLMResponse(
            content=_message_text(message.get("content")),
            reasoning=_message_text(message.get("reasoning_content")) or _message_text(message.get("reasoning")),
            search_results=[],
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            cost_ms=cost_ms,
            raw=payload,
        )
