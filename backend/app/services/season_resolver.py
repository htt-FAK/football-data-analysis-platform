"""Helpers for resolving the most relevant season row consistently."""

from __future__ import annotations

import re
from datetime import date

from sqlalchemy.orm import Session

from app.models.season import Season


def season_sort_key(season: Season):
    name = (season.name or "").strip()
    numbers = [int(part) for part in re.findall(r"\d{2,4}", name)]
    primary = max(numbers) if numbers else -1
    secondary = len(numbers)
    date_hint = season.end_date or season.start_date or date.min
    return (
        primary,
        secondary,
        date_hint,
        season.id,
    )


def resolve_latest_season(
    db: Session,
    league_id: int | None = None,
    season_name: str | None = None,
):
    query = db.query(Season)
    if league_id is not None:
        query = query.filter(Season.league_id == league_id)
    if season_name:
        query = query.filter(Season.name == season_name)
    seasons = query.all()
    if not seasons:
        return None
    return max(seasons, key=season_sort_key)
