"""联网搜索 API 冒烟测试（Tavily / Serper）。

用法（在 backend 目录下）：
    python test_web_search_provider.py            # 用 .env 里配置的 provider
    python test_web_search_provider.py tavily     # 强制用 tavily
    python test_web_search_provider.py serper     # 强制用 serper

拿到 Tavily/Serper 的 key 后填进 .env（TAVILY_API_KEY / SERPER_API_KEY），
跑这个脚本验证搜索是否返回结果、字段是否正确。
不调用任何 LLM，只验证搜索 API 本身。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.prediction.web_search import (
    SearchError,
    SearchResult,
    build_intel_block,
    get_search_provider,
    is_available,
)


def safe_print(s: str) -> None:
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(s.encode(enc, errors="replace").decode(enc, errors="replace"))


def main() -> None:
    forced = sys.argv[1] if len(sys.argv) > 1 else ""
    provider = get_search_provider(forced) if forced else get_search_provider()

    print("=" * 60)
    if provider is None:
        provider_name = forced or "(.env 配置)"
        safe_print(f"  ❌ 联网搜索未启用（provider={provider_name}）")
        print("=" * 60)
        print("  请检查 .env：")
        print("    WEB_SEARCH_PROVIDER=tavily   (或 serper)")
        print("    TAVILY_API_KEY=tvly-xxxxx    (去 https://tavily.com 注册)")
        return

    safe_print(f"  联网搜索 provider: {type(provider).__name__}")
    safe_print(f"  is_available: {is_available()}")
    print("=" * 60)

    query = "2026 FIFA World Cup schedule fixtures"
    safe_print(f"\n  搜索查询: {query}")
    print("  正在调用搜索 API ...\n")

    try:
        results: list[SearchResult] = provider.search(query, max_results=5)
    except SearchError as exc:
        safe_print(f"  ❌ 搜索失败: {exc}")
        return

    print(f"  命中结果数: {len(results)}")
    print("-" * 60)
    for i, r in enumerate(results, 1):
        safe_print(f"  {i}. {r.title[:60]}")
        safe_print(f"     URL: {r.url[:70]}")
        if r.content:
            safe_print(f"     摘要: {r.content[:120]}{'...' if len(r.content) > 120 else ''}")
        print()

    # 演示 build_intel_block（这是注入 prompt 的格式）
    if results:
        print("-" * 60)
        safe_print("  build_intel_block 输出（注入 prompt 的格式，前 600 字）:")
        print("-" * 60)
        block = build_intel_block(results[:3], heading="实时网络情报")
        safe_print(block[:600])

    print()
    print("=" * 60)
    ok = len(results) > 0
    safe_print(f"  结论: {'✅ 联网搜索工作正常' if ok else '❌ 未返回结果，检查 key/额度'}")
    if ok:
        safe_print("  → 现在可以跑 python test_prediction_e2e.py 验证完整预测链路")
    print("=" * 60)


if __name__ == "__main__":
    main()
