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
from app.models.player_stat import PlayerStat
from app.models.standings import Standings

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

    for raw in raw_matches:
        try:
            # 1. 字段映射
            std = map_fields(raw, source)

            # 2. 解析联赛（优先用数据自带的 league 字段，否则用 league_name 参数）
            lg_name = std.get("league") or league_name
            if lg_name and resolved_league_id is None:
                resolved_league_id = resolve_league(db, lg_name, source)
            league_id = resolved_league_id

            # 赛季
            sn = std.get("season") or season_name
            if sn and league_id and resolved_season_id is None:
                resolved_season_id = resolve_season(db, league_id, sn, source)
            season_id = resolved_season_id

            # 3. 解析主客队
            home_id = resolve_team(db, std.get("home_team", ""), source) if std.get("home_team") else None
            away_id = resolve_team(db, std.get("away_team", ""), source) if std.get("away_team") else None

            # 4. 构造 Match 数据
            match_date = _parse_date(std.get("date"), std.get("time"))
            data = {
                "league_id": league_id,
                "season_id": season_id,
                "home_team_id": home_id,
                "away_team_id": away_id,
                "home_score": std.get("home_score"),
                "away_score": std.get("away_score"),
                "status": std.get("status", "scheduled"),
                "match_date": match_date,
            }
            # source_id 用 主队-客队-日期 保证唯一
            source_id = f"{home_id}-{away_id}-{std.get('date', '')}"

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
    league_id = resolve_league(db, league_name, source) if league_name else None
    season_id = resolve_season(db, league_id, season_name, source) if (league_id and season_name) else None

    for raw in raw_standings:
        try:
            std = map_fields(raw, source)
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
                        season_name: str | None = None) -> dict:
    """入库球员统计数据"""
    stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
    # 球员统计需要 season_id，但 season 关联 league，这里用一个全局最新赛季兜底
    from app.models.season import Season
    season_obj = db.query(Season).order_by(Season.id.desc()).first()
    season_id = season_obj.id if season_obj else None

    for raw in raw_stats:
        try:
            std = map_fields(raw, source)
            # 解析球队和球员
            team_id = resolve_team(db, std.get("team", ""), source) if std.get("team") else None
            player_id = resolve_player(db, std.get("name", ""), team_id,
                                       std.get("position"), source)
            if not player_id or not season_id:
                stats["failed"] += 1
                continue

            data = {
                "player_id": player_id,
                "season_id": season_id,
                "appearances": std.get("appearances", 0),
                "goals": std.get("goals", 0),
                "assists": std.get("assists", 0),
                "yellow_cards": std.get("yellow_cards", 0),
                "red_cards": std.get("red_cards", 0),
                "minutes_played": std.get("minutes_played", 0),
                "shots": std.get("shots", 0),
                "shots_on_target": std.get("shots_on_target", 0),
                "xg": std.get("xg", 0),
                "xa": std.get("xa", 0),
                "passes": std.get("passes", 0),
                "pass_accuracy": std.get("pass_accuracy", 0),
                "tackles": std.get("tackles", 0),
                "interceptions": std.get("interceptions", 0),
                "rating": std.get("rating", 0),
            }
            source_id = f"{player_id}-{season_id}"
            result = _versioning.upsert(db, PlayerStat, source_id, data)
            stats[result["action"]] = stats.get(result["action"], 0) + 1
        except Exception as e:
            logger.error("入库球员统计失败: %s | raw=%s", e, raw)
            stats["failed"] += 1

    logger.info("[%s] 球员统计入库完成: %s", source, stats)
    return stats


def ingest_events(db: Session, raw_events: list[dict], match_id: int | None = None,
                  source: str = "dongqiudi") -> dict:
    """入库比赛事件（进球/换人/红黄牌）"""
    stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}

    for raw in raw_events:
        try:
            std = map_fields(raw, source)
            team_id = resolve_team(db, std.get("team", ""), source) if std.get("team") else None
            player_id = resolve_player(db, std.get("player", ""), team_id, None, source) if std.get("player") else None

            data = {
                "match_id": match_id or std.get("match_id"),
                "minute": std.get("minute"),
                "event_type": std.get("event_type") or std.get("type"),
                "team_id": team_id,
                "player_id": player_id,
                "detail": std.get("detail") or std.get("description"),
            }
            source_id = f"{data['match_id']}-{data.get('minute')}-{player_id}-{data.get('event_type')}"
            result = _versioning.upsert(db, MatchEvent, source_id, data)
            stats[result["action"]] = stats.get(result["action"], 0) + 1
        except Exception as e:
            logger.error("入库事件失败: %s | raw=%s", e, raw)
            stats["failed"] += 1

    logger.info("[%s] 事件入库完成: %s", source, stats)
    return stats


async def push_live_update(match_id: int, league_id: int, match_data: dict):
    """比赛数据变更后：写 Redis 缓存 + WebSocket 推送

    供实时采集任务在 upsert 后调用，把变更秒级触达前端。
    """
    # 1. 写 Redis 缓存（供降级轮询 /api/v1/live 读取）
    from app.services.live_service import LiveService
    live_svc = LiveService()
    await live_svc.update_live_cache(match_id, match_data)

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


def _parse_date(date_str: str | None, time_str: str | None = None):
    """解析日期+时间为 datetime，失败返回 None"""
    if not date_str:
        return None
    try:
        fmt = "%Y-%m-%d"
        ds = date_str.strip()
        if time_str:
            return datetime.strptime(f"{ds} {time_str.strip()}", f"{fmt} %H:%M")
        # 尝试纯日期
        return datetime.strptime(ds, fmt)
    except (ValueError, TypeError):
        return None
