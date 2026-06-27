"""去重模块 — 基于 key_fields 对记录去重"""


def dedup_records(records: list[dict], key_fields: list[str]) -> list[dict]:
    """基于 key_fields 对记录列表去重

    以 key_fields 对应的字段值组成元组作为唯一键，保留首次出现的记录。
    若某条记录缺少 key_fields 中的字段，则该字段视为 None 参与比较。

    Args:
        records: 原始记录列表
        key_fields: 用作唯一键的字段名列表

    Returns:
        list[dict]: 去重后的记录列表（保持原顺序）
    """
    if not records:
        return []

    seen = set()
    result = []
    for record in records:
        # 组装唯一键元组
        key = tuple(record.get(field) for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result
