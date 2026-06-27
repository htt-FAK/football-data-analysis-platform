"""缺失值处理模块 — 按规则填充缺失字段"""

# 默认填充规则：字段 -> 默认值
DEFAULT_RULES = {
    "goals": 0,
    "assists": 0,
    "shots": 0,
    "shots_on_target": 0,
    "passes": 0,
    "pass_accuracy": 0.0,
    "possession": 0.0,
    "minutes_played": 0,
    "xg": 0.0,
    "xa": 0.0,
    "rating": 0.0,
    "height": None,
    "weight": None,
    "age": None,
    "position": "Unknown",
    "nationality": "Unknown",
    "team": "Unknown",
    "league": "Unknown",
    "season": "Unknown",
    "home_score": 0,
    "away_score": 0,
}


def fill_missing(record: dict, rules: dict) -> dict:
    """按规则填充记录中的缺失字段

    仅当字段值为 None 或字段不存在时才填充默认值；
    已存在的非空值保持不变。

    Args:
        record: 单条记录字典
        rules: 填充规则字典（字段 -> 默认值），通常传入 DEFAULT_RULES

    Returns:
        dict: 填充后的记录字典（不修改原字典）
    """
    result = dict(record)
    for field, default_value in rules.items():
        if field not in result or result[field] is None:
            result[field] = default_value
    return result
