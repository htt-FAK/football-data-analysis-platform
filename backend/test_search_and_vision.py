"""Smoke tests for StepFun web_search and multimodal capabilities."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import DEEPSEEK_API_KEY, STEPFUN_API_KEY
from app.prediction.llm_client import LLMError, StepFunClient


SAMPLE_IMAGE_URL = "https://www.stepfun.com/assets/section-1-CTe4nZiO.webp"
SAMPLE_VIDEO_URL = "https://static-openapi.stepfun.com/static/platform-web/vipcase/case1.mp4"
LINE_WIDTH = 70


def safe_text(value: object) -> str:
    text_value = str(value)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text_value.encode(encoding, errors="replace").decode(encoding, errors="replace")


def console_print(*parts: object, sep: str = " ", end: str = "\n") -> None:
    print(sep.join(safe_text(part) for part in parts), end=end)


def banner(title: str, char: str = "=") -> None:
    console_print()
    console_print(char * LINE_WIDTH)
    console_print(f"  {title}")
    console_print(char * LINE_WIDTH)


def line() -> None:
    console_print("-" * LINE_WIDTH)


def check_key() -> bool:
    if not STEPFUN_API_KEY:
        console_print("[FAIL] STEPFUN_API_KEY 未配置，无法测试，请检查 .env")
        return False
    console_print(f"[OK] STEPFUN_API_KEY 已配置（长度 {len(STEPFUN_API_KEY)}）")
    console_print(f"[OK] DEEPSEEK_API_KEY {'已配置' if DEEPSEEK_API_KEY else '未配置（本测试不需要）'}")
    return True


def test_web_search() -> bool:
    banner("测试 1 / 3 | web_search 联网搜索")
    system = "每个提问先通过web search，然后通过web search的结果，回答用户问题"
    user = "上海最高的楼是哪座？请只回答楼的名称。"
    console_print("  诊断目标：对比 reasoning_effort=high vs none，定位为何搜不到来源")
    console_print(f"  提问：{user}")

    # 变体 A：当前默认（reasoning_effort=high）
    console_print("\n  -- 变体 A：reasoning_effort=high（当前默认）")
    client_a = StepFunClient(timeout=90, reasoning_effort="high")
    resp_a = _try_search(client_a, system, user)
    _diagnose("A (high)", resp_a)

    # 变体 B：不启用思考（官方 web_search 示例的写法）
    console_print("\n  -- 变体 B：reasoning_effort=none（官方示例写法）")
    client_b = StepFunClient(timeout=90, reasoning_effort="none")
    resp_b = _try_search(client_b, system, user)
    _diagnose("B (none)", resp_b)

    best = resp_a if (resp_a and len(resp_a.search_results) > 0) else resp_b
    ok = bool(best and len(best.search_results) > 0)
    if ok:
        win = "A(high)" if (resp_a and len(resp_a.search_results) > 0) else "B(none)"
        console_print(f"\n  [OK] web_search 正常  -> 生效变体：{win}（建议编排器采用此配置）")
    else:
        console_print("\n  [WARN] 两个变体都没搜到来源，见上方诊断（可能 key 无 web_search 权限或被限流）")
    return ok


def _try_search(client: StepFunClient, system: str, user: str):
    try:
        return client.chat(system, user, enable_search=True, max_tokens=800)
    except LLMError as exc:
        console_print(f"    [FAIL] 调用失败：{exc}")
        return None


def _diagnose(tag: str, resp) -> None:
    """打印单次搜索调用的详细诊断，含原始响应结构。"""
    if resp is None:
        console_print(f"    [{tag}] 无响应")
        return
    console_print(f"    [{tag}] 耗时={resp.cost_ms}ms  token=prompt{resp.prompt_tokens}/comp{resp.completion_tokens}/total{resp.total_tokens}")
    console_print(f"    [{tag}] 联网来源数 = {len(resp.search_results)}")
    raw_msg = ((resp.raw or {}).get("choices") or [{}])[0].get("message") or {}
    has_tool_calls = bool(raw_msg.get("tool_calls"))
    finish = ((resp.raw or {}).get("choices") or [{}])[0].get("finish_reason")
    console_print(f"    [{tag}] 原始 message 有 tool_calls 字段：{has_tool_calls}  finish_reason={finish}")
    if resp.search_results:
        console_print(f"    [{tag}] 命中来源：")
        for idx, source in enumerate(resp.search_results[:4], start=1):
            console_print(f"      {idx}. {(source.get('title') or '')[:50]}  ->  {(source.get('url') or '')[:55]}")
    content_preview = (resp.content or "").strip().replace("\n", " ")[:120]
    console_print(f"    [{tag}] 正文预览：{content_preview or '(空)'}")
    if "<tool_call>" in (resp.content or ""):
        console_print(f"    [{tag}] [WARN] 正文出现 <tool_call> 文本 = 模型把工具调用当文本输出（未真正联网）")


def test_image_understanding() -> bool:
    banner("测试 2 / 3 | 图片理解")
    client = StepFunClient(timeout=90)
    system = "你是一个图像理解助手，请准确描述图片中的主要元素。"
    user = "请用中文详细描述这张图片里的主要元素，包括建筑、文字、环境和光线。"
    console_print(f"  图片 URL：{SAMPLE_IMAGE_URL}")
    console_print("  正在调用（detail=high），约 10-30s ...")
    try:
        resp = client.chat_multimodal(
            system,
            user,
            image_urls=[SAMPLE_IMAGE_URL],
            vision_model="step-1o-turbo-vision",
            detail="high",
            max_tokens=600,
        )
    except LLMError as exc:
        console_print(f"  [FAIL] 调用失败：{exc}")
        return False

    console_print(f"  耗时  : {resp.cost_ms} ms")
    console_print(f"  token : prompt={resp.prompt_tokens} completion={resp.completion_tokens} total={resp.total_tokens}")
    line()
    console_print("  模型描述：")
    console_print("  " + (resp.content or "(空)").replace("\n", "\n  "))
    ok = bool(resp.content) and len(resp.content) > 20
    console_print(f"\n  结论：{'[OK] 图片理解正常' if ok else '[WARN] 返回内容过短或为空'}")
    return ok


def test_video_understanding() -> bool:
    banner("测试 3 / 3 | 视频理解")
    client = StepFunClient(timeout=120)
    system = "你是视频内容分析助手，请概括视频中的关键信息。"
    user = "请用中文概括这个视频的主要内容，并提取 3 个关键信息点。"
    console_print(f"  视频 URL：{SAMPLE_VIDEO_URL}")
    console_print("  正在调用，约 20-60s ...")
    try:
        resp = client.chat_multimodal(
            system,
            user,
            video_urls=[SAMPLE_VIDEO_URL],
            max_tokens=600,
        )
    except LLMError as exc:
        console_print(f"  [FAIL] 调用失败：{exc}")
        return False

    console_print(f"  耗时  : {resp.cost_ms} ms")
    console_print(f"  token : prompt={resp.prompt_tokens} completion={resp.completion_tokens} total={resp.total_tokens}")
    line()
    console_print("  模型概括：")
    console_print("  " + (resp.content or "(空)").replace("\n", "\n  "))
    ok = bool(resp.content) and len(resp.content) > 20
    console_print(f"\n  结论：{'[OK] 视频理解正常' if ok else '[WARN] 返回内容过短或为空'}")
    return ok


def main() -> None:
    banner("StepFun 能力冒烟测试：联网搜索 + 图片/视频理解", "#")
    if not check_key():
        return

    args = set(sys.argv[1:])
    run_all = not args
    results: dict[str, bool] = {}

    if run_all or "--search" in args:
        results["web_search"] = test_web_search()
    if run_all or "--image" in args:
        results["image"] = test_image_understanding()
    if run_all or "--video" in args:
        results["video"] = test_video_understanding()

    banner("汇总", "#")
    for name, ok in results.items():
        console_print(f"  {'[OK]' if ok else '[FAIL]'} {name}")


if __name__ == "__main__":
    main()
