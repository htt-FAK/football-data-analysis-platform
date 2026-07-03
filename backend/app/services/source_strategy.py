"""Task-oriented source strategy helpers.

This module centralizes source priorities by task so schedulers and API
responses can reflect the same execution strategy.
"""

from __future__ import annotations

from typing import Iterable


DEFAULT_SOURCE_PRIORITY: dict[str, int] = {
    "fifa_official": 0,
    "api_football": 10,
    "dongqiudi": 30,
    "fbref": 40,
    "fotmob": 45,
    "understat": 50,
    "statsbomb": 55,
    "football_data": 60,
    "thesportsdb": 70,
    "openligadb": 80,
    "teamrankings": 90,
}

SOURCE_SUPPORTED_TARGETS: dict[str, set[str]] = {
    "fifa_official": {"live", "schedule", "standings", "players", "player_stats", "statistics"},
    "api_football": {"fixtures", "standings", "players"},
    "dongqiudi": {"schedule", "standings", "match_detail", "player_stats", "team_info"},
    "fbref": {"player_stats", "team_stats"},
    "fotmob": {"match_xg"},
    "understat": {"shots", "xg_timeline"},
    "statsbomb": {"matches", "player_stats", "shots"},
    "football_data": {"matches"},
    "thesportsdb": {"events", "teams", "players"},
    "openligadb": {"matches", "teams"},
    "teamrankings": {"rankings", "ratings"},
}

SOURCE_GENERIC_TARGET_ALIASES: dict[str, dict[str, str]] = {
    "fifa_official": {
        "team_stats": "statistics",
        "statistics": "statistics",
        "player_stats": "players",
    },
    "api_football": {
        "live": "fixtures",
        "schedule": "fixtures",
        "matches": "fixtures",
        "player_stats": "players",
    },
    "dongqiudi": {
        "player_stats": "player_stats",
    },
    "fbref": {
        "team_stats": "team_stats",
        "statistics": "team_stats",
    },
    "statsbomb": {
        "schedule": "matches",
        "matches": "matches",
    },
    "football_data": {
        "schedule": "matches",
        "matches": "matches",
    },
    "openligadb": {
        "schedule": "matches",
        "matches": "matches",
    },
    "thesportsdb": {
        "schedule": "events",
        "matches": "events",
    },
}


TASK_SOURCE_PRIORITY: dict[str, dict[str, int]] = {
    "live_match": {
        "fifa_official": 0,
        "api_football": 10,
    },
    "match_catalog": {
        "fifa_official": 0,
        "api_football": 10,
        "dongqiudi": 20,
        "football_data": 40,
        "openligadb": 50,
    },
    "player_basic": {
        "fifa_official": 0,
        "api_football": 10,
        "dongqiudi": 20,
        "thesportsdb": 30,
    },
    "player_advanced": {
        "fbref": 10,
        "understat": 20,
        "statsbomb": 25,
        "api_football": 30,
    },
    "metadata": {
        "thesportsdb": 10,
        "dongqiudi": 20,
        "api_football": 30,
    },
}


