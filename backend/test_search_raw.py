"""web_search 原始响应诊断脚本（不经过封装，直接打 HTTP）。

用法（在 backend 目录下）：
    python test_search_raw.py

会尝试多种 tools / tool_choice 写法，并 dump 每次的完整原始 JSON 响应，
从而精确定位阶跃 API 到底有没有执行搜索、结果放在哪个字段。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests
from app.config import STEPFUN_API_KEY

URL = "https://api.stepfun.com/v1/chat/completions"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {STEPFUN_API_KEY}",
}
MESSAGES = [
    {"role": "system", "content": "每个提问先通过web search，然后通过web search的结果，回答用户问题"},
    {"role": "user", "content": "上海最高的楼是哪座？请只回答楼的名称。"},
]

# 要尝试的多种 tools 声明写法（覆盖阶跃文档可能的格式）
VARIANTS = [
    ("写法1: type=web_search + function.description", {
        "tools": [{"type": "web_search", "function": {"description": "搜索互联网的信息"}}],
        "tool_choice": "auto",
    }),
    ("写法2: type=web_search + function.description(中文)", {
        "tools": [{"type": "web_search", "function": {"description": "这个web_search用来搜索互联网的信息"}}],
        "tool_choice": "auto",
    }),
    ("写法3: web_search + tool_choice=required", {
        "tools": [{"type": "web_search", "function": {"description": "搜索互联网的信息"}}],
        "tool_choice": "required",
    }),
    ("写法4: web_search_prompt 模式（无 tools，改用 extra_body）", {
        "web_search": True,
    }),
    ("写法5: 纯净（只 tools 不 tool_choice）", {
        "tools": [{"type": "web_search", "function": {"description": "搜索互联网的信息"}}],
    }),
]


def safe_print(s: str) -> None:
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(s.encode(enc, errors="replace").decode(enc, errors="replace"))


def try_variant(name: str, extra: dict) -> None:
    print("\n" + "=" * 70)
    safe_print(f"  {name}")
    print("=" * 70)
    body = {
        "model": "step-3.7-flash",
        "messages": MESSAGES,
        "max_tokens": 600,
        **extra,
    }
    # 不传 reasoning_effort（官方 web_search 示例不传）
    start = time.time()
    try:
        resp = requests.post(URL, headers=HEADERS, json=body, timeout=90)
    except Exception as exc:
        safe_print(f"  [请求异常] {exc}")
        return
    cost = int((time.time() - start) * 1000)

    if resp.status_code >= 400:
        safe_print(f"  HTTP {resp.status_code}: {resp.text[:500]}")
        return

    payload = resp.json()
    usage = payload.get("usage") or {}
    choice = (payload.get("choices") or [{}])[0]
    msg = choice.get("message") or {}

    print(f"  耗时={cost}ms  HTTP=200  finish_reason={choice.get('finish_reason')}")
    safe_print(f"  usage: prompt={usage.get('prompt_tokens')} completion={usage.get('completion_tokens')} total={usage.get('total_tokens')}")
    safe_print(f"  message 顶层 keys: {list(msg.keys())}")
    safe_print(f"  有 tool_calls: {'tool_calls' in msg and bool(msg.get('tool_calls'))}")
    safe_print(f"  有 search_results: {'search_results' in msg}")
    safe_print(f"  有 annotations: {'annotations' in msg}")

    # 关键判定：prompt_tokens > 500 基本说明搜索结果被注入了上下文
    pt = usage.get("prompt_tokens", 0)
    if pt and pt > 500:
        print(f"  >>> prompt_tokens={pt} 较大，疑似搜索结果已注入上下文（web_search 生效）")

    # 打印 content 片段
    content = msg.get("content")
    if isinstance(content, list):
        safe_print(f"  content(列表) 片段: {json.dumps(content[:2], ensure_ascii=False)[:300]}")
    else:
        safe_print(f"  content 片段: {str(content)[:200]}")

    # 打印 tool_calls（如果有）
    tc = msg.get("tool_calls")
    if tc:
        safe_print(f"  tool_calls: {json.dumps(tc, ensure_ascii=False)[:600]}")

    # 打印 search_results / annotations（如果有）
    for k in ("search_results", "annotations", "citations"):
        v = msg.get(k)
        if v:
            safe_print(f"  {k}: {json.dumps(v, ensure_ascii=False)[:600]}")

    # 兜底：dump 整个 message（精简）
    print("  ---- 完整 message（JSON）----")
    safe_print(json.dumps(msg, ensure_ascii=False, indent=2)[:1500])


def main() -> None:
    if not STEPFUN_API_KEY:
        print("STEPFUN_API_KEY 未配置")
        return
    print(f"key 长度={len(STEPFUN_API_KEY)}  提问={MESSAGES[1]['content']}")
    for name, extra in VARIANTS:
        try:
            try_variant(name, extra)
        except Exception as exc:
            safe_print(f"  [未捕获异常] {type(exc).__name__}: {exc}")
    print("\n" + "=" * 70)
    print("  诊断完成。请把上面任何一处 prompt_tokens>500 或 tool_calls/search_results 有内容的写法贴给我。")
    print("=" * 70)


if __name__ == "__main__":
    main()
