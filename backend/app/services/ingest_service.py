"""数据入库服务 — 爬虫原始数据 → 标准化 → 实体解析 → upsert → Redis 缓存 → WebSocket 推送

这是连接「爬虫层」和「数据层 + 实时层」的桥梁，对应方案 3.8 / 6.4 的数据闭环：

    爬虫 crawl() 返回 list[dict]（业务字段）
            │
            ▼
    1. 字段映射（field_mapping）  → 统一字段名
    2. 实体解析（entity_resolver）→ 球队/联赛/球员名 → ID
    3. 增量 upsert（versioning）  → 按 data_hash 决定 created/updated/skipped
    4. Redis 缓存（live_service） → 进行中比赛写 live:{match_id}
    5. WebSocket 推送（ConnectionManager）→ 订阅了对应联赛的前端连接收到更新
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.cleaning.field_mapping import map_fields
from app.cleaning.entity_resolver import (
    resolve_league, resolve_team, resolve_player, resolve_season,
)
from app.services.versioning import VersioningService
from app.models.match import Match
from app.models.match_event import MatchEvent
from app.models.player import Player
from app.models.player_stat import PlayerStat
from app.models.shot import Shot
from app.models.standings import Standings
from app.models.team_stat import TeamStat
from app.models.season import Season
from app.services.season_resolver import resolve_latest_season

# 这些数据源的爬虫直接返回标准字段名（goals/assists/xg/...），ingest 时跳过 map_fields
STANDARD_FIELD_SOURCES = {"fbref", "fifa_official"}
FIFA_DEFAULT_LEAGUE_NAME = "世界杯"
FIFA_DEFAULT_SEASON_NAME = "2026"
LIVE_MATCH_STATUSES = {"playing", "live", "in_progress", "half_time"}

logger = logging.getLogger(__name__)
_versioning = VersioningService()


def ingest_matches(db: Session, raw_matches: list[dict], source: str = "dongqiudi",
                   league_name: str | None = None, season_name: str | None = None) -> dict:
    """入库比赛数据（赛程/比分）

    Args:
        db: 数据库会话
        raw_matches: 爬虫返回的比赛列表，每条含 home_team/away_team/home_score 等
        source: 数据源编码
        league_name: 联赛名称（若 raw 数据里没带 league 字段，用此兜底）
        season_name: 赛季名称
    Returns:
        dict: {"created": n, "updated": n, "skipped": n, "failed": n}
    """
    stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}

    # 联赛/赛季在循环外解析一次（同一批数据通常属于同一联赛赛季）
    resolved_league_id = None
    resolved_season_id = None

    skip_mapping = source in STANDARD_FIELD_SOURCES
    league_name, season_name = _normalize_ingest_context(source, league_name, season_name)

    for raw in raw_matches:
        try:
            # 1. 字段映射
            std = raw if skip_mapping else map_fields(raw, source)
            if source == "fifa_official":
                std = {
                    **std,
                    "league": league_name or FIFA_DEFAULT_LEAGUE_NAME,
                    "season": season_name or FIFA_DEFAULT_SEASON_NAME,
                }

            # 2. 解析联赛（优先用数据自带的 league 字段，否则用 league_name 参数）
            lg_name = league_name or std.get("league")
            if lg_name and resolved_league_id is None:
                resolved_league_id = resolve_league(db, lg_name, source)
            league_id = resolved_league_id

            # 赛季
            sn = season_name or std.get("season")
            if sn and league_id and resolved_season_id is None:
                resolved_season_id = resolve_season(db, league_id, sn, source)
            season_id = resolved_season_id

            # 3. 解析主客队
            home_id = resolve_team(db, std.get("home_team", ""), source) if std.get("home_team") else None
            away_id = resolve_team(db, std.get("away_team", ""), source) if std.get("away_team") else None

            # 4. 构造 Match 数据
            if source == "fifa_official" and std.get("date_time_iso"):
                match_date = _parse_date_iso(std.get("date_time_iso"))
            else:
                match_date = _parse_date(std.get("date"), std.get("time"))
            # 推断比赛状态：有比分 → finished，否则 scheduled
            home_score = std.get("home_score")
            away_score = std.get("away_score")
            inferred_status = (
                "finished"
                if (home_score is not None and away_score is not None)
                else "scheduled"
            )
            data = {
                "league_id": league_id,
                "season_id": season_id,
                "matchday": std.get("matchday"),
                "home_team_id": home_id,
                "away_team_id": away_id,
                "home_score": home_score,
                "away_score": away_score,
                "status": std.get("status") or inferred_status,
                "match_date": match_date,
                "venue": std.get("venue"),
                "stage": std.get("stage"),
                "group_name": std.get("group"),
                "data_source": source,
            }
            # source_id 用 主队-客队-日期 保证唯一
            source_id = std.get("match_id") or f"{home_id}-{away_id}-{std.get('date', '')}"

            # 5. upsert
            result = _versioning.upsert(db, Match, source_id, data)
            stats[result["action"]] = stats.get(result["action"], 0) + 1

        except Exception as e:
            logger.error("入库比赛失败: %s | raw=%s", e, raw)
            stats["failed"] += 1

    logger.info("[%s] 比赛入库完成: %s", source, stats)
    return stats


def ingest_standings(db: Session, raw_standings: list[dict], source: str = "dongqiudi",
                     league_name: str | None = None, season_name: str | None = None) -> dict:
    """入库积分榜数据"""
    stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
    skip_mapping = source in STANDARD_FIELD_SOURCES
    league_name, season_name = _normalize_ingest_context(source, league_name, season_name)
    sample = raw_standings[0] if raw_standings else {}
    sample_std = sample if skip_mapping else map_fields(sample, source) if sample else {}
    eff_league = league_name or sample_std.get("league")
    eff_season = season_name or sample_std.get("season")
    league_id = resolve_league(db, eff_league, source) if eff_league else None
    season_id = resolve_season(db, league_id, eff_season, source) if (league_id and eff_season) else None

    for raw in raw_standings:
        try:
            std = raw if skip_mapping else map_fields(raw, source)
            team_id = resolve_team(db, std.get("team", ""), source)
            if not team_id or not season_id:
                stats["failed"] += 1
                continue

            data = {
                "season_id": season_id,
                "team_id": team_id,
                "position": std.get("position"),
                "played": std.get("played", 0),
                "won": std.get("won", 0),
                "drawn": std.get("drawn", 0),
                "lost": std.get("lost", 0),
                "goals_for": std.get("goals_for", 0),
                "goals_against": std.get("goals_against", 0),
                "goal_diff": std.get("goal_diff", 0),
                "points": std.get("points", 0),
                "form": std.get("form"),
                "group_name": std.get("group"),
                "stage": std.get("stage"),
                "qualification_status": std.get("qualification_status"),
                "data_source": source,
            }
            source_id = f"{season_id}-{team_id}"
            result = _versioning.upsert(db, Standings, source_id, data)
            stats[result["action"]] = stats.get(result["action"], 0) + 1
        except Exception as e:
            logger.error("入库积分榜失败: %s | raw=%s", e, raw)
            stats["failed"] += 1

    logger.info("[%s] 积分榜入库完成: %s", source, stats)
    return stats


def ingest_player_stats(db: Session, raw_stats: list[dict], source: str = "dongqiudi",
                        season_name: str | None = None, league_name: str | None = None) -> dict:
    """入库球员统计数据

    对于 source 在 STANDARD_FIELD_SOURCES（如 fbref）的数据，爬虫已返回标准字段名，
    跳过 map_fields，直接用 raw 中的字段。
    """
    stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}

    # 解析 season_id：优先用参数 season_name + league_name，其次用第一条 raw 的 season/league
    season_id = None
    sample = raw_stats[0] if raw_stats else {}
    league_name, season_name = _normalize_ingest_context(source, league_name, season_name)
    eff_league = league_name or sample.get("league")
    eff_season = season_name or sample.get("season")
    league_id = None
    if eff_league and eff_season:
        league_id = resolve_league(db, eff_league, source)
        if league_id:
            season_id = resolve_season(db, league_id, eff_season, source)
    if season_id is None:
        season_obj = resolve_latest_season(db, league_id=league_id, season_name=eff_season)
        season_id = season_obj.id if season_obj else None

    skip_mapping = source in STANDARD_FIELD_SOURCES

    for raw in raw_stats:
        try:
            std = raw if skip_mapping else map_fields(raw, source)
            # 解析球队和球员
            team_name = std.get("team")
            team_id = resolve_team(db, team_name, source) if team_name else None
            player_id = resolve_player(db, std.get("name", ""), team_id,
                                       std.get("position"), source)
            if not player_id or not season_id:
                stats["failed"] += 1
                continue

            _update_player_profile(
                db,
                player_id,
                {
                    "position": std.get("position"),
                    "shirt_number": std.get("shirt_number"),
                    "nationality": std.get("nationality"),
                    "birth_date": std.get("birth_date"),
                    "height": std.get("height"),
                    "weight": std.get("weight"),
                    "photo_url": std.get("photo_url"),
                    "saves": std.get("saves"),
                    "save_rate": std.get("save_rate"),
                    "xcs": std.get("xcs"),
                    "sweeper_actions": std.get("sweeper_actions"),
                    "team_id": team_id,
                    "data_source": source,
                    "source_id": std.get("player_source_id") or std.get("source_id"),
                },
            )

            data = {
                "player_id": player_id,
                "season_id": season_id,
                "appearances": std.get("appearances", 0) or 0,
                "goals": std.get("goals", 0) or 0,
                "assists": std.get("assists", 0) or 0,
                "yellow_cards": std.get("yellow_cards", 0) or 0,
                "red_cards": std.get("red_cards", 0) or 0,
                "minutes_played": std.get("minutes_played", 0) or 0,
                "shots": std.get("shots", 0) or 0,
                "shots_on_target": std.get("shots_on_target", 0) or 0,
                "xg": std.get("xg", 0) or 0,
                "xa": std.get("xa", 0) or 0,
                "passes": std.get("passes", 0) or 0,
                "pass_accuracy": std.get("pass_accuracy", 0) or 0,
                "tackles": std.get("tackles", 0) or 0,
                "interceptions": std.get("interceptions", 0) or 0,
                "rating": std.get("rating", 0) or 0,
                "data_source": source,
            }
            source_id = f"{player_id}-{season_id}"
            result = _versioning.upsert(db, PlayerStat, source_id, data)
            stats[result["action"]] = stats.get(result["action"], 0) + 1
        except Exception as e:
            logger.error("入库球员统计失败: %s | raw=%s", e, raw)
            stats["failed"] += 1

    logger.info("[%s] 球员统计入库完成: %s", source, stats)
    return stats


def ingest_team_stats(db: Session, raw_stats: list[dict], source: str = "dongqiudi",
                      season_name: str | None = None, league_name: str | None = None) -> dict:
    """入库球队赛季统计数据

    FBref 球队统计表返回字段：team, played, won, drawn, lost, goals_for, goals_against,
    goal_diff, points, xg_for, xg_against, possession
    """
    stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}

    # 解析 season_id
    sample = raw_stats[0] if raw_stats else {}
    league_name, season_name = _normalize_ingest_context(source, league_name, season_name)
    eff_league = league_name or sample.get("league")
    eff_season = season_name or sample.get("season")
    season_id = None
    league_id = None
    if eff_league and eff_season:
        league_id = resolve_league(db, eff_league, source)
        if league_id:
            season_id = resolve_season(db, league_id, eff_season, source)
    if season_id is None:
        season_obj = resolve_latest_season(db, league_id=league_id, season_name=eff_season)
        season_id = season_obj.id if season_obj else None

    skip_mapping = source in STANDARD_FIELD_SOURCES

    for raw in raw_stats:
        try:
            std = raw if skip_mapping else map_fields(raw, source)
            team_id = resolve_team(db, std.get("team", ""), source) if std.get("team") else None
            if not team_id or not season_id:
                stats["failed"] += 1
                continue

            data = {
                "team_id": team_id,
                "season_id": season_id,
                "matches_played": std.get("played", 0) or 0,
                "wins": std.get("won", 0) or 0,
                "draws": std.get("drawn", 0) or 0,
                "losses": std.get("lost", 0) or 0,
                "goals_for": std.get("goals_for", 0) or 0,
                "goals_against": std.get("goals_against", 0) or 0,
                "xg_for": std.get("xg_for", 0) or 0,
                "xg_against": std.get("xg_against", 0) or 0,
                "possession": std.get("possession", 0) or 0,
                # FBref 标准统计表不含以下字段，保持默认 0
                "shots_total": std.get("shots_total", 0) or 0,
                "shots_on_target_total": std.get("shots_on_target_total", 0) or 0,
                "passes_total": std.get("passes_total", 0) or 0,
                "pass_accuracy": std.get("pass_accuracy", 0) or 0,
                "corners": std.get("corners", 0) or 0,
                "fouls": std.get("fouls", 0) or 0,
                "clean_sheets": std.get("clean_sheets", 0) or 0,
                "data_source": source,
            }
            source_id = f"{team_id}-{season_id}"
            result = _versioning.upsert(db, TeamStat, source_id, data)
            stats[result["action"]] = stats.get(result["action"], 0) + 1
        except Exception as e:
            logger.error("入库球队统计失败: %s | raw=%s", e, raw)
            stats["failed"] += 1

    if season_id:
        _refresh_team_stat_ratings(db, season_id)

    logger.info("[%s] 球队统计入库完成: %s", source, stats)
    return stats


def ingest_events(db: Session, raw_events: list[dict], match_id: int | None = None,
                  source: str = "dongqiudi") -> dict:
    """入库比赛事件（进球/换人/红黄牌）"""
    stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
    match_obj = db.query(Match).filter(Match.id == match_id).first() if match_id else None

    for raw in raw_events:
        try:
            is_normalized_event = any(key in raw for key in ("event_type", "detail", "source_id", "player"))
            std = raw if (source in STANDARD_FIELD_SOURCES or is_normalized_event) else map_fields(raw, source)
            team_name = std.get("team")
            player_name = std.get("player")
            if team_name == "home" and match_obj:
                team_id = match_obj.home_team_id
            elif team_name == "away" and match_obj:
                team_id = match_obj.away_team_id
            else:
                team_id = resolve_team(db, team_name, source) if team_name else None
            player_id = resolve_player(db, player_name, team_id, None, source) if player_name else None

            data = {
                "match_id": match_id or std.get("match_id"),
                "minute": std.get("minute"),
                "event_type": std.get("event_type") or std.get("type"),
                "team_id": team_id,
                "player_id": player_id,
                "detail": std.get("detail") or std.get("description"),
                "data_source": std.get("data_source") or source,
            }
            source_id = std.get("source_id") or f"{data['match_id']}-{data.get('minute')}-{player_id}-{data.get('event_type')}"
            result = _versioning.upsert(db, MatchEvent, source_id, data)
            stats[result["action"]] = stats.get(result["action"], 0) + 1
        except Exception as e:
            logger.error("入库事件失败: %s | raw=%s", e, raw)
            stats["failed"] += 1

    logger.info("[%s] 事件入库完成: %s", source, stats)
    return stats


def ingest_shots(
    db: Session,
    raw_shots: list[dict],
    source: str = "understat",
    season_name: str | None = None,
    league_name: str | None = None,
) -> dict:
    """入库射门事件（坐标 + xG）。"""

    stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
    skip_mapping = source in STANDARD_FIELD_SOURCES
    league_name, season_name = _normalize_ingest_context(source, league_name, season_name)
    _ = league_name, season_name

    for raw in raw_shots:
        try:
            std = raw if skip_mapping else map_fields(raw, source)
            match_source_id = std.get("match_id") or raw.get("match_id") or raw.get("match_id_sb")
            match_obj = None
            if match_source_id is not None:
                match_obj = db.query(Match).filter(Match.source_id == str(match_source_id)).first()
            if not match_obj and raw.get("match_id") is not None:
                match_obj = db.query(Match).filter(Match.id == raw.get("match_id")).first()
            if not match_obj:
                match_obj = _resolve_match_for_shot(db, raw)

            team_name = (
                std.get("team")
                or raw.get("team")
                or raw.get("team_name")
                or (raw.get("home_team") if raw.get("side") == "home" else raw.get("away_team") if raw.get("side") == "away" else None)
            )
            player_name = std.get("player") or raw.get("player_name") or raw.get("name")
            team_id = resolve_team(db, team_name, source) if team_name else None
            player_id = resolve_player(db, player_name, team_id, None, source) if player_name else None

            x_coord = raw.get("x_coord_100")
            y_coord = raw.get("y_coord_100")
            if x_coord is None:
                x_coord = raw.get("x_coord")
            if y_coord is None:
                y_coord = raw.get("y_coord")

            data = {
                "match_id": match_obj.id if match_obj else None,
                "player_id": player_id,
                "team_id": team_id,
                "minute": raw.get("minute"),
                "x_coord": x_coord,
                "y_coord": y_coord,
                "result": raw.get("result"),
                "shot_type": raw.get("shot_type"),
                "situation": raw.get("situation"),
                "xg": raw.get("xg"),
                "data_source": source,
            }
            if not data["match_id"] or data["minute"] is None:
                stats["failed"] += 1
                continue

            source_id = (
                raw.get("shot_id")
                or raw.get("source_id")
                or f"{data['match_id']}-{data['minute']}-{player_id}-{data.get('result')}-{x_coord}-{y_coord}"
            )
            result = _versioning.upsert(db, Shot, source_id, data)
            stats[result["action"]] = stats.get(result["action"], 0) + 1
        except Exception as e:
            logger.error("入库射门失败: %s | raw=%s", e, raw)
            stats["failed"] += 1

    logger.info("[%s] 射门入库完成: %s", source, stats)
    return stats


async def push_live_update(match_id: int, league_id: int, match_data: dict):
    """比赛数据变更后：写 Redis 缓存 + WebSocket 推送

    供实时采集任务在 upsert 后调用，把变更秒级触达前端。

    比赛时段（开赛后约 3h 内）即使上游 status 不是 playing，
    只要带比分也按 live 写缓存并推送，保证实时比分稳定触达前端。
    """
    from app.services.live_service import LiveService
    live_svc = LiveService()

    status_raw = str(match_data.get("status") or "").strip().lower()
    has_scores = match_data.get("home_score") is not None or match_data.get("away_score") is not None
    is_live_status = status_raw in LIVE_MATCH_STATUSES

    # 比赛时段推断：基于开赛时间窗口判断是否在比赛中（弥补上游 status 回传延迟）
    in_match_window = _is_within_match_window(match_data.get("match_date"))
    treat_as_live = is_live_status or (in_match_window and has_scores)

    try:
        if treat_as_live:
            # 统一对外状态为 live，便于前端消费
            enriched = dict(match_data)
            if is_live_status and status_raw == "playing":
                enriched["status"] = "live"
            elif not is_live_status:
                enriched["status"] = "live"
            await live_svc.update_live_cache(match_id, enriched)
            match_data = enriched
        else:
            await live_svc.clear_live_cache(match_id)
    except Exception as exc:
        logger.warning("Live cache update skipped for match_id=%s because Redis is unavailable: %s", match_id, exc)

    # 2. WebSocket 推送给订阅了该联赛的连接
    from app.api.websocket import manager
    await manager.publish_to_league(league_id, {
        "type": "match_update",
        "data": {
            "match_id": match_id,
            "league_id": league_id,
            **match_data,
        },
    })


def _is_within_match_window(match_date_iso: str | None) -> bool:
    """判断当前是否处于比赛进行时间窗口（开赛后 ~3h 内）。

    用于 push_live_update：比赛时段即使上游 status 没标 playing，
    只要有比分也按 live 推送，确保实时比分稳定触达前端。
    """
    if not match_date_iso:
        return False
    try:
        from datetime import datetime, timedelta

        from app.services.match_service import MATCH_LIVE_WINDOW_HOURS, get_worldcup_reference_now

        # 容忍 ISO 末尾带 Z
        kickoff = datetime.fromisoformat(str(match_date_iso).replace("Z", "+00:00"))
        if kickoff.tzinfo is not None:
            kickoff = kickoff.replace(tzinfo=None)
        now = get_worldcup_reference_now()
        elapsed = now - kickoff
        return timedelta(0) <= elapsed <= timedelta(hours=MATCH_LIVE_WINDOW_HOURS)
    except (ValueError, TypeError):
        return False


def _parse_date(date_str: str | None, time_str: str | None = None):
    """解析日期+时间为 datetime，失败返回 None

    支持两种日期格式：
    - %Y-%m-%d（ISO 风格，OpenLigaDB/TheSportsDB 等）
    - %d/%m/%Y（Football-Data CSV 风格，如 16/08/2024）
    """
    if not date_str:
        return None
    ds = date_str.strip()
    time_fmts = ["%H:%M", "%H:%M:%S"]
    date_fmts = ["%Y-%m-%d", "%d/%m/%Y"]

    for date_fmt in date_fmts:
        try:
            if time_str:
                ts = time_str.strip()
                for time_fmt in time_fmts:
                    try:
                        return datetime.strptime(f"{ds} {ts}", f"{date_fmt} {time_fmt}")
                    except ValueError:
                        continue
            return datetime.strptime(ds, date_fmt)
        except ValueError:
            continue
    return None


def _parse_date_iso(value: str | None):
    """Parse an ISO datetime string and preserve its actual absolute time."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _update_player_profile(db: Session, player_id: int, profile: dict):
    """Best-effort sync of player bio fields discovered during stat ingestion."""
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        return

    if profile.get("team_id"):
        player.team_id = profile["team_id"]
    if profile.get("position"):
        player.position = profile["position"]
    if profile.get("shirt_number") is not None:
        player.shirt_number = profile["shirt_number"]
    if profile.get("nationality"):
        player.nationality = profile["nationality"]
    if profile.get("height") is not None:
        player.height = profile["height"]
    if profile.get("weight") is not None:
        player.weight = profile["weight"]
    if profile.get("photo_url"):
        player.photo_url = profile["photo_url"]
    if profile.get("saves") is not None:
        player.saves = profile["saves"]
    if profile.get("save_rate") is not None:
        player.save_rate = profile["save_rate"]
    if profile.get("xcs") is not None:
        player.xcs = profile["xcs"]
    if profile.get("sweeper_actions") is not None:
        player.sweeper_actions = profile["sweeper_actions"]
    if profile.get("data_source"):
        player.data_source = profile["data_source"]
    if profile.get("source_id"):
        player.source_id = str(profile["source_id"])

    birth_date = profile.get("birth_date")
    if birth_date and not player.birth_date:
        try:
            player.birth_date = datetime.strptime(str(birth_date), "%Y-%m-%d").date()
        except ValueError:
            pass

    db.commit()


