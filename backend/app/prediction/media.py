"""图片/视频视觉理解增强 —— 把搜索到的媒体交给视觉模型分析。

流程：
  1. 从 SearchResult.images 提取图片 URL（去重、过滤非图链接）
  2. 调 StepFunClient.chat_multimodal（step-1o-turbo-vision）批量分析图片
  3. 返回结构化「视觉情报」文本块，注入到预测 prompt 的 context

聚焦足球预测相关视觉信息：首发阵容图、训练照、新闻发布会、球场/天气、
球迷氛围、伤病公告图等。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from app.config import VISION_MAX_IMAGES
from app.prediction.llm_client import LLMError, LLMResponse, StepFunClient
from app.prediction.web_search import SearchResult

logger = logging.getLogger(__name__)

# 只保留这些扩展名/特征的 URL（过滤掉非图片链接）
_IMAGE_HOST_HINTS = ("img", "image", "cdn", "static", "photo", "media", "upload")
_IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")

# 低质量/社交媒体图片源：视觉模型识别价值低，且常导致 500，直接排除
_BAD_IMAGE_HOSTS = (
    "facebook", "fbcdn", "fbsbx", "threads", "instagram",
    "tiktok", "twitter", "x.com", "pinterest", "reddit",
    "youtube", "youtu.be",
)

# 高质量阵容/战术图来源（优先采用）
_GOOD_IMAGE_HOSTS = (
    "theanalyst", "opta", "whoscored", "transfermarkt",
    "si.com", "espn", "goal", "sportskeeda", "101greatgoals",
    "footballcriticism", "footballdna", "coachesvoice",
)


def _looks_like_image(url: str) -> bool:
    """粗略判断一个 URL 是否指向「值得分析的图片」。

    过滤掉：非图片链接、社交媒体缩略图（质量低且易致视觉模型 500）。
    """
    if not url or not url.startswith(("http://", "https://")):
        return False
    lower = url.lower().split("?")[0]
    host = urlparse(lower).netloc
    # 排除社交媒体低质来源
    if any(bad in host for bad in _BAD_IMAGE_HOSTS):
        return False
    if lower.endswith(_IMAGE_EXT):
        return True
    return any(hint in host for hint in _IMAGE_HOST_HINTS)


def _is_good_source(url: str) -> bool:
    """是否来自高质量阵容/战术图来源（优先采纳）。"""
    host = urlparse(url.lower()).netloc
    return any(good in host for good in _GOOD_IMAGE_HOSTS)


def _probe_image_url(url: str) -> bool:
    """5s 内验证 URL 可达且是 image/* Content-Type。

    返回 True 表示该 URL 可以被视觉模型安全使用。
    """
    import requests as _requests  # 局部导入避免循环依赖

    try:
        resp = _requests.head(
            url,
            timeout=5,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        if resp.status_code != 200:
            logger.debug("image URL %s returned %d, skipped", url, resp.status_code)
            return False
        ct = (resp.headers.get("Content-Type") or "").lower()
        if not ct.startswith("image/"):
            # 部分 CDN 不返 Content-Type，但 url 含 .jpg/.png 也放行
            lower = url.lower().split("?")[0]
            if not any(lower.endswith(ext) for ext in _IMAGE_EXT):
                logger.debug("image URL %s Content-Type=%s, skipped", url, ct)
                return False
        return True
    except _requests.RequestException as exc:
        logger.debug("image URL %s probe failed: %s", url, exc)
        return False


def extract_image_urls(results: list[SearchResult], limit: int = VISION_MAX_IMAGES) -> list[dict]:
    """从搜索结果里提取图片 URL，去重，返回 [{url, description, source}]。

    排序策略：优先高质量来源（theanalyst/opta/si 等），再按出现顺序。
    source 是该图片所属搜索结果的标题，便于追溯。
    """
    seen: set[str] = set()
    good: list[dict] = []
    others: list[dict] = []
    for r in results or []:
        source_title = (r.title or "").strip()
        for img in r.images:
            url = (img.get("url") or "").strip()
            if not url or url in seen:
                continue
            if not _looks_like_image(url):
                continue
            seen.add(url)
            entry = {
                "url": url,
                "description": (img.get("description") or "").strip(),
                "source": source_title,
            }
            if _is_good_source(url):
                good.append(entry)
            else:
                others.append(entry)
    # 优质来源优先，补足 limit
    collected = (good + others)[:limit]

    # 并行 HEAD 校验：过滤掉 404/403/非 image Content-Type 的失效链接
    if collected:
        workers = min(5, len(collected))
        with ThreadPoolExecutor(max_workers=workers) as exe:
            valid_flags = list(
                exe.map(_probe_image_url, [c["url"] for c in collected])
            )
        collected = [c for c, ok in zip(collected, valid_flags) if ok]

    return collected


# 视觉分析的 system prompt：聚焦足球预测有用信息
_VISION_SYSTEM_PROMPT = """你是一位足球赛前分析师，正在分析从互联网搜集到的与某场比赛相关的图片。
请聚焦以下对比赛预测有价值的信息（按重要度）：
1. **首发阵容 / 阵型**：训练照、发布会展示的阵容图、预测首发图 → 识别阵型（如4231/343）和关键球员
2. **球员状态 / 伤停**：球员表情、身体状态、训练参与情况 → 是否有主力缺阵、带伤
3. **教练态度**：发布会照片里教练的表情、肢体语言 → 自信/紧张/暗示轮换
4. **场地与天气**：球场草皮、天气状况（雨/晴/高温）、看台布置 → 是否有天气变量
5. **球迷氛围**：看台、横幅、侨民聚集 → 主场氛围强度

只提取与足球比赛预测相关的信息，忽略纯装饰性图片、广告、logo。
如果图片信息量低或与比赛无关，明确说明"信息量有限"。
用简洁的要点输出，不要泛泛描述图片美观。"""


def build_vision_prompt(match_meta: dict, images: list[dict]) -> str:
    """构造视觉分析的 user prompt（文本部分，图片通过 image_urls 传入）。"""
    home = match_meta.get("home_name", "主队")
    away = match_meta.get("away_name", "客队")
    return f"""请分析下面这 {len(images)} 张与「{home} vs {away}」比赛相关的图片，
提取对赛前预测有价值的视觉情报。

请按以下格式输出（中文）：
- 【阵容/阵型】识别到的阵型与关键球员（若无相关图片写"无明确信息"）
- 【球员状态】观察到的主力缺阵/带伤/状态（若无写"无明确信息"）
- 【教练态度】发布会/训练中的教练信号（若无写"无明确信息"）
- 【场地天气】球场/天气条件（若无写"无明确信息"）
- 【球迷氛围】主场氛围迹象（若无写"无明确信息"）
- 【其他】任何其他与比赛相关的视觉线索

最后用一句话总结：这些视觉情报对哪一方更有利，或影响中性。"""


def analyze_images(
    client: StepFunClient,
    match_meta: dict,
    images: list[dict],
    detail: str = "high",
) -> tuple[LLMResponse | None, str | None]:
    """调视觉模型分析图片，返回 (响应, 错误)。

    images 为 extract_image_urls 的输出。无图片时直接返回 (None, reason)。
    reason 区分 "no_images"（调用方未搜到任何图片）和 "no_valid_images"
    （所有候选 URL 经 HEAD 校验后均失效）。
    """
    if not images:
        # 区分"从未搜到"vs"搜到但全挂了"：images 调用方已做 probe，
        # 能走到这里说明所有候选都被过滤，记 warning 静默跳过。
        logger.warning("视觉分析跳过：无可用图片（候选 URL 均已失效或从未搜到）")
        return None, "no_valid_images"
    image_urls = [img["url"] for img in images]
    try:
        resp = client.chat_multimodal(
            system_prompt=_VISION_SYSTEM_PROMPT,
            user_prompt=build_vision_prompt(match_meta, images),
            image_urls=image_urls,
            vision_model="step-1o-turbo-vision",
            detail=detail,
            enable_search=False,
            max_tokens=1500,
        )
        return resp, None
    except LLMError as exc:
        logger.warning("视觉分析失败: %s", exc)
        return None, str(exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception("视觉分析异常: %s", exc)
        return None, f"{type(exc).__name__}: {exc}"


def build_vision_block(resp: LLMResponse | None, images: list[dict]) -> str:
    """把视觉分析结果格式化成 markdown 块，供注入预测 prompt。"""
    if not resp or not (resp.content or "").strip():
        return ""
    lines = ["\n# 视觉情报（视觉模型分析比赛相关图片）"]
    if images:
        lines.append(f"\n> 分析了 {len(images)} 张图片，来源：")
        for i, img in enumerate(images[:5], 1):
            src = img.get("source") or ""
            lines.append(f"> {i}. {src[:50]}")
    lines.append("\n" + resp.content.strip())
    return "\n".join(lines)
