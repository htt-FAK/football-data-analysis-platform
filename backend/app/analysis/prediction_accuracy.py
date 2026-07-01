"""预测命中判定 —— 比较赛前预测比分与赛后真实比分，给出三档结果。

三档：
  score_hit   预测比分完全一致（最准）
  result_hit  胜负平方向一致但比分不同
  miss        方向都不一致

胜负平方向以净胜球符号判定：>0 主胜、<0 客胜、=0 平局。
平局特殊：预测平局且实际也平局，即使比分不同也算 result_hit。
"""

from __future__ import annotations

from typing import Any, Optional

# 命中等级
LEVEL_SCORE_HIT = "score_hit"   # 命中比分
LEVEL_RESULT_HIT = "result_hit"  # 命中胜负
LEVEL_MISS = "miss"             # 未中

# 中文标签（前端可直接展示，列表徽章用）
LABEL_SCORE_HIT = "命中比分"
LABEL_RESULT_HIT = "命中胜负"
LABEL_MISS = "未中"


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def outcome_sign(home: int, away: int) -> int:
    """胜负平方向：>0 主胜，<0 客胜，=0 平局。"""
    diff = home - away
    if diff > 0:
        return 1
    if diff < 0:
        return -1
    return 0


def assess_accuracy(
    predicted_home: Any,
    predicted_away: Any,
    real_home: Any,
    real_away: Any,
) -> Optional[dict]:
    """判定一场预测的命中等级。

    Args:
        predicted_home/away: 预测主客队得分
        real_home/away: 真实主客队得分

    Returns:
        比赛未结束（真实比分缺失）时返回 None；否则返回::

            {
                "level": "score_hit" | "result_hit" | "miss",
                "label": "命中比分" | "命中胜负" | "未中",
                "predicted_home": int,
                "predicted_away": int,
                "real_home": int,
                "real_away": int,
                "predicted_outcome": "home_win" | "draw" | "away_win",
                "real_outcome": "home_win" | "draw" | "away_win",
            }
    """
    ph = _coerce_int(predicted_home)
    pa = _coerce_int(predicted_away)
    rh = _coerce_int(real_home)
    ra = _coerce_int(real_away)

    # 真实比分缺失（比赛未结束/未录入）→ 无法判定
    if rh is None or ra is None:
        return None
    # 预测比分缺失 → 无法判定（理论上有预测记录就会有，保险起见）
    if ph is None or pa is None:
        return None

    predicted_sign = outcome_sign(ph, pa)
    real_sign = outcome_sign(rh, ra)

    outcome_map = {1: "home_win", -1: "away_win", 0: "draw"}

    if ph == rh and pa == ra:
        level = LEVEL_SCORE_HIT
        label = LABEL_SCORE_HIT
    elif predicted_sign == real_sign:
        level = LEVEL_RESULT_HIT
        label = LABEL_RESULT_HIT
    else:
        level = LEVEL_MISS
        label = LABEL_MISS

    return {
        "level": level,
        "label": label,
        "predicted_home": ph,
        "predicted_away": pa,
        "real_home": rh,
        "real_away": ra,
        "predicted_outcome": outcome_map[predicted_sign],
        "real_outcome": outcome_map[real_sign],
    }


def summarize_accuracy(accuracy: Optional[dict]) -> Optional[dict]:
    """精简命中摘要，供列表徽章展示（只保留 level + label）。"""
    if not accuracy:
        return None
    return {"level": accuracy["level"], "label": accuracy["label"]}