def _normalize_ingest_context(
    source: str,
    league_name: str | None,
    season_name: str | None,
) -> tuple[str | None, str | None]:
    if source != "fifa_official":
        return league_name, season_name
    return league_name or FIFA_DEFAULT_LEAGUE_NAME, season_name or FIFA_DEFAULT_SEASON_NAME


def _resolve_match_for_shot(db: Session, raw: dict) -> Match | None:
    home_team = raw.get("home_team")
    away_team = raw.get("away_team")
    date_str = raw.get("date")
    if not home_team or not away_team or not date_str:
        return None

    parsed_date = None
    try:
        parsed_date = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed_date = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
        except ValueError:
            return None

    home_team_id = resolve_team(db, home_team, raw.get("source", "unknown"))
    away_team_id = resolve_team(db, away_team, raw.get("source", "unknown"))
    if not home_team_id or not away_team_id:
        return None

    day_prefix = parsed_date.strftime("%Y-%m-%d")
    return (
        db.query(Match)
        .filter(
            Match.home_team_id == home_team_id,
            Match.away_team_id == away_team_id,
            Match.match_date.like(f"{day_prefix}%"),
        )
        .order_by(Match.id.asc())
        .first()
    )


def _refresh_team_stat_ratings(db: Session, season_id: int):
    rows = db.query(TeamStat).filter(TeamStat.season_id == season_id).all()
    if not rows:
        return

    attack_components = {
        "goals_for": (0.35, False),
        "xg_for": (0.25, False),
        "shots_total": (0.20, False),
        "shots_on_target_total": (0.20, False),
    }
    defense_components = {
        "goals_against": (0.45, True),
        "xg_against": (0.35, True),
        "clean_sheets": (0.20, False),
    }

    for row in rows:
        row.attack_rating = round(_weighted_stat_score(row, rows, attack_components), 2)
        row.defense_rating = round(_weighted_stat_score(row, rows, defense_components), 2)

    attack_pool = [float(item.attack_rating or 0) for item in rows]
    defense_pool = [float(item.defense_rating or 0) for item in rows]
    possession_pool = [float(item.possession or 0) for item in rows]
    pass_accuracy_pool = [float(item.pass_accuracy or 0) for item in rows]
    shot_accuracy_pool = [
        ((float(item.shots_on_target_total or 0) / float(item.shots_total or 1)) * 100)
        if (item.shots_total or 0) > 0
        else 0.0
        for item in rows
    ]

    for row in rows:
        shot_accuracy = (
            (float(row.shots_on_target_total or 0) / float(row.shots_total or 1)) * 100
            if (row.shots_total or 0) > 0
            else 0.0
        )
        row.overall_rating = round(
            _normalized_score(float(row.attack_rating or 0), attack_pool) * 0.35
            + _normalized_score(float(row.defense_rating or 0), defense_pool) * 0.35
            + _normalized_score(float(row.possession or 0), possession_pool) * 0.10
            + _normalized_score(float(row.pass_accuracy or 0), pass_accuracy_pool) * 0.10
            + _normalized_score(shot_accuracy, shot_accuracy_pool) * 0.10,
            2,
        )

    db.commit()


def _weighted_stat_score(
    row: TeamStat,
    rows: list[TeamStat],
    component_map: dict[str, tuple[float, bool]],
) -> float:
    total = 0.0
    for field, (weight, reverse) in component_map.items():
        population = [float(getattr(item, field) or 0) for item in rows]
        total += _normalized_score(float(getattr(row, field) or 0), population, reverse=reverse) * weight
    return total


def _normalized_score(value: float, population: list[float], reverse: bool = False) -> float:
    if not population:
        return 50.0
    low = min(population)
    high = max(population)
    if high == low:
        return 50.0
    normalized = (value - low) / (high - low) * 100
    normalized = max(0.0, min(100.0, normalized))
    return 100.0 - normalized if reverse else normalized
