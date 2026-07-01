"""Shared helpers for serializing and validating shot rows."""

from __future__ import annotations

from typing import Any


def shot_value(shot: Any, field: str):
    if isinstance(shot, dict):
        return shot.get(field)
    return getattr(shot, field, None)


def coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def has_xg_timeline_fields(shot: Any) -> bool:
    return all(
        (
            coerce_int(shot_value(shot, "team_id")) is not None,
            coerce_int(shot_value(shot, "minute")) is not None,
            coerce_float(shot_value(shot, "xg")) is not None,
        )
    )


def has_heatmap_fields(shot: Any) -> bool:
    return all(
        (
            coerce_float(shot_value(shot, "x_coord")) is not None,
            coerce_float(shot_value(shot, "y_coord")) is not None,
        )
    )


def is_complete_shot_record(shot: Any) -> bool:
    return has_xg_timeline_fields(shot) and has_heatmap_fields(shot)


def shot_sort_key(shot: Any) -> tuple[int, int]:
    minute = coerce_int(shot_value(shot, "minute"))
    shot_id = coerce_int(shot_value(shot, "id"))
    return (minute if minute is not None else 9999, shot_id if shot_id is not None else 999999999)


def serialize_shot(
    shot: Any,
    *,
    match_id: int | None = None,
    team_name: str | None = None,
    player_name: str | None = None,
) -> dict:
    xg = coerce_float(shot_value(shot, "xg"))
    x_coord = coerce_float(shot_value(shot, "x_coord"))
    y_coord = coerce_float(shot_value(shot, "y_coord"))
    minute = coerce_int(shot_value(shot, "minute"))
    shot_match_id = coerce_int(shot_value(shot, "match_id"))

    return {
        "id": coerce_int(shot_value(shot, "id")),
        "match_id": match_id if match_id is not None else shot_match_id,
        "minute": minute,
        "team_id": coerce_int(shot_value(shot, "team_id")),
        "team_name": team_name,
        "player_id": coerce_int(shot_value(shot, "player_id")),
        "player_name": player_name,
        "x_coord": x_coord,
        "y_coord": y_coord,
        "x": x_coord,
        "y": y_coord,
        "result": shot_value(shot, "result"),
        "shot_type": shot_value(shot, "shot_type"),
        "situation": shot_value(shot, "situation"),
        "xg": round(xg, 3) if xg is not None else None,
        "data_source": shot_value(shot, "data_source"),
        "source_id": shot_value(shot, "source_id"),
    }
