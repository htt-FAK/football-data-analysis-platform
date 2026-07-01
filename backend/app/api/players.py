"""Player endpoints with graceful analytics degradation."""

from __future__ import annotations

import statistics
import unicodedata
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.match import Match
from app.models.match_event import MatchEvent
from app.models.player import Player
from app.models.player_stat import PlayerStat
from app.models.season import Season
from app.models.team import Team
from app.services.season_resolver import resolve_latest_season, season_sort_key

router = APIRouter(tags=["players"])

ADVANCED_RADAR_MODE = "advanced_radar"
CONTRIBUTION_RADAR_MODE = "contribution_radar"
SUMMARY_MODE = "summary_only"
ADVANCED_SOURCE_CODES = {"fbref", "understat"}
KEY_EVENT_TYPES = ("goal", "yellow_card", "red_card", "substitution")
WORLD_CUP_SEASON_NAME = "2026"
WORLD_CUP_DATA_SOURCES = {"fifa_official", "statsbomb", "fbref"}


@router.get("/")
def list_players(
    team_id: int | None = Query(None, description="Filter by team ID"),
    league_id: int | None = Query(None, description="Filter by league ID"),
    season: str | None = Query(None, description="Season name when filtering by league"),
    position: str | None = Query(None, description="Filter by position: GK/DF/MF/FW"),
    name: str | None = Query(None, description="Fuzzy search by player name"),
    limit: int = Query(100, description="Maximum rows", le=500),
    db: Session = Depends(get_db),
):
    query = db.query(Player)
    if team_id:
        query = query.filter(Player.team_id == team_id)
    if position:
        query = query.filter(Player.position == position)
    if name:
        query = query.filter(Player.name.like(f"%{name}%"))
    if league_id:
        season_obj = _resolve_league_season(db, league_id, season)
        if season_obj:
            player_ids = [
                player_id
                for (player_id,) in (
                    db.query(PlayerStat.player_id)
                    .filter(PlayerStat.season_id == season_obj.id)
                    .distinct()
                    .all()
                )
            ]
            query = query.filter(Player.id.in_(player_ids or [-1]))
        else:
            query = query.filter(Player.id == -1)
    players = query.order_by(Player.name).limit(limit).all()

    team_ids = {player.team_id for player in players if player.team_id}
    teams_map = (
        {team.id: team.name for team in db.query(Team).filter(Team.id.in_(team_ids)).all()}
        if team_ids
        else {}
    )

    return [
        {
            "id": player.id,
            "name": player.name,
            "position": player.position,
            "team_id": player.team_id,
            "team_name": teams_map.get(player.team_id),
            "nationality": player.nationality,
            "photo_url": player.photo_url,
            "overall_rating": player.overall_rating,
            "data_source": player.data_source,
        }
        for player in players
    ]


@router.get("/top-scorers")
def get_top_scorers(
    limit: int = Query(10, description="Maximum rows", le=100),
    season: str | None = Query(None, description="Season name, defaults to latest"),
    db: Session = Depends(get_db),
):
    season_obj = _resolve_player_stats_season(db, season)
    if not season_obj:
        return []

    rows = (
        db.query(PlayerStat, Player)
        .join(Player, PlayerStat.player_id == Player.id)
        .filter(PlayerStat.season_id == season_obj.id, PlayerStat.goals > 0)
        .order_by(PlayerStat.goals.desc(), PlayerStat.xg.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "player_id": player.id,
            "name": player.name,
            "team_id": player.team_id,
            "goals": stat.goals,
            "assists": stat.assists,
            "xg": stat.xg,
            "appearances": stat.appearances,
            "minutes_played": stat.minutes_played,
        }
        for stat, player in rows
    ]


