"""图片/视频视觉理解增强 链路测试。

用法（在 backend 目录下）：
    python test_media_vision.py            # 跑全部三步
    python test_media_vision.py --extract  # 只测图片提取（不调视觉模型）
    python test_media_vision.py --vision   # 只测视觉模型分析

测试链路：
  1) 用 Tavily 搜比赛相关图片（include_images=True）
  2) extract_image_urls 提取去重图片 URL
  3) 调 step-1o-turbo-vision 分析图片，产出「视觉情报」块
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import VISION_MAX_IMAGES
from app.prediction.llm_client import StepFunClient
from app.prediction.media import analyze_images, build_vision_block, extract_image_urls
from app.prediction.web_search import is_available, search_safe


def safe_print(s: str) -> None:
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(s.encode(enc, errors="replace").decode(enc, errors="replace"))


def banner(title: str, char: str = "=") -> None:
    print()
    print(char * 60)
    safe_print(f"  {title}")
    print(char * 60)


def step1_search_images() -> list:
    banner("第 1 步：用 Tavily 搜索比赛图片（include_images=True）")
    if not is_available():
        safe_print("  [SKIP] 联网搜索未配置，无法测试")
        return []
    query = "Brazil vs Japan World Cup 2026 lineup formation preview"
    safe_print(f"  搜索: {query}")
    results = search_safe(query, include_images=True)
    total_images = sum(len(r.images) for r in results)
    safe_print(f"  命中 {len(results)} 条结果，原始图片字段共 {total_images} 个")
    for i, r in enumerate(results[:3], 1):
        safe_print(f"    {i}. {r.title[:50]} ({len(r.images)} 张图)")
    return results


def step2_extract(results: list) -> list:
    banner("第 2 步：extract_image_urls 提取去重图片")
    images = extract_image_urls(results, limit=VISION_MAX_IMAGES)
    safe_print(f"  提取到 {len(images)} 张图片（limit={VISION_MAX_IMAGES}）")
    for i, img in enumerate(images, 1):
        safe_print(f"  {i}. {img['url'][:70]}")
        if img.get("description"):
            safe_print(f"     描述: {img['description'][:60]}")
        if img.get("source"):
            safe_print(f"     来源: {img['source'][:50]}")
    if not images:
        safe_print("  [WARN] 没有提取到图片（可能 Tavily 该查询未返回图片）")
    return images


def step3_vision(images: list) -> None:
    banner("第 3 步：调 step-1o-turbo-vision 分析图片")
    if not images:
        safe_print("  [SKIP] 无图片，跳过视觉分析")
        return
    try:
        client = StepFunClient(timeout=120)
    except Exception as exc:
        safe_print(f"  [FAIL] 初始化 StepFunClient 失败: {exc}")
        return

    meta = {"home_name": "Brazil", "away_name": "Japan"}
    safe_print(f"  提交 {len(images)} 张图片给 step-1o-turbo-vision ...")
    resp, error = analyze_images(client, meta, images, detail="high")
    if error and not resp:
        safe_print(f"  [FAIL] 视觉分析失败: {error}")
        return
    if resp:
        safe_print(f"  耗时={resp.cost_ms}ms  tokens={resp.total_tokens}")
        print("-" * 60)
        safe_print("  视觉分析结果：")
        safe_print(resp.content)
        print("-" * 60)
        # 展示 build_vision_block（注入 prompt 的格式）
        block = build_vision_block(resp, images)
        safe_print("\n  build_vision_block 输出（注入预测 prompt 的格式，前 500 字）:")
        safe_print(block[:500])

    ok = bool(resp and resp.content and len(resp.content) > 50)
    print()
    safe_print(f"  结论: {'✅ 视觉理解增强链路正常' if ok else '⚠️ 视觉分析结果偏弱，但链路已通'}")


def main() -> None:
    args = set(sys.argv[1:])
    run_all = not args

    if run_all or "--extract" in args:
        results = step1_search_images()
        images = step2_extract(results)
    else:
        # --vision 单跑时，先搜图
        results = step1_search_images() if is_available() else []
        images = step2_extract(results)

    if run_all or "--vision" in args:
        step3_vision(images)

    banner("完成", "=")


if __name__ == "__main__":
    main()
