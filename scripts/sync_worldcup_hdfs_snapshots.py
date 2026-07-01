"""Sync locally verified World Cup processed snapshots to remote HDFS."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.hdfs_client import hdfs_client  # noqa: E402
from app.models.league import League  # noqa: E402
from app.models.match import Match  # noqa: E402
from app.models.match_event import MatchEvent  # noqa: E402
from app.models.player import Player  # noqa: E402
from app.models.player_stat import PlayerStat  # noqa: E402
from app.models.season import Season  # noqa: E402
from app.models.shot import Shot  # noqa: E402
from app.models.standings import Standings  # noqa: E402
from app.models.team import Team  # noqa: E402
from app.models.team_stat import TeamStat  # noqa: E402
from app.services.ingest_service import FIFA_DEFAULT_LEAGUE_NAME, FIFA_DEFAULT_SEASON_NAME  # noqa: E402
from app.services.match_service import MatchService, resolve_effective_match_status  # noqa: E402
from app.services.season_resolver import resolve_latest_season  # noqa: E402
from app.services.text_repair import repair_payload  # noqa: E402

WORLD_CUP_ALIASES = {
    "世界杯",
    "fifa world cup",
    "fifa world cup™",
    "world cup",
    "wc",
}


def _normalize_name(value: str | None) -> str:
    return " ".join((value or "").strip().lower().replace("™", "").replace("？", "").replace("?", "").split())


def _json_default(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _write_hdfs_json(hdfs_dir: str, filename: str, payload: dict | list) -> str:
    hdfs_path = f"{hdfs_dir.rstrip('/')}/{filename}"
    hdfs_client.write_json(
        json.dumps(repair_payload(payload), ensure_ascii=False, indent=2, default=_json_default),
        hdfs_path,
    )
    return hdfs_path


def _resolve_worldcup_context(db) -> tuple[League, Season]:
    leagues = db.query(League).order_by(League.id.desc()).all()
    candidates: list[tuple[int, League, Season]] = []
    fallback: tuple[League, Season] | None = None

    for league in leagues:
        normalized = _normalize_name(league.name)
        if normalized not in WORLD_CUP_ALIASES and (league.data_source or "").strip().lower() != "fifa_official":
            continue
        season = resolve_latest_season(db, league_id=league.id, season_name=FIFA_DEFAULT_SEASON_NAME)
        if not season:
            continue
        if fallback is None:
            fallback = (league, season)

        signal = (
            db.query(Match).filter(Match.league_id == league.id, Match.season_id == season.id).count()
            + db.query(Standings).filter(Standings.season_id == season.id).count()
            + db.query(PlayerStat).filter(PlayerStat.season_id == season.id).count()
            + db.query(TeamStat).filter(TeamStat.season_id == season.id).count()
        )
        if signal > 0:
            candidates.append((signal, league, season))

    if candidates:
        _, league, season = max(candidates, key=lambda item: (item[0], item[1].id, item[2].id))
        return league, season

    if fallback:
        return fallback

    raise RuntimeError(f"未找到 {FIFA_DEFAULT_LEAGUE_NAME} {FIFA_DEFAULT_SEASON_NAME} 的有效上下文")


def _build_team_lookup(db, matches: list[Match], standings_rows: list[Standings]) -> dict[int, Team]:
    team_ids = {team_id for match in matches for team_id in (match.home_team_id, match.away_team_id) if team_id}
    team_ids.update({row.team_id for row in standings_rows if row.team_id})
    if not team_ids:
        return {}
    return {team.id: team for team in db.query(Team).filter(Team.id.in_(team_ids)).all()}


def _serialize_matches(matches: list[Match], teams_by_id: dict[int, Team]) -> list[dict]:
    rows: list[dict] = []
    for match in matches:
        rows.append(
            {
                "id": match.id,
                "season_id": match.season_id,
                "league_id": match.league_id,
                "matchday": match.matchday,
                "match_date": match.match_date.isoformat() if match.match_date else None,
                "status": resolve_effective_match_status(match),
                "stage": match.stage,
                "group_name": match.group_name,
                "venue": match.venue,
                "home_team_id": match.home_team_id,
                "home_team_name": teams_by_id.get(match.home_team_id).name if match.home_team_id in teams_by_id else None,
                "away_team_id": match.away_team_id,
                "away_team_name": teams_by_id.get(match.away_team_id).name if match.away_team_id in teams_by_id else None,
                "home_score": match.home_score,
                "away_score": match.away_score,
                "home_score_ht": match.home_score_ht,
                "away_score_ht": match.away_score_ht,
                "data_source": match.data_source,
                "source_id": match.source_id,
            }
        )
    return rows


def _serialize_league_context(league: League, season: Season) -> dict:
    return {
        "league": {
            "id": league.id,
            "name": league.name,
            "country": league.country,
            "type": league.type,
            "logo_url": league.logo_url,
            "data_source": league.data_source,
            "source_id": league.source_id,
        },
        "season": {
            "id": season.id,
            "name": season.name,
            "start_date": season.start_date.isoformat() if season.start_date else None,
            "end_date": season.end_date.isoformat() if season.end_date else None,
            "current_matchday": season.current_matchday,
            "data_source": season.data_source,
            "source_id": season.source_id,
        },
    }


def _serialize_teams(
    teams_by_id: dict[int, Team],
    standings_rows: list[Standings],
    team_stats_rows: list[TeamStat],
) -> list[dict]:
    standings_by_team = {row.team_id: row for row in standings_rows if row.team_id}
    stats_by_team = {row.team_id: row for row in team_stats_rows if row.team_id}

    rows: list[dict] = []
    for team_id, team in sorted(teams_by_id.items(), key=lambda item: item[0]):
        standing = standings_by_team.get(team_id)
        stat = stats_by_team.get(team_id)
        rows.append(
            {
                "team_id": team.id,
                "name": team.name,
                "full_name": team.full_name,
                "country": team.country,
                "logo_url": team.logo_url,
                "stadium": team.stadium,
                "coach": team.coach,
                "founded_year": team.founded_year,
                "group_name": standing.group_name if standing else None,
                "position": standing.position if standing else None,
                "points": standing.points if standing else None,
                "goal_diff": standing.goal_diff if standing else None,
                "qualification_status": standing.qualification_status if standing else None,
                "matches_played": stat.matches_played if stat else 0,
                "wins": stat.wins if stat else 0,
                "draws": stat.draws if stat else 0,
                "losses": stat.losses if stat else 0,
                "goals_for": stat.goals_for if stat else 0,
                "goals_against": stat.goals_against if stat else 0,
                "xg_for": stat.xg_for if stat else 0,
                "xg_against": stat.xg_against if stat else 0,
                "shots_total": stat.shots_total if stat else 0,
                "passes_total": stat.passes_total if stat else 0,
                "attack_rating": stat.attack_rating if stat else 0,
                "defense_rating": stat.defense_rating if stat else 0,
                "overall_rating": stat.overall_rating if stat else 0,
                "data_source": team.data_source,
                "source_id": team.source_id,
            }
        )
    return rows


def _serialize_standings(standings_rows: list[Standings], teams_by_id: dict[int, Team]) -> list[dict]:
    rows: list[dict] = []
    for row in sorted(
        standings_rows,
        key=lambda item: (
            item.group_name or "",
            item.position or 999,
            item.team_id or 999999,
        ),
    ):
        team = teams_by_id.get(row.team_id)
        rows.append(
            {
                "id": row.id,
                "season_id": row.season_id,
                "team_id": row.team_id,
                "team_name": team.name if team else None,
                "group_name": row.group_name,
                "stage": row.stage,
                "position": row.position,
                "played": row.played,
                "won": row.won,
                "drawn": row.drawn,
                "lost": row.lost,
                "goals_for": row.goals_for,
                "goals_against": row.goals_against,
                "goal_diff": row.goal_diff,
                "points": row.points,
                "form": row.form,
                "qualification_status": row.qualification_status,
                "data_source": row.data_source,
                "source_id": row.source_id,
            }
        )
    return rows


def _serialize_players(db, season_id: int, teams_by_id: dict[int, Team]) -> tuple[list[dict], list[dict]]:
    player_stats = db.query(PlayerStat).filter(PlayerStat.season_id == season_id).all()
    player_ids = [row.player_id for row in player_stats if row.player_id]
    players = (
        {player.id: player for player in db.query(Player).filter(Player.id.in_(player_ids or [-1])).all()}
        if player_ids
        else {}
    )

    player_rows: list[dict] = []
    rating_rows: list[dict] = []
    for stat in player_stats:
        player = players.get(stat.player_id)
        if not player:
            continue
        team = teams_by_id.get(player.team_id) if player.team_id else None
        base_row = {
            "player_id": player.id,
            "name": player.name,
            "team_id": player.team_id,
            "team_name": team.name if team else None,
            "position": player.position,
            "shirt_number": player.shirt_number,
            "nationality": player.nationality,
            "birth_date": player.birth_date.isoformat() if player.birth_date else None,
            "height": player.height,
            "weight": player.weight,
            "photo_url": player.photo_url,
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
            "data_source": player.data_source,
            "source_id": player.source_id,
        }
        player_rows.append(base_row)
        rating_rows.append(
            {
                "player_id": player.id,
                "name": player.name,
                "team_name": team.name if team else None,
                "position": player.position,
                "atk_score": player.atk_score,
                "org_score": player.org_score,
                "def_score": player.def_score,
                "gk_score": player.gk_score,
                "phy_score": player.phy_score,
                "dis_score": player.dis_score,
                "overall_rating": player.overall_rating,
                "source": "worldcup_player_rating_service",
            }
        )
    return player_rows, rating_rows


def _serialize_match_events(db, match_ids: list[int], teams_by_id: dict[int, Team]) -> dict:
    service = MatchService()
    events = (
        db.query(MatchEvent)
        .filter(MatchEvent.match_id.in_(match_ids or [-1]))
        .order_by(MatchEvent.match_id.asc(), MatchEvent.minute.asc(), MatchEvent.id.asc())
        .all()
    )
    player_ids = [event.player_id for event in events if event.player_id]
    players = (
        {player.id: player for player in db.query(Player).filter(Player.id.in_(player_ids or [-1])).all()}
        if player_ids
        else {}
    )

    rows = [
        {
            "id": event.id,
            "match_id": event.match_id,
            "minute": event.minute,
            "event_type": event.event_type,
            "team_id": event.team_id,
            "team_name": teams_by_id.get(event.team_id).name if event.team_id in teams_by_id else None,
            "player_id": event.player_id,
            "player_name": players.get(event.player_id).name if event.player_id in players else None,
            "detail": service._localize_event_detail(
                event.detail,
                event.event_type,
                players.get(event.player_id).name if event.player_id in players else None,
            ),
            "data_source": event.data_source,
            "source_id": event.source_id,
        }
        for event in events
    ]
    return {
        "available": bool(rows),
        "row_count": len(rows),
        "source": "match_events" if rows else None,
        "rows": rows,
    }


def _serialize_team_ratings(team_rows: list[dict]) -> list[dict]:
    return [
        {
            "team_id": row["team_id"],
            "name": row["name"],
            "group_name": row["group_name"],
            "attack_rating": row["attack_rating"],
            "defense_rating": row["defense_rating"],
            "overall_rating": row["overall_rating"],
            "shots_total": row["shots_total"],
            "xg_for": row["xg_for"],
            "xg_against": row["xg_against"],
            "source": "team_stats",
        }
        for row in team_rows
    ]


def _serialize_xg_snapshot(db, matches: list[Match]) -> list[dict]:
    service = MatchService()
    rows: list[dict] = []
    for match in matches:
        timeline = service.get_xg_timeline(db, match.id)
        rows.append(
            {
                "match_id": match.id,
                "status": resolve_effective_match_status(match),
                "stage": match.stage,
                "group_name": match.group_name,
                "match_date": match.match_date.isoformat() if match.match_date else None,
                "available": bool(timeline and timeline.get("available")),
                "source": timeline.get("source") if timeline else None,
                "shot_count": timeline.get("shot_count") if timeline else 0,
                "coverage": timeline.get("coverage") if timeline else None,
                "note": timeline.get("note") if timeline else "未生成 xG 快照",
                "home_team": timeline.get("home_team") if timeline else None,
                "away_team": timeline.get("away_team") if timeline else None,
            }
        )
    return rows


def _serialize_report_snapshot(db, matches: list[Match]) -> dict:
    service = MatchService()
    rows = []
    for match in matches:
        report = service.get_match_report(db, match.id)
        if not report:
            continue
        rows.append(report)
    return {
        "available": bool(rows),
        "row_count": len(rows),
        "source": "match_service",
        "rows": rows,
    }


def _serialize_shots(db, match_ids: list[int]) -> dict:
    shots = (
        db.query(Shot)
        .filter(Shot.match_id.in_(match_ids or [-1]))
        .order_by(Shot.match_id.asc(), Shot.minute.asc(), Shot.id.asc())
        .all()
    )
    rows = [
        {
            "id": shot.id,
            "match_id": shot.match_id,
            "player_id": shot.player_id,
            "team_id": shot.team_id,
            "minute": shot.minute,
            "x": shot.x_coord,
            "y": shot.y_coord,
            "result": shot.result,
            "shot_type": shot.shot_type,
            "situation": shot.situation,
            "xg": shot.xg,
            "data_source": shot.data_source,
            "source_id": shot.source_id,
        }
        for shot in shots
    ]
    return {
        "available": bool(rows),
        "row_count": len(rows),
        "note": None if rows else "当前服务器侧没有 2026 世界杯真实逐脚 shot rows，保留空值并等待后续可用源回填。",
        "shots": rows,
    }


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db = SessionLocal()
    try:
        league, season = _resolve_worldcup_context(db)
        matches = (
            db.query(Match)
            .filter(Match.league_id == league.id, Match.season_id == season.id)
            .order_by(Match.match_date.asc(), Match.id.asc())
            .all()
        )
        standings_rows = db.query(Standings).filter(Standings.season_id == season.id).all()
        team_stats_rows = db.query(TeamStat).filter(TeamStat.season_id == season.id).all()
        teams_by_id = _build_team_lookup(db, matches, standings_rows)
        league_context = _serialize_league_context(league, season)
        processed_matches = _serialize_matches(matches, teams_by_id)
        processed_teams = _serialize_teams(teams_by_id, standings_rows, team_stats_rows)
        processed_standings = _serialize_standings(standings_rows, teams_by_id)
        processed_players, player_ratings = _serialize_players(db, season.id, teams_by_id)
        processed_events = _serialize_match_events(db, [match.id for match in matches], teams_by_id)
        team_ratings = _serialize_team_ratings(processed_teams)
        xg_snapshot = _serialize_xg_snapshot(db, matches)
        shots_snapshot = _serialize_shots(db, [match.id for match in matches])
        report_snapshot = _serialize_report_snapshot(db, matches)

        manifest = {
            "league_id": league.id,
            "league_name": league.name,
            "season_id": season.id,
            "season_name": season.name,
            "exported_at": datetime.now().isoformat(),
            "counts": {
                "matches": len(processed_matches),
                "standings": len(processed_standings),
                "teams": len(processed_teams),
                "players": len(processed_players),
                "events": processed_events["row_count"],
                "reports": report_snapshot["row_count"],
                "player_ratings": len(player_ratings),
                "team_ratings": len(team_ratings),
                "shots": shots_snapshot["row_count"],
                "xg_snapshot_matches": len(xg_snapshot),
            },
            "notes": {
                "shots": shots_snapshot["note"],
                "xg_model": "xG 快照按真实 shot rows 生成；无真实逐脚数据时保持 available=false 和中文说明。",
                "events": "比赛事件优先写入真实 match_events；若某场为空，比赛详情接口会按赛果生成派生摘要时间线。",
                "reports": "聚合报告快照来自 match_service，包含事件、xG、射门与 data_availability 说明。",
            },
        }

        written = {
            "processed_manifest": _write_hdfs_json(
                "/sports/processed/fifa_official",
                f"worldcup_manifest_{timestamp}.json",
                manifest,
            ),
            "processed_league_context": _write_hdfs_json(
                "/sports/processed/leagues",
                f"worldcup_league_context_{season.name}_{timestamp}.json",
                league_context,
            ),
            "processed_matches": _write_hdfs_json(
                "/sports/processed/matches",
                f"worldcup_matches_{season.name}_{timestamp}.json",
                {"season": season.name, "rows": processed_matches},
            ),
            "processed_standings": _write_hdfs_json(
                "/sports/processed/standings",
                f"worldcup_standings_{season.name}_{timestamp}.json",
                {"season": season.name, "rows": processed_standings},
            ),
            "processed_teams": _write_hdfs_json(
                "/sports/processed/teams",
                f"worldcup_teams_{season.name}_{timestamp}.json",
                {"season": season.name, "rows": processed_teams},
            ),
            "processed_players": _write_hdfs_json(
                "/sports/processed/players",
                f"worldcup_players_{season.name}_{timestamp}.json",
                {"season": season.name, "rows": processed_players},
            ),
            "processed_match_events": _write_hdfs_json(
                "/sports/processed/match_events",
                f"worldcup_match_events_{season.name}_{timestamp}.json",
                processed_events,
            ),
            "processed_shots": _write_hdfs_json(
                "/sports/processed/shots",
                f"worldcup_shots_{season.name}_{timestamp}.json",
                shots_snapshot,
            ),
            "analysis_player_rating": _write_hdfs_json(
                "/sports/analysis/player_rating",
                f"worldcup_player_rating_{season.name}_{timestamp}.json",
                {"season": season.name, "rows": player_ratings},
            ),
            "analysis_team_rating": _write_hdfs_json(
                "/sports/analysis/team_rating",
                f"worldcup_team_rating_{season.name}_{timestamp}.json",
                {"season": season.name, "rows": team_ratings},
            ),
            "analysis_xg_model": _write_hdfs_json(
                "/sports/analysis/xg_model",
                f"worldcup_xg_model_{season.name}_{timestamp}.json",
                {"season": season.name, "rows": xg_snapshot},
            ),
            "analysis_reports": _write_hdfs_json(
                "/sports/analysis/reports",
                f"worldcup_match_reports_{season.name}_{timestamp}.json",
                report_snapshot,
            ),
        }

        print(json.dumps({"ok": True, "written": written, "manifest": manifest}, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