@router.get("/compare")
def compare_players(
    player_a: int = Query(..., description="Player A ID"),
    player_b: int = Query(..., description="Player B ID"),
    season: str | None = Query(None, description="Season name, defaults to latest"),
    db: Session = Depends(get_db),
):
    left = db.query(Player).filter(Player.id == player_a).first()
    right = db.query(Player).filter(Player.id == player_b).first()
    if not left or not right:
        raise HTTPException(status_code=404, detail="未找到对应球员")

    season_obj = _resolve_compare_season(db, left.id, right.id, season)
    left_stat = _get_stat_model(left.id, season_obj, db)
    right_stat = _get_stat_model(right.id, season_obj, db)
    left_events = _key_events(left.id, db, season_obj=season_obj)
    right_events = _key_events(right.id, db, season_obj=season_obj)
    left_completeness = _calculate_player_completeness(left, left_stat, len(left_events), season_obj, db)
    right_completeness = _calculate_player_completeness(right, right_stat, len(right_events), season_obj, db)

    return {
        "player_a": {"id": left.id, "name": left.name, "position": left.position, "team_id": left.team_id},
        "player_b": {"id": right.id, "name": right.name, "position": right.position, "team_id": right.team_id},
        "same_position": left.position == right.position,
        "radar": {
            "player_a": _build_radar_for(left, left.position, season_obj, db),
            "player_b": _build_radar_for(right, right.position, season_obj, db),
        },
        "season_stats": {
            "player_a": _serialize_stat(left_stat),
            "player_b": _serialize_stat(right_stat),
        },
        "position_rank": {
            "player_a": _position_rank(left, db, season_obj, strict_season=season is not None),
            "player_b": _position_rank(right, db, season_obj, strict_season=season is not None),
        },
        "key_events": {
            "player_a": left_events,
            "player_b": right_events,
        },
        "completeness": {
            "player_a": left_completeness,
            "player_b": right_completeness,
        },
        "recommended_visualization": _resolve_compare_visualization(left_completeness, right_completeness),
    }