SOURCE_PROFILES: dict[str, dict[str, object]] = {
    "fifa_official": {
        "role": "official_world_cup_primary",
        "implemented": True,
        "recommended_tasks": ["live_match", "match_catalog", "player_basic"],
        "coverage_note": "Official World Cup source for fixtures, standings, squad metadata, and match-derived player statistics.",
    },
    "api_football": {
        "role": "primary_structured_api",
        "implemented": True,
        "recommended_tasks": ["live_match", "match_catalog", "player_basic"],
        "coverage_note": "Best current structured source for live events, lineups, and basic player stats.",
    },
    "dongqiudi": {
        "role": "supplemental_scrape",
        "implemented": True,
        "recommended_tasks": ["match_catalog", "player_basic"],
        "coverage_note": "Useful as a supplemental source, but should not carry the only critical path.",
    },
    "fbref": {
        "role": "advanced_analytics",
        "implemented": True,
        "recommended_tasks": ["player_advanced"],
        "coverage_note": "Advanced league analytics source; not the guaranteed World Cup player backbone.",
    },
    "fotmob": {
        "role": "world_cup_xg_supplement",
        "implemented": True,
        "recommended_tasks": [],
        "coverage_note": "Fotmob 单场汇总 xG（浏览器渲染抓取，绕过 x-fm-req 反爬）。仅提供主/客队最终 xG，逐脚时间线不可用。",
    },
    "understat": {
        "role": "xg_analytics",
        "implemented": True,
        "recommended_tasks": ["player_advanced"],
        "coverage_note": "Useful for shot maps and xG enrichment where supported. World Cup shot coverage is not available there.",
    },
    "statsbomb": {
        "role": "event_shot_open_data",
        "implemented": True,
        "recommended_tasks": ["player_advanced"],
        "coverage_note": "Open event and shot dataset that can enrich xG timelines and shot maps, but 2026 World Cup shots are not in open data.",
    },
    "football_data": {
        "role": "historical_dataset",
        "implemented": True,
        "recommended_tasks": ["match_catalog"],
        "coverage_note": "Historical league dataset for training samples and batch exports.",
    },
    "thesportsdb": {
        "role": "metadata_fallback",
        "implemented": True,
        "recommended_tasks": ["metadata"],
        "coverage_note": "Best used for logos, bios, and metadata fallback rather than advanced stats.",
    },
    "openligadb": {
        "role": "event_fallback",
        "implemented": True,
        "recommended_tasks": ["match_catalog"],
        "coverage_note": "Event-oriented fallback for supported competitions, not a World Cup player-analysis source.",
    },
    "teamrankings": {
        "role": "analysis_auxiliary",
        "implemented": True,
        "recommended_tasks": [],
        "coverage_note": "Auxiliary probability and team-strength source. World Cup pages are usable; some older league URLs may not be.",
    },
}


def get_default_priority(source_code: str) -> int:
    """Return the neutral fallback priority for a source."""

    return DEFAULT_SOURCE_PRIORITY.get(source_code, 999)


def get_task_priority(source_code: str, task: str) -> int:
    """Return the task-specific priority for a source."""

    return TASK_SOURCE_PRIORITY.get(task, {}).get(source_code, 999)


def get_source_profile(source_code: str) -> dict[str, object]:
    """Return API-friendly strategy metadata for a source."""

    profile = dict(SOURCE_PROFILES.get(source_code, {}))
    profile.setdefault("role", "unclassified")
    profile.setdefault("implemented", True)
    profile.setdefault("recommended_tasks", [])
    profile.setdefault("coverage_note", "No explicit task strategy has been registered for this source.")
    profile["source_code"] = source_code
    profile["default_priority"] = get_default_priority(source_code)
    profile["task_priority"] = {
        task: priority
        for task, mapping in TASK_SOURCE_PRIORITY.items()
        if (priority := mapping.get(source_code)) is not None
    }
    return profile


def resolve_crawl_target(source_code: str, target: str) -> str | None:
    """Map a generic pipeline target to a crawler-supported concrete target."""

    supported = SOURCE_SUPPORTED_TARGETS.get(source_code, set())
    if not supported:
        return target
    mapped = SOURCE_GENERIC_TARGET_ALIASES.get(source_code, {}).get(target, target)
    return mapped if mapped in supported else None


def sort_sources_for_task(sources: Iterable, task: str) -> list:
    """Sort SQLAlchemy source rows by task strategy first."""

    return sorted(
        sources,
        key=lambda source: (
            get_task_priority(source.source_code, task),
            get_default_priority(source.source_code),
            getattr(source, "priority", 999),
            source.source_code,
        ),
    )


def supports_task(source_code: str, task: str) -> bool:
    """Return whether a source is intentionally enabled for a task."""

    profile = get_source_profile(source_code)
    recommended_tasks = profile.get("recommended_tasks") or []
    return task in recommended_tasks
