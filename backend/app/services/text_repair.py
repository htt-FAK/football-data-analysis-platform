"""Helpers for repairing mojibake text before returning API payloads."""

from __future__ import annotations

import re

MOJIBAKE_HINT = re.compile(
    r"[脙脗脜脝脟脠脡脢脣脤脥脦脧脨脩脪脫脭脮脰脴脵脷脹脺脻脼脽脿谩芒茫盲氓忙莽猫茅锚毛矛铆卯茂冒帽貌贸么玫枚酶霉煤没眉媒镁每äåæçèéêëìíîïðñòóôõöøùúûüýþÿ]"
)

HAN_RE = re.compile(r"[\u4e00-\u9fff]")


def _count_han(text: str) -> int:
    return len(HAN_RE.findall(text))


def _decode_mojibake_once(text: str) -> str | None:
    if not text or not MOJIBAKE_HINT.search(text):
        return None
    if not all(ord(char) <= 0xFF for char in text):
        return None

    try:
        decoded = bytes(ord(char) for char in text).decode("utf-8").strip()
    except Exception:
        return None

    if not decoded or "\uFFFD" in decoded:
        return None
    return decoded


def repair_text(value: str | None) -> str | None:
    if value is None:
        return None

    text = str(value)
    if not text:
        return text

    repaired = text
    for _ in range(2):
        decoded = _decode_mojibake_once(repaired)
        if not decoded:
            break
        if _count_han(decoded) == 0 and _count_han(repaired) == 0 and not any(ord(char) > 127 for char in decoded):
            break
        repaired = decoded

    return repaired


def repair_dict_text(payload: dict | None, keys: list[str]) -> dict | None:
    if payload is None:
        return None
    for key in keys:
        if key in payload and isinstance(payload[key], str):
            payload[key] = repair_text(payload[key])
    return payload


def repair_payload(value):
    if isinstance(value, str):
        return repair_text(value)
    if isinstance(value, list):
        return [repair_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(repair_payload(item) for item in value)
    if isinstance(value, dict):
        return {key: repair_payload(item) for key, item in value.items()}
    return value
