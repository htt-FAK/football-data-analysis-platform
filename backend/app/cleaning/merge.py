"""数据源合并模块 — 按优先级合并多源记录"""

from typing import Any


def merge_sources(records: list[dict], priority: dict[str, int]) -> list[dict]:
    """按优先级合并多数据源记录

    将同一实体（依据 player_id / match_id / team_id 等标识）的多源记录合并，
    优先级高的源覆盖优先级低的源。priority 数值越大优先级越高。

    合并规则：
      1. 按标识字段（首个出现的 *_id 字段）分组
      2. 同组内按 priority 从低到高逐层覆盖（高优先级源的字段值优先）
      3. 仅在字段值为 None / 缺失时，才用低优先级源的值补齐

    Args:
        records: 多源记录列表，每条记录需含标识 source 来源标识（如 {"source": "fbref", ...}）
        priority: 源名称 -> 优先级数值（越大越高）

    Returns:
        list[dict]: 合并后的记录列表
    """
    if not records:
        return []

    # 找到标识字段（首个以 _id 结尾的字段）
    def _find_id(record: dict) -> str | None:
        for key in record:
            if key.endswith("_id") and key != "source_id":
                return key
        return None

    groups: dict[Any, list[dict]] = {}
    id_field = None
    for record in records:
        if id_field is None:
            id_field = _find_id(record)
        # 标识值作为分组键
        key = record.get(id_field) if id_field else id(record)
        groups.setdefault(key, []).append(record)

    # 各组内按 priority 升序排序（低优先级先打底，高优先级后覆盖）
    results = []
    for group_records in groups.values():
        sorted_records = sorted(
            group_records,
            key=lambda r: priority.get(r.get("source", ""), 0),
        )
        merged: dict = {}
        for record in sorted_records:
            for field, value in record.items():
                # 高优先级源的值优先；仅在已存在非空值时跳过
                if field in merged and merged[field] not in (None, ""):
                    continue
                merged[field] = value
        results.append(merged)

    return results


def merge_player(dongqiudi_data: dict, fbref_data: dict) -> dict:
    """球员数据合并示例函数

    以 FBref 为主源（高优先级），懂球帝为辅源（低优先级）补齐缺失字段。

    Args:
        dongqiudi_data: 懂球帝源球员数据（标准化后）
        fbref_data: FBref 源球员数据（标准化后）

    Returns:
        dict: 合并后的球员数据
    """
    # FBref 优先级更高
    priority = {"dongqiudi": 1, "fbref": 2}
    records = [
        {"source": "dongqiudi", **dongqiudi_data},
        {"source": "fbref", **fbref_data},
    ]
    merged = merge_sources(records, priority)
    return merged[0] if merged else {}