@router.get("/position-stats")
def get_position_stats(
    position: str = Query(..., description="Position code: FW/MF/DF/GK"),
    season: str | None = Query(None, description="Season name, defaults to latest"),
    db: Session = Depends(get_db),
):
    season_obj = _resolve_player_stats_season(db, season)
    if not season_obj:
        return {"position": position, "count": 0, "distributions": {}}

    player_ids = [
        player_id
        for (player_id,) in (
            db.query(PlayerStat.player_id)
            .filter(PlayerStat.season_id == season_obj.id)
            .distinct()
            .all()
        )
    ]
    players = (
        db.query(Player)
        .filter(Player.position == position, Player.id.in_(player_ids or [-1]))
        .all()
    )
    dims = ["atk_score", "org_score", "def_score", "phy_score", "dis_score"]
    if position == "GK":
        dims = ["gk_score", "org_score", "phy_score", "dis_score"]

    distributions = {dim: [getattr(player, dim, 0) for player in players] for dim in dims}
    box_stats = {}
    for dim, values in distributions.items():
        if values:
            sorted_values = sorted(values)
            size = len(sorted_values)
            box_stats[dim] = {
                "min": sorted_values[0],
                "q1": sorted_values[size // 4],
                "median": statistics.median(sorted_values),
                "q3": sorted_values[3 * size // 4],
                "max": sorted_values[-1],
            }
        else:
            box_stats[dim] = {"min": 0, "q1": 0, "median": 0, "q3": 0, "max": 0}

    return {"position": position, "count": len(players), "distributions": box_stats}


@router.get("/{player_id}")
def get_player(player_id: int, db: Session = Depends(get_db)):
    player = _resolve_canonical_player(db, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="未找到该球员")

    team_name = None
    if player.team_id:
        team = db.query(Team).filter(Team.id == player.team_id).first()
        team_name = team.name if team else None

    return {
        "id": player.id,
        "requested_id": player_id,
        "canonical_id": player.id,
        "name": player.name,
        "position": player.position,
        "shirt_number": player.shirt_number,
        "nationality": player.nationality,
        "birth_date": player.birth_date.isoformat() if player.birth_date else None,
        "height": player.height,
        "weight": player.weight,
        "photo_url": player.photo_url,
        "team_id": player.team_id,
        "team_name": team_name,
        "overall_rating": player.overall_rating,
        "data_source": player.data_source,
    }


@router.get("/{player_id}/stats")
def get_player_stats(
    player_id: int,
    season: str | None = Query(None, description="Season name, defaults to latest"),
    db: Session = Depends(get_db),
):
    player = _resolve_canonical_player(db, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="未找到该球员")

    season_obj = _resolve_player_stat_season(db, player.id, season)
    stat = _get_stat_model(player.id, season_obj, db)
    return {
        "player_id": player.id,
        "requested_player_id": player_id,
        "canonical_player_id": player.id,
        "season": season_obj.name if season_obj else None,
        "stats": _serialize_stat(stat),
            "completeness": _calculate_player_completeness(
                player,
                stat,
                _count_key_events(player.id, db, season_obj),
                season_obj,
                db,
            ),
    }


@router.get("/{player_id}/radar")
def get_player_radar(
    player_id: int,
    position: str | None = Query(None, description="Override player position"),
    season: str | None = Query(None, description="Season name, defaults to latest"),
    db: Session = Depends(get_db),
):
    player = _resolve_canonical_player(db, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="未找到该球员")

    season_obj = _resolve_player_stat_season(db, player.id, season)
    target_position = position or player.position
    return _build_radar_for(player, target_position, season_obj, db)


@router.get("/{player_id}/position-rank")
def get_player_position_rank(
    player_id: int,
    season: str | None = Query(None, description="Season name, defaults to latest"),
    db: Session = Depends(get_db),
):
    player = _resolve_canonical_player(db, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="未找到该球员")
    season_obj = _resolve_player_stat_season(db, player.id, season)
    return _position_rank(player, db, season_obj, strict_season=bool(season))


def _resolve_season(db: Session, season_name: str | None):
    return resolve_latest_season(db, season_name=season_name)


def _resolve_canonical_player(db: Session, player_id: int) -> Player | None:
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        return None

    if _player_has_stats(db, player.id):
        return player

    canonical = _find_worldcup_canonical_player(db, player)
    return canonical or player


def _player_has_stats(db: Session, player_id: int) -> bool:
    return db.query(PlayerStat).filter(PlayerStat.player_id == player_id).first() is not None


def _find_worldcup_canonical_player(db: Session, player: Player) -> Player | None:
    if not player.team_id:
        return None

    season_obj = resolve_latest_season(db, season_name=WORLD_CUP_SEASON_NAME)
    if not season_obj:
        return None

    candidate_query = (
        db.query(Player)
        .join(PlayerStat, PlayerStat.player_id == Player.id)
        .filter(Player.team_id == player.team_id, PlayerStat.season_id == season_obj.id)
    )
    candidates = [
        row
        for row in candidate_query.all()
        if (row.data_source or "").strip().lower() in WORLD_CUP_DATA_SOURCES
    ]
    if not candidates:
        return None

    requested_key = _normalize_player_identity(player.name)
    exact = [candidate for candidate in candidates if _normalize_player_identity(candidate.name) == requested_key]
    if exact:
        return max(exact, key=_canonical_player_score)

    alias_identity = _lookup_player_alias_identity(player.name)
    if alias_identity:
        alias_matches = [
            candidate for candidate in candidates if _normalize_player_identity(candidate.name) == alias_identity
        ]
        if alias_matches:
            return max(alias_matches, key=_canonical_player_score)

    requested_tokens = _player_identity_tokens(player.name)
    if not requested_tokens:
        return None

    scored: list[tuple[int, int, Player]] = []
    for candidate in candidates:
        tokens = _player_identity_tokens(candidate.name)
        overlap = len(requested_tokens & tokens)
        if overlap > 0:
            scored.append((overlap, _canonical_player_score(candidate), candidate))

    if scored:
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return scored[0][2]
    return None


def _canonical_player_score(player: Player) -> int:
    score = 0
    if player.position:
        score += 10
    if player.photo_url:
        score += 5
    if (player.overall_rating or 0) > 0:
        score += 20
    if (player.data_source or "").strip().lower() == "fifa_official":
        score += 50
    return score


def _normalize_player_identity(name: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", name or "")
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().replace("&", "and")
    return "".join(ch for ch in normalized if ch.isalnum())


def _player_identity_tokens(name: str | None) -> set[str]:
    normalized = unicodedata.normalize("NFKD", name or "")
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = normalized.lower().replace("&", "and")
    parts = [
        token
        for token in (
            lowered.replace("-", " ").replace("_", " ").replace(".", " ").replace("'", " ").split()
        )
        if token
    ]
    return set(parts)


def _lookup_player_alias_identity(name: str | None) -> str | None:
    if not name:
        return None
    alias = _load_reverse_player_name_aliases().get(name.strip())
    if not alias:
        return None
    return _normalize_player_identity(alias)


@lru_cache(maxsize=1)
def _load_reverse_player_name_aliases() -> dict[str, str]:
    repo_root = Path(__file__).resolve().parents[3]
    utils_path = repo_root / "frontend" / "src" / "lib" / "utils.ts"
    if not utils_path.exists():
        return {}

    text = utils_path.read_text(encoding="utf-8", errors="ignore")
    marker = "const PLAYER_NAME_CN_MAP: Record<string, string> = {"
    start = text.find(marker)
    if start == -1:
        return {}
    end = text.find("\n};", start)
    if end == -1:
        return {}

    reverse: dict[str, str] = {}
    block = text[start:end].splitlines()[1:]
    for line in block:
        stripped = line.strip().rstrip(",")
        if not stripped or ":" not in stripped:
            continue
        key_part, value_part = stripped.split(":", 1)
        key = key_part.strip().strip('"').strip("'")
        value = value_part.strip().strip('"').strip("'")
        if value:
            reverse.setdefault(value, key)
    return reverse


def _resolve_league_season(db: Session, league_id: int, season_name: str | None):
    return resolve_latest_season(db, league_id=league_id, season_name=season_name)


def _resolve_player_stat_season(db: Session, player_id: int, season_name: str | None):
    season_ids = [
        season_id
        for (season_id,) in db.query(PlayerStat.season_id).filter(PlayerStat.player_id == player_id).distinct().all()
        if season_id
    ]
    if not season_ids:
        return resolve_latest_season(db, season_name=season_name)

    season_rows = db.query(Season).filter(Season.id.in_(season_ids)).all()
    if season_name:
        season_rows = [row for row in season_rows if row.name == season_name]
    if not season_rows:
        return None
    return max(season_rows, key=season_sort_key)


def _resolve_player_stats_season(db: Session, season_name: str | None):
    season_ids = [
        season_id
        for (season_id,) in db.query(PlayerStat.season_id).distinct().all()
        if season_id
    ]
    if not season_ids:
        return resolve_latest_season(db, season_name=season_name)

    season_rows = db.query(Season).filter(Season.id.in_(season_ids)).all()
    if season_name:
        season_rows = [row for row in season_rows if row.name == season_name]
    if not season_rows:
        return None
    return max(season_rows, key=season_sort_key)


def _resolve_compare_season(db: Session, player_a_id: int, player_b_id: int, season_name: str | None):
    season_ids = set(
        season_id
        for (season_id,) in db.query(PlayerStat.season_id).filter(PlayerStat.player_id == player_a_id).distinct().all()
        if season_id
    )
    season_ids |= set(
        season_id
        for (season_id,) in db.query(PlayerStat.season_id).filter(PlayerStat.player_id == player_b_id).distinct().all()
        if season_id
    )
    if not season_ids:
        return resolve_latest_season(db, season_name=season_name)

    season_rows = db.query(Season).filter(Season.id.in_(season_ids)).all()
    if season_name:
        season_rows = [row for row in season_rows if row.name == season_name]
    if not season_rows:
        return None
    return max(season_rows, key=season_sort_key)


def _get_stat_model(player_id: int, season_obj, db: Session) -> PlayerStat | None:
    if not season_obj:
        return None
    return (
        db.query(PlayerStat)
        .filter(PlayerStat.player_id == player_id, PlayerStat.season_id == season_obj.id)
        .first()
    )


def _serialize_stat(stat: PlayerStat | None) -> dict | None:
    if not stat:
        return None
    return {
        "appearances": stat.appearances,
        "goals": stat.goals,
        "assists": stat.assists,
        "yellow_cards": stat.yellow_cards,
        "red_cards": stat.red_cards,
        "minutes_played": stat.minutes_played,
        "shots": stat.shots,
        "shots_on_target": stat.shots_on_target,
        "xg": stat.xg,
        "xa": stat.xa,
        "passes": stat.passes,
        "pass_accuracy": stat.pass_accuracy,
        "tackles": stat.tackles,
        "interceptions": stat.interceptions,
        "rating": stat.rating,
        "saves": stat.player.saves if stat.player else None,
        "save_rate": stat.player.save_rate if stat.player else None,
        "xcs": stat.player.xcs if stat.player else None,
        "sweeper_actions": stat.player.sweeper_actions if stat.player else None,
    }


def _count_non_zero(*values) -> int:
    return sum(1 for value in values if value not in (None, 0, 0.0, ""))


def _has_model_scores(player: Player, position: str | None) -> bool:
    dims = _RADAR_DIMS.get(position or player.position or "MF", _RADAR_DIMS["MF"])
    return any((getattr(player, attr, 0) or 0) > 0 for attr, _ in dims)


def _count_key_events(player_id: int, db: Session, season_obj=None) -> int:
    return len(_key_events(player_id, db, season_obj=season_obj, limit=None))


def _calculate_player_completeness(
    player: Player,
    stat: PlayerStat | None,
    key_events_count: int = 0,
    season_obj=None,
    db: Session | None = None,
) -> dict:
    source_code = player.data_source or "unknown"
    if db is not None and season_obj is not None and stat is not None:
        key_events_count = _count_key_events(player.id, db, season_obj)
    if not stat:
        return {
            "tier": "tier0",
            "label": "no_stats",
            "advanced_ready": False,
            "recommended_visualization": SUMMARY_MODE,
            "source_code": source_code,
            "signals": {
                "key_events": key_events_count,
                "advanced_signal_count": 0,
                "has_model_scores": _has_model_scores(player, player.position),
            },
        }

    advanced_signal_count = _count_non_zero(
        stat.xg,
        stat.xa,
        stat.shots,
        stat.shots_on_target,
        stat.passes,
        stat.pass_accuracy,
        stat.tackles,
        stat.interceptions,
    )
    has_model_scores = _has_model_scores(player, player.position)
    enhanced_signal_count = _count_non_zero(
        stat.appearances,
        stat.minutes_played,
        stat.rating,
        key_events_count,
    )
    advanced_ready = has_model_scores and (
        advanced_signal_count >= 3 or (source_code in ADVANCED_SOURCE_CODES and advanced_signal_count >= 1)
    )

    if advanced_ready:
        tier = "tier3"
        label = "advanced"
        visualization = ADVANCED_RADAR_MODE
    elif enhanced_signal_count >= 2:
        tier = "tier2"
        label = "contribution"
        visualization = CONTRIBUTION_RADAR_MODE
    else:
        tier = "tier1"
        label = "basic"
        visualization = SUMMARY_MODE

    return {
        "tier": tier,
        "label": label,
        "advanced_ready": advanced_ready,
        "recommended_visualization": visualization,
        "source_code": source_code,
        "signals": {
            "key_events": key_events_count,
            "advanced_signal_count": advanced_signal_count,
            "has_model_scores": has_model_scores,
        },
    }


def _resolve_compare_visualization(left: dict, right: dict) -> str:
    if left["recommended_visualization"] == ADVANCED_RADAR_MODE and right["recommended_visualization"] == ADVANCED_RADAR_MODE:
        return ADVANCED_RADAR_MODE
    if CONTRIBUTION_RADAR_MODE in (left["recommended_visualization"], right["recommended_visualization"]):
        return CONTRIBUTION_RADAR_MODE
    return SUMMARY_MODE


def _clamp_score(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0
    return round(max(0.0, min((value / max_value) * 100.0, 100.0)), 2)


def _build_contribution_radar(
    player: Player,
    position: str | None,
    season_obj,
    stat: PlayerStat | None,
    completeness: dict,
    key_events_count: int,
) -> dict:
    if completeness["tier"] == "tier0":
        return {
            "player_id": player.id,
            "name": player.name,
            "position": position or player.position,
            "season": season_obj.name if season_obj else None,
            "mode": SUMMARY_MODE,
            "dimensions": ["Goals", "Assists", "Minutes", "Discipline", "Impact", "Availability"],
            "values": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "overall": 0.0,
            "completeness": completeness,
        }

    stat = stat or PlayerStat()
    discipline_penalty = (stat.yellow_cards or 0) * 10 + (stat.red_cards or 0) * 25
    values = [
        _clamp_score(float(stat.goals or 0), 5.0),
        _clamp_score(float(stat.assists or 0), 5.0),
        _clamp_score(float(stat.minutes_played or 0), 900.0),
        round(max(0.0, 100.0 - discipline_penalty), 2),
        _clamp_score(float((stat.goals or 0) + (stat.assists or 0) + key_events_count), 8.0),
        _clamp_score(float(stat.appearances or 0), 7.0),
    ]
    return {
        "player_id": player.id,
        "name": player.name,
        "position": position or player.position,
        "season": season_obj.name if season_obj else None,
        "mode": CONTRIBUTION_RADAR_MODE if completeness["tier"] == "tier2" else SUMMARY_MODE,
        "dimensions": ["Goals", "Assists", "Minutes", "Discipline", "Impact", "Availability"],
        "values": values,
        "overall": round(sum(values) / len(values), 2) if values else 0,
        "completeness": completeness,
    }


_RADAR_DIMS = {
    "GK": [
        ("gk_score", "Goalkeeping"),
        ("org_score", "Distribution"),
        ("def_score", "Positioning"),
        ("phy_score", "Aerial"),
        ("dis_score", "Decision Making"),
        ("overall_rating", "Overall Level"),
    ],
    "DF": [
        ("def_score", "Defending"),
        ("phy_score", "Aerial"),
        ("org_score", "Build-up"),
        ("atk_score", "Support"),
        ("dis_score", "Decision Making"),
        ("overall_rating", "Overall Level"),
    ],
    "MF": [
        ("atk_score", "Attacking Impact"),
        ("org_score", "Distribution"),
        ("def_score", "Ball-winning"),
        ("phy_score", "Coverage"),
        ("dis_score", "Decision Making"),
        ("overall_rating", "Overall Level"),
    ],
    "FW": [
        ("atk_score", "Attacking Impact"),
        ("org_score", "Chance Creation"),
        ("phy_score", "Physical Duel"),
        ("def_score", "Pressing"),
        ("dis_score", "Decision Making"),
        ("overall_rating", "Overall Level"),
    ],
}


def _build_radar_for(player: Player, position: str | None, season_obj, db: Session) -> dict:
    pos = position or "MF"
    stat = _get_stat_model(player.id, season_obj, db)
    key_events_count = _count_key_events(player.id, db, season_obj)
    completeness = _calculate_player_completeness(player, stat, key_events_count, season_obj, db)
    if completeness["recommended_visualization"] != ADVANCED_RADAR_MODE:
        return _build_contribution_radar(player, pos, season_obj, stat, completeness, key_events_count)

    dims = _RADAR_DIMS.get(pos, _RADAR_DIMS["MF"])
    peers_query = db.query(Player).filter(Player.position == pos)
    if season_obj is not None:
        season_player_ids = [
            player_id
            for (player_id,) in (
                db.query(PlayerStat.player_id)
                .filter(PlayerStat.season_id == season_obj.id)
                .distinct()
                .all()
            )
            if player_id
        ]
        peers_query = peers_query.filter(Player.id.in_(season_player_ids or [-1]))
    peers = peers_query.all()

    median_values = []
    for attr, _ in dims:
        values = [
            float(getattr(peer, attr, 0) or 0)
            for peer in peers
            if getattr(peer, attr, None) is not None
        ]
        median_values.append(round(statistics.median(values), 2) if values else 0.0)

    return {
        "player_id": player.id,
        "name": player.name,
        "position": pos,
        "season": season_obj.name if season_obj else None,
        "mode": ADVANCED_RADAR_MODE,
        "dimensions": [label for _, label in dims],
        "values": [getattr(player, attr, 0) for attr, _ in dims],
        "median_values": median_values,
        "overall": player.overall_rating or 0,
        "completeness": completeness,
    }


def _position_rank(player: Player, db: Session, season_obj=None, strict_season: bool = False) -> dict:
    if not player.position:
        return {
            "position": None,
            "rank": None,
            "overall_rank": None,
            "total": 0,
            "total_players": 0,
            "dimensions": {},
        }
    if strict_season and season_obj is None:
        return {
            "position": player.position,
            "rank": None,
            "overall_rank": None,
            "total": 0,
            "total_players": 0,
            "dimensions": {},
        }
    peers_query = db.query(Player).filter(Player.position == player.position)
    if season_obj is not None:
        season_player_ids = [
            player_id
            for (player_id,) in (
                db.query(PlayerStat.player_id)
                .filter(PlayerStat.season_id == season_obj.id)
                .distinct()
                .all()
            )
        ]
        peers_query = peers_query.filter(Player.id.in_(season_player_ids or [-1]))
    peers = peers_query.order_by(Player.overall_rating.desc()).all()
    rank = None
    for index, peer in enumerate(peers, start=1):
        if peer.id == player.id:
            rank = index
            break

    dims = _RADAR_DIMS.get(player.position, _RADAR_DIMS["MF"])
    dimension_ranks: dict[str, dict[str, int]] = {}
    total_players = len(peers)
    if total_players > 0:
        for attr, _label in dims:
            ranked_peers = sorted(
                peers,
                key=lambda peer: (getattr(peer, attr, 0) or 0, peer.overall_rating or 0, -peer.id),
                reverse=True,
            )
            attr_rank = None
            for index, peer in enumerate(ranked_peers, start=1):
                if peer.id == player.id:
                    attr_rank = index
                    break
            if attr_rank is not None:
                dimension_ranks[attr] = {"rank": attr_rank, "total": total_players}

    return {
        "position": player.position,
        "rank": rank,
        "overall_rank": rank,
        "total": total_players,
        "total_players": total_players,
        "dimensions": dimension_ranks,
    }


def _key_events(player_id: int, db: Session, season_obj=None, limit: int | None = 10) -> list:
    query = (
        db.query(MatchEvent)
        .join(Match, MatchEvent.match_id == Match.id)
        .filter(MatchEvent.player_id == player_id, MatchEvent.event_type.in_(KEY_EVENT_TYPES))
    )
    if season_obj is not None:
        query = query.filter(Match.season_id == season_obj.id)
    events_query = query.order_by(Match.match_date.desc(), MatchEvent.minute.desc(), MatchEvent.id.desc())
    if limit is not None:
        events_query = events_query.limit(limit)
    events = events_query.all()
    return [
        {
            "match_id": event.match_id,
            "event_type": event.event_type,
            "minute": event.minute,
            "detail": event.detail,
        }
        for event in events
    ]
