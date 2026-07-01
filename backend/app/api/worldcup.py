"""World Cup focused endpoints for the presentation layer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.league import League
from app.models.match import Match
from app.models.match_event import MatchEvent
from app.models.player import Player
from app.models.player_stat import PlayerStat
from app.models.season import Season
from app.models.shot import Shot
from app.models.standings import Standings
from app.models.team import Team
from app.models.team_stat import TeamStat
from app.services.season_resolver import resolve_latest_season
from app.services.match_service import (
    get_worldcup_reference_now,
    refresh_worldcup_matches,
    resolve_effective_match_status,
)
from app.services.shot_utils import has_xg_timeline_fields, is_complete_shot_record
from app.services.ingest_service import (
    FIFA_DEFAULT_LEAGUE_NAME,
    FIFA_DEFAULT_SEASON_NAME,
)
from app.services.text_repair import repair_payload, repair_text
from app.api import players as players_api

router = APIRouter(tags=["worldcup"])
WORLD_CUP_LEAGUE_ALIASES = (
    FIFA_DEFAULT_LEAGUE_NAME,
    "世界杯",
    "FIFA World Cup™",
    "FIFA World Cup",
    "World Cup",
    "WC",
)


def _normalize_worldcup_league_name(name: str | None) -> str:
    normalized = (name or "").strip().lower()
    normalized = normalized.replace("™", "").replace("?", "")
    normalized = normalized.replace("鈩", "").replace("？", "")
    normalized = " ".join(normalized.split())
    return normalized


def _is_worldcup_league_name(name: str | None) -> bool:
    normalized = _normalize_worldcup_league_name(name)
    return normalized in {
        _normalize_worldcup_league_name(alias)
        for alias in WORLD_CUP_LEAGUE_ALIASES
    }


def _resolve_worldcup_context(
    db: Session,
    season_name: str | None = None,
) -> tuple[League, Season]:
    target_season_name = season_name or FIFA_DEFAULT_SEASON_NAME
    leagues = (
        db.query(League)
        .order_by(League.id.desc())
        .all()
    )
    leagues = [league for league in leagues if _is_worldcup_league_name(league.name)]
    if not leagues:
        raise HTTPException(status_code=404, detail="未找到世界杯联赛数据")

    candidates: list[tuple[int, League, Season]] = []
    fallback: tuple[League, Season] | None = None
    for league in leagues:
        season = resolve_latest_season(db, league_id=league.id, season_name=target_season_name)
        if not season:
            continue
        if fallback is None:
            fallback = (league, season)

        standings_count = db.query(Standings).filter(Standings.season_id == season.id).count()
        matches_count = db.query(Match).filter(Match.league_id == league.id, Match.season_id == season.id).count()
        player_stats_count = db.query(PlayerStat).filter(PlayerStat.season_id == season.id).count()
        team_stats_count = db.query(TeamStat).filter(TeamStat.season_id == season.id).count()
        signal = standings_count + matches_count + player_stats_count + team_stats_count
        if signal > 0:
            candidates.append((signal, league, season))

    if candidates:
        _, league, season = max(candidates, key=lambda item: (item[0], item[1].id, item[2].id))
        return league, season
    if fallback:
        return fallback
    raise HTTPException(status_code=404, detail="未找到世界杯赛季数据")


def _resolve_worldcup_schedule_context(
    db: Session,
    season_name: str | None = None,
) -> tuple[League, Season]:
    target_season_name = season_name or FIFA_DEFAULT_SEASON_NAME
    leagues = db.query(League).order_by(League.id.desc()).all()
    leagues = [league for league in leagues if league.data_source == "fifa_official"]
    if not leagues:
        leagues = [league for league in db.query(League).order_by(League.id.desc()).all() if _is_worldcup_league_name(league.name)]
    if not leagues:
        raise HTTPException(status_code=404, detail="未找到世界杯联赛数据")

    candidates: list[tuple[int, League, Season]] = []
    fallback: tuple[League, Season] | None = None
    for league in leagues:
        season = resolve_latest_season(db, league_id=league.id, season_name=target_season_name)
        if not season:
            continue
        if fallback is None:
            fallback = (league, season)

        matches_count = db.query(Match).filter(Match.league_id == league.id, Match.season_id == season.id).count()
        if matches_count > 0:
            candidates.append((matches_count, league, season))

    if candidates:
        _, league, season = max(candidates, key=lambda item: (item[0], item[1].id, item[2].id))
        return league, season
    if fallback:
        return fallback
    raise HTTPException(status_code=404, detail="未找到世界杯赛程上下文")


def _serialize_worldcup_upcoming_match(match: Match, teams_map: dict[int, str]) -> dict:
    home_team_name = repair_text(teams_map.get(match.home_team_id)) if match.home_team_id else None
    away_team_name = repair_text(teams_map.get(match.away_team_id)) if match.away_team_id else None
    home_team_name = home_team_name or None
    away_team_name = away_team_name or None
    effective_status = resolve_effective_match_status(match)
    return {
        "match_id": match.id,
        "match_date": match.match_date.isoformat() if match.match_date else None,
        "status": effective_status,
        "stage": match.stage,
        "group": match.group_name,
        "home_team_id": match.home_team_id,
        "home_team_name": home_team_name,
        "away_team_id": match.away_team_id,
        "away_team_name": away_team_name,
        "home_score": match.home_score,
        "away_score": match.away_score,
        "venue": match.venue,
        "is_ready_for_prediction": bool(
            match.home_team_id and match.away_team_id and home_team_name and away_team_name
        ),
    }


def _serialize_worldcup_team(row: Standings, teams_map: dict[int, Team]) -> dict:
    team = teams_map.get(row.team_id) if row.team_id else None
    return {
        "team_id": row.team_id,
        "name": repair_text(team.name) if team else None,
        "group": row.group_name,
        "played": row.played or 0,
        "wins": row.won or 0,
        "draws": row.drawn or 0,
        "losses": row.lost or 0,
        "goals_for": row.goals_for or 0,
        "goals_against": row.goals_against or 0,
        "goal_diff": row.goal_diff or 0,
        "points": row.points or 0,
        "rank": row.position or 0,
    }


@router.get("/summary")
def get_worldcup_summary(
    season: str | None = Query(FIFA_DEFAULT_SEASON_NAME, description="Season name"),
    db: Session = Depends(get_db),
):
    stat_league, stat_season = _resolve_worldcup_context(db, season)
    schedule_league, schedule_season = _resolve_worldcup_schedule_context(db, season)

    standings_rows = db.query(Standings).filter(Standings.season_id == stat_season.id).all()
    matches_rows = db.query(Match).filter(Match.league_id == schedule_league.id, Match.season_id == schedule_season.id).all()
    player_stat_rows = db.query(PlayerStat).filter(PlayerStat.season_id == stat_season.id).all()

    group_names = sorted(
        {
            row.group_name
            for row in standings_rows + matches_rows
            if getattr(row, "group_name", None)
        }
    )
    finished_matches = [row for row in matches_rows if resolve_effective_match_status(row) == "finished"]
    active_players = [
        row
        for row in player_stat_rows
        if any(
            (
                row.appearances,
                row.goals,
                row.assists,
                row.minutes_played,
                row.shots,
                row.passes,
            )
        )
    ]
    qualified_teams = [
        row
        for row in standings_rows
        if (row.qualification_status or "").lower().find("qualified") >= 0
    ]
    rated_players = [row for row in player_stat_rows if float(row.rating or 0) > 0]

    return repair_payload({
        "league_id": schedule_league.id,
        "league_name": repair_text(stat_league.name),
        "season": schedule_season.name,
        "group_count": len(group_names),
        "group_names": group_names,
        "match_count": len(matches_rows),
        "finished_match_count": len(finished_matches),
        "team_count": len({row.team_id for row in standings_rows if row.team_id}),
        "player_count": len({row.player_id for row in player_stat_rows if row.player_id}),
        "active_player_count": len(active_players),
        "rated_player_count": len(rated_players),
        "qualified_team_count": len({row.team_id for row in qualified_teams if row.team_id}),
    })


@router.get("/leaders")
def get_worldcup_leaders(
    season: str | None = Query(FIFA_DEFAULT_SEASON_NAME, description="Season name"),
    limit: int = Query(10, ge=1, le=50, description="Rows per leaderboard"),
    db: Session = Depends(get_db),
):
    league, season_obj = _resolve_worldcup_context(db, season)
    _ = league

    rows = (
        db.query(PlayerStat, Player, Team)
        .join(Player, PlayerStat.player_id == Player.id)
        .outerjoin(Team, Player.team_id == Team.id)
        .filter(PlayerStat.season_id == season_obj.id)
        .all()
    )

    payload = []
    for stat, player, team in rows:
        payload.append(
            {
                "player_id": player.id,
                "name": repair_text(player.name),
                "position": player.position,
                "team_id": team.id if team else None,
                "team_name": repair_text(team.name) if team else None,
                "photo_url": player.photo_url,
                "appearances": stat.appearances or 0,
                "goals": stat.goals or 0,
                "assists": stat.assists or 0,
                "minutes_played": stat.minutes_played or 0,
                "rating": float(stat.rating or 0),
                "shots": stat.shots or 0,
                "passes": stat.passes or 0,
            }
        )

    def _top(key: str):
        return sorted(
            payload,
            key=lambda row: (row[key], row["minutes_played"], row["appearances"], row["name"]),
            reverse=True,
        )[:limit]

    return repair_payload({
        "season": season_obj.name,
        "top_scorers": _top("goals"),
        "top_assists": _top("assists"),
        "top_ratings": _top("rating"),
    })


@router.get("/teams")
def get_worldcup_teams(
    season: str | None = Query(FIFA_DEFAULT_SEASON_NAME, description="Season name"),
    group_name: str | None = Query(None, alias="group", description="Group filter"),
    db: Session = Depends(get_db),
):
    league, season_obj = _resolve_worldcup_context(db, season)
    _ = league

    standings_query = db.query(Standings).filter(Standings.season_id == season_obj.id)
    if group_name:
        standings_query = standings_query.filter(Standings.group_name == group_name)
    standings_rows = standings_query.all()

    team_ids = [row.team_id for row in standings_rows if row.team_id]
    teams_map = (
        {team.id: team for team in db.query(Team).filter(Team.id.in_(team_ids)).all()}
        if team_ids
        else {}
    )

    rows = sorted(
        standings_rows,
        key=lambda row: (
            row.group_name or "",
            row.position or 999,
            -(row.points or 0),
            -(row.goal_diff or 0),
            (
                repair_text(teams_map.get(row.team_id).name)
                if row.team_id and teams_map.get(row.team_id)
                else ""
            ),
        ),
    )

    return repair_payload({
        "season": season_obj.name,
        "group": group_name,
        "teams": [_serialize_worldcup_team(row, teams_map) for row in rows],
    })


@router.get("/players")
def get_worldcup_players(
    season: str | None = Query(FIFA_DEFAULT_SEASON_NAME, description="Season name"),
    group_name: str | None = Query(None, alias="group", description="Group name"),
    position: str | None = Query(None, description="Position filter"),
    sort_by: str = Query("rating", description="Sort by: rating/goals/assists/minutes"),
    limit: int = Query(200, ge=1, le=2000, description="Rows to return"),
    db: Session = Depends(get_db),
):
    league, season_obj = _resolve_worldcup_context(db, season)
    _ = league

    standings_rows = db.query(Standings).filter(Standings.season_id == season_obj.id).all()
    team_lookup = {
        row.team_id: {
            "group": row.group_name,
            "group_rank": row.position,
            "qualification_status": row.qualification_status,
        }
        for row in standings_rows
        if row.team_id
    }

    rows = (
        db.query(PlayerStat, Player, Team)
        .join(Player, PlayerStat.player_id == Player.id)
        .outerjoin(Team, Player.team_id == Team.id)
        .filter(PlayerStat.season_id == season_obj.id)
        .all()
    )

    payload = []
    for stat, player, team in rows:
        team_meta = team_lookup.get(team.id if team else None, {})
        row = {
            "player_id": player.id,
            "name": repair_text(player.name),
            "position": player.position,
            "team_id": team.id if team else None,
            "team_name": repair_text(team.name) if team else None,
            "group": team_meta.get("group"),
            "group_rank": team_meta.get("group_rank"),
            "qualification_status": team_meta.get("qualification_status"),
            "photo_url": player.photo_url,
            "nationality": repair_text(player.nationality),
            "appearances": stat.appearances or 0,
            "goals": stat.goals or 0,
            "assists": stat.assists or 0,
            "minutes_played": stat.minutes_played or 0,
            "rating": float(stat.rating or 0),
            "shots": stat.shots or 0,
            "passes": stat.passes or 0,
            "xg": float(stat.xg or 0),
            "xa": float(stat.xa or 0),
            "overall_rating": float(player.overall_rating or 0),
            "atk_score": float(player.atk_score or 0),
            "org_score": float(player.org_score or 0),
            "def_score": float(player.def_score or 0),
            "gk_score": float(player.gk_score or 0),
            "phy_score": float(player.phy_score or 0),
            "dis_score": float(player.dis_score or 0),
        }
        if group_name and row["group"] != group_name:
            continue
        if position and row["position"] != position:
            continue
        payload.append(row)

    sort_key_map = {
        "rating": "rating",
        "goals": "goals",
        "assists": "assists",
        "minutes": "minutes_played",
    }
    sort_key = sort_key_map.get(sort_by, "rating")
    payload = sorted(
        payload,
        key=lambda item: (
            item[sort_key],
            item["minutes_played"],
            item["goals"],
            item["assists"],
            item["name"],
        ),
        reverse=True,
    )[:limit]

    return repair_payload({
        "season": season_obj.name,
        "sort_by": sort_key,
        "group": group_name,
        "position": position,
        "players": payload,
    })


@router.get("/players/{player_id}/radar")
def get_worldcup_player_radar(
    player_id: int,
    season: str | None = Query(FIFA_DEFAULT_SEASON_NAME, description="Season name"),
    db: Session = Depends(get_db),
):
    league, season_obj = _resolve_worldcup_context(db, season)
    _ = league

    player = players_api._resolve_canonical_player(db, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="未找到该世界杯球员")
    player_stat = (
        db.query(PlayerStat)
        .filter(PlayerStat.player_id == player.id, PlayerStat.season_id == season_obj.id)
        .first()
    )
    if not player_stat:
        raise HTTPException(status_code=404, detail="未找到该球员对应赛季的世界杯统计")

    return repair_payload(players_api._build_radar_for(player, player.position, season_obj, db))


@router.get("/coverage")
def get_worldcup_coverage(
    season: str | None = Query(FIFA_DEFAULT_SEASON_NAME, description="Season name"),
    db: Session = Depends(get_db),
):
    league, season_obj = _resolve_worldcup_context(db, season)
    schedule_league, schedule_season = _resolve_worldcup_schedule_context(db, season)

    standings_count = (
        db.query(Standings)
        .filter(Standings.season_id == season_obj.id)
        .count()
    )
    matches_count = (
        db.query(Match)
        .filter(Match.league_id == schedule_league.id, Match.season_id == schedule_season.id)
        .count()
    )
    player_stats_rows = db.query(PlayerStat).filter(PlayerStat.season_id == season_obj.id).all()
    team_stats_rows = db.query(TeamStat).filter(TeamStat.season_id == season_obj.id).all()
    worldcup_match_ids = [
        match_id
        for (match_id,) in (
            db.query(Match.id)
            .filter(Match.league_id == schedule_league.id, Match.season_id == schedule_season.id)
            .all()
        )
    ]
    match_events_count = (
        db.query(MatchEvent)
        .filter(
            MatchEvent.match_id.in_(worldcup_match_ids or [-1]),
            MatchEvent.event_type.isnot(None),
        )
        .count()
    )
    worldcup_shots = (
        db.query(Shot)
        .filter(Shot.match_id.in_(worldcup_match_ids or [-1]))
        .all()
    )
    worldcup_shots_count = len(worldcup_shots)
    worldcup_complete_shot_count = sum(1 for shot in worldcup_shots if is_complete_shot_record(shot))
    worldcup_timeline_ready_shot_count = sum(1 for shot in worldcup_shots if has_xg_timeline_fields(shot))
    rated_count = sum(1 for row in player_stats_rows if float(row.rating or 0) > 0)
    xg_count = sum(1 for row in player_stats_rows if float(row.xg or 0) > 0)
    pass_count = sum(1 for row in player_stats_rows if int(row.passes or 0) > 0)
    minutes_count = sum(1 for row in player_stats_rows if int(row.minutes_played or 0) > 0)
    rated_team_count = sum(
        1
        for row in team_stats_rows
        if any(float(value or 0) > 0 for value in (row.attack_rating, row.defense_rating, row.overall_rating))
    )
    team_stat_shot_count = sum(1 for row in team_stats_rows if int(row.shots_total or 0) > 0)

    players = db.query(Player).filter(Player.data_source == "fifa_official").all()
    dimension_score_count = sum(
        1
        for player in players
        if any(
            float(value or 0) > 0
            for value in (
                player.atk_score,
                player.org_score,
                player.def_score,
                player.gk_score,
                player.phy_score,
                player.dis_score,
                player.overall_rating,
            )
        )
    )

    coverage = [
        {
            "module": "小组积分榜",
            "status": "ready" if standings_count > 0 else "missing",
            "detail": f"standings={standings_count}",
        },
        {
            "module": "小组赛程与比分",
            "status": "ready" if matches_count > 0 else "missing",
            "detail": f"matches={matches_count}",
        },
        {
            "module": "球员榜单与基础统计",
            "status": "ready" if len(player_stats_rows) > 0 else "missing",
            "detail": f"player_stats={len(player_stats_rows)}",
        },
        {
            "module": "球员评分榜",
            "status": "ready" if rated_count > 0 else "missing",
            "detail": f"rated_players={rated_count}",
        },
        {
            "module": "球员六维能力雷达",
            "status": "partial" if dimension_score_count == 0 and rated_count > 0 else "ready",
            "detail": f"dimension_scored_players={dimension_score_count}",
        },
        {
            "module": "球队攻防雷达",
            "status": "ready" if team_stats_rows and rated_team_count > 0 else "missing",
            "detail": f"team_stats={len(team_stats_rows)}, rated_team_rows={rated_team_count}",
        },
        {
            "module": "射门热图 / xG 时间线",
            "status": (
                "ready"
                if worldcup_complete_shot_count > 0
                else ("partial" if worldcup_shots_count > 0 or xg_count > 0 or team_stat_shot_count > 0 else "missing")
            ),
            "detail": (
                f"player_xg_rows={xg_count}, team_stats={len(team_stats_rows)}, "
                f"shots_table={worldcup_shots_count}, timeline_ready={worldcup_timeline_ready_shot_count}, "
                f"complete_shots={worldcup_complete_shot_count}"
            ),
        },
        {
            "module": "关键事件影响分析",
            "status": "ready" if match_events_count > 0 else "missing",
            "detail": f"match_events={match_events_count}",
        },
        {
            "module": "传控与出场强度分析",
            "status": "ready" if pass_count > 0 and minutes_count > 0 else "missing",
            "detail": f"passes>0 rows={pass_count}, minutes>0 rows={minutes_count}",
        },
    ]

    return repair_payload({
        "season": season_obj.name,
        "coverage": coverage,
    })


@router.get("/upcoming")
def get_worldcup_upcoming(
    season: str | None = Query(FIFA_DEFAULT_SEASON_NAME, description="Season name"),
    limit: int = Query(16, ge=1, le=64, description="Rows to return"),
    db: Session = Depends(get_db),
):
    league, season_obj = _resolve_worldcup_schedule_context(db, season)
    now = get_worldcup_reference_now()
    matches = [
        match
        for match in (
            db.query(Match)
            .filter(Match.league_id == league.id, Match.season_id == season_obj.id, Match.status == "scheduled")
            .all()
        )
        if match.match_date is None or match.match_date >= now
    ]
    refresh_worldcup_matches(db, matches)
    matches = [
        match
        for match in (
            db.query(Match)
            .filter(Match.league_id == league.id, Match.season_id == season_obj.id)
            .all()
        )
        if resolve_effective_match_status(match) != "finished"
        and (match.match_date is None or match.match_date >= now)
    ]
    matches = sorted(
        matches,
        key=lambda match: (
            match.match_date is None,
            match.match_date or datetime.max,
            match.id,
        ),
    )[:limit]
    team_ids = {match.home_team_id for match in matches if match.home_team_id} | {
        match.away_team_id for match in matches if match.away_team_id
    }
    teams_map = (
        {team.id: repair_text(team.name) for team in db.query(Team).filter(Team.id.in_(team_ids)).all()}
        if team_ids
        else {}
    )

    return repair_payload({
        "season": season_obj.name,
        "matches": [_serialize_worldcup_upcoming_match(match, teams_map) for match in matches],
    })


@router.get("/matches")
def get_worldcup_matches(
    season: str | None = Query(FIFA_DEFAULT_SEASON_NAME, description="Season name"),
    status: str | None = Query(None, description="Optional match status filter"),
    limit: int = Query(128, ge=1, le=256, description="Rows to return"),
    db: Session = Depends(get_db),
):
    league, season_obj = _resolve_worldcup_schedule_context(db, season)
    matches = db.query(Match).filter(Match.league_id == league.id, Match.season_id == season_obj.id)
    matches = matches.order_by(Match.match_date.asc(), Match.id.asc()).limit(limit).all()
    refresh_worldcup_matches(db, matches)
    matches = db.query(Match).filter(Match.league_id == league.id, Match.season_id == season_obj.id)
    matches = matches.order_by(Match.match_date.asc(), Match.id.asc()).limit(limit).all()
    if status:
        matches = [match for match in matches if resolve_effective_match_status(match) == status]

    team_ids = {match.home_team_id for match in matches if match.home_team_id} | {
        match.away_team_id for match in matches if match.away_team_id
    }
    teams_map = (
        {team.id: repair_text(team.name) for team in db.query(Team).filter(Team.id.in_(team_ids)).all()}
        if team_ids
        else {}
    )

    return repair_payload({
        "season": season_obj.name,
        "matches": [_serialize_worldcup_upcoming_match(match, teams_map) for match in matches],
    })
