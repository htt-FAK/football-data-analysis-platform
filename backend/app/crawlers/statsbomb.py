"""StatsBomb Open Data 爬虫 — 免费 GitHub 开源事件级足球数据

数据源：https://github.com/statsbomb/open-data
通过 jsdelivr CDN 访问（国内稳定）：
    https://cdn.jsdelivr.net/gh/statsbomb/open-data@master/data/...

支持目标：
- matches:       比赛列表（赛程 + 比分）
- player_stats:  球员统计聚合（从 events 聚合 goals/assists/shots/xg 等）
- shots:         射门事件（含坐标 + xG）

默认数据集：2022 FIFA World Cup（competition_id=43, season_id=106，64 场比赛）
"""

import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Optional

import requests

from app.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)

# jsdelivr CDN 镜像（国内访问稳定）
SB_BASE = "https://cdn.jsdelivr.net/gh/statsbomb/open-data@master/data"

# StatsBomb 默认数据集：2022 FIFA World Cup
DEFAULT_COMPETITION_ID = 43
DEFAULT_SEASON_ID = 106


class StatsBombCrawler(BaseCrawler):
    """StatsBomb Open Data 爬虫"""

    # competition_id → 联赛名
    COMPETITION_NAMES = {
        43: "FIFA World Cup",
        72: "Women's World Cup",
        2: "Premier League",
        11: "La Liga",
        9: "Bundesliga",
        12: "Serie A",
        7: "Ligue 1",
        16: "Champions League",
        55: "UEFA Euro",
    }

    # 已知的 (competition_id, season_year) → season_id 映射
    SEASON_MAP = {
        (43, "2022"): 106,
        (43, "2018"): 3,
        (72, "2023"): 107,
        (72, "2019"): 30,
        (55, "2024"): 282,
        (55, "2020"): 43,
    }
    COMPETITION_ALIASES = {
        "fifa world cup": 43,
        "world cup": 43,
        "wc": 43,
        "世界杯": 43,
    }

    def __init__(self):
        super().__init__(source_code="statsbomb", base_url=SB_BASE)
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "Mozilla/5.0"})
        # events 缓存：match_id → events list（同一进程内避免重复下载）
        self._events_cache: dict[int, list[dict]] = {}

    # ──────────────────────────────────────────────────────
    # 通用工具
    # ──────────────────────────────────────────────────────

    def _fetch_json(self, path: str, timeout: int = 30) -> Optional[object]:
        """从 jsdelivr CDN 下载 JSON，3 次重试"""
        url = f"{self.base_url}/{path}"
        for attempt in range(3):
            try:
                r = self._session.get(url, timeout=timeout)
                if r.status_code == 200:
                    return r.json()
                logger.warning("[statsbomb] %s HTTP %d (尝试 %d/3)",
                               path, r.status_code, attempt + 1)
            except requests.RequestException as e:
                logger.warning("[statsbomb] %s 异常: %s (尝试 %d/3)",
                               path, e, attempt + 1)
            time.sleep(2)
        logger.error("[statsbomb] %s 3 次重试均失败", path)
        return None

    def _parse_comp_season(self, league: str | None, season: str | None):
        """解析 competition_id + season_id

        支持格式：
        1. league="43:106"             → 直接解析
        2. league="FIFA World Cup" + season="2022"  → 查映射
        3. 默认 43:106 (2022 World Cup)
        """
        if league and ":" in league:
            try:
                c, s = league.split(":", 1)
                return int(c), int(s)
            except ValueError:
                pass
        if league:
            alias_competition_id = self.COMPETITION_ALIASES.get(league.strip().lower())
            if alias_competition_id is not None:
                if season:
                    season_id = self.SEASON_MAP.get((alias_competition_id, season))
                    if season_id is None:
                        raise ValueError(
                            f"StatsBomb open data does not provide {self.COMPETITION_NAMES.get(alias_competition_id, league)} season {season}"
                        )
                    return alias_competition_id, season_id
                fallback_candidates = [
                    mapped_season_id
                    for (mapped_cid, _), mapped_season_id in self.SEASON_MAP.items()
                    if mapped_cid == alias_competition_id
                ]
                return (
                    alias_competition_id,
                    max(fallback_candidates) if fallback_candidates else DEFAULT_SEASON_ID,
                )
            for cid, name in self.COMPETITION_NAMES.items():
                if name.lower() == league.lower():
                    if season:
                        season_id = self.SEASON_MAP.get((cid, season))
                        if season_id is None:
                            raise ValueError(
                                f"StatsBomb open data does not provide {name} season {season}"
                            )
                        return cid, season_id
                    fallback_candidates = [
                        mapped_season_id
                        for (mapped_cid, _), mapped_season_id in self.SEASON_MAP.items()
                        if mapped_cid == cid
                    ]
                    return cid, max(fallback_candidates) if fallback_candidates else DEFAULT_SEASON_ID
        return DEFAULT_COMPETITION_ID, DEFAULT_SEASON_ID

    # ──────────────────────────────────────────────────────
    # 采集入口
    # ──────────────────────────────────────────────────────

    def crawl(self, target: str, league: str | None = None,
              season: str | None = None, **kwargs) -> list[dict]:
        """采集入口

        Args:
            target: matches / player_stats / shots
            league: 联赛标识，支持 "43:106" 格式或联赛英文名（如 "FIFA World Cup"）
            season: 赛季名（如 "2022"），用于日志
        """
        comp_id, season_id = self._parse_comp_season(league, season)
        logger.info("[statsbomb] target=%s competition_id=%d season_id=%d",
                    target, comp_id, season_id)

        dispatch = {
            "matches": self._crawl_matches,
            "player_stats": self._crawl_player_stats,
            "shots": self._crawl_shots,
        }
        handler = dispatch.get(target)
        if not handler:
            logger.warning("[statsbomb] 不支持的目标: %s", target)
            return []
        return handler(comp_id, season_id, season)

    # ──────────────────────────────────────────────────────
    # 1. 比赛列表
    # ──────────────────────────────────────────────────────

    def _crawl_matches(self, comp_id: int, season_id: int,
                       season_name: str | None = None) -> list[dict]:
        """采集比赛列表（赛程 + 比分）"""
        path = f"matches/{comp_id}/{season_id}.json"
        data = self._fetch_json(path)
        if not data:
            return []

        league_name = self.COMPETITION_NAMES.get(comp_id, "Unknown")
        results = []
        for m in data:
            home = m.get("home_team", {})
            away = m.get("away_team", {})
            home_score = m.get("home_score")
            away_score = m.get("away_score")
            results.append({
                "source": "statsbomb",
                "league": league_name,
                "season": season_name or str(season_id),
                "match_id": m.get("match_id"),
                "match_id_sb": m.get("match_id"),
                "match_date": m.get("match_date"),
                "time": m.get("kick_off"),
                "home_team": home.get("home_team_name"),
                "away_team": away.get("away_team_name"),
                "home_score": home_score,
                "away_score": away_score,
                "venue": m.get("stadium", {}).get("name") if m.get("stadium") else None,
                "stage": m.get("competition_stage", {}).get("name"),
                "status": "finished" if home_score is not None else "scheduled",
            })

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/statsbomb/matches/{league_name}_{season_name or season_id}_{ts}.json"
        try:
            self._save_raw_to_hdfs(results, hdfs_path)
        except Exception as e:
            logger.warning("[statsbomb] HDFS 写入失败: %s", e)

        logger.info("[statsbomb] 比赛采集完成: %d 条", len(results))
        return results

    # ──────────────────────────────────────────────────────
    # 2. 事件下载（共享缓存）
    # ──────────────────────────────────────────────────────

    def _download_all_events(self, comp_id: int, season_id: int) -> dict[int, list[dict]]:
        """下载该赛季所有比赛的 events，返回 match_id → events list"""
        path = f"matches/{comp_id}/{season_id}.json"
        matches = self._fetch_json(path)
        if not matches:
            return {}

        events_map = {}
        total = len(matches)
        for i, m in enumerate(matches, 1):
            mid = m.get("match_id")
            if not mid:
                continue
            if mid in self._events_cache:
                events_map[mid] = self._events_cache[mid]
                continue
            logger.info("[statsbomb] 下载 events %d/%d (match_id=%d)",
                        i, total, mid)
            events = self._fetch_json(f"events/{mid}.json", timeout=60)
            if events:
                self._events_cache[mid] = events
                events_map[mid] = events
            time.sleep(0.3)  # 避免请求过快触发限流
        return events_map

    @staticmethod
    def _resolve_team_position(events: list[dict]):
        """扫描 events，建立 (player_id, player_name) → (team, position) 映射"""
        player_team: dict[tuple, str] = {}
        player_position: dict[tuple, str] = {}
        for ev in events:
            player = ev.get("player")
            if not player:
                continue
            pid = player.get("id")
            pname = player.get("name")
            team = ev.get("team", {}).get("name")
            pos = ev.get("position", {}).get("name") if ev.get("position") else None
            if not pid or not pname:
                continue
            key = (pid, pname)
            if key not in player_team and team:
                player_team[key] = team
            if key not in player_position and pos and pos != "Substitute":
                player_position[key] = pos
        return player_team, player_position

    # ──────────────────────────────────────────────────────
    # 3. 球员统计聚合
    # ──────────────────────────────────────────────────────

    def _crawl_player_stats(self, comp_id: int, season_id: int,
                            season_name: str | None = None) -> list[dict]:
        """从 events 聚合球员统计

        返回字段（标准字段名，与 ingest_player_stats 期望对齐）：
            name, team, position, appearances, minutes_played,
            goals, assists, shots, shots_on_target, xg,
            passes, passes_completed, yellow_cards, red_cards,
            player_id_sb
        """
        events_map = self._download_all_events(comp_id, season_id)
        if not events_map:
            return []

        league_name = self.COMPETITION_NAMES.get(comp_id, "Unknown")

        # 聚合字典：player_key → stats
        stats_map: dict[tuple, dict] = defaultdict(lambda: {
            "name": None, "team": None, "position": None,
            "matches_played_set": set(),
            "goals": 0, "assists": 0, "shots": 0, "shots_on_target": 0,
            "xg": 0.0, "passes": 0, "passes_completed": 0,
            "yellow_cards": 0, "red_cards": 0,
        })

        for mid, events in events_map.items():
            player_team, player_position = self._resolve_team_position(events)

            for ev in events:
                player = ev.get("player")
                if not player:
                    continue
                pid = player.get("id")
                pname = player.get("name")
                if not pid or not pname:
                    continue
                key = (pid, pname)
                stats = stats_map[key]
                stats["name"] = pname
                stats["team"] = player_team.get(key) or stats["team"]
                stats["position"] = player_position.get(key) or stats["position"]
                stats["matches_played_set"].add(mid)

                ev_type = ev.get("type", {}).get("name")
                if ev_type == "Shot":
                    stats["shots"] += 1
                    shot = ev.get("shot", {}) or {}
                    xg = shot.get("statsbomb_xg")
                    if xg is not None:
                        stats["xg"] += float(xg)
                    outcome = shot.get("outcome", {}).get("name")
                    if outcome in ("Goal", "Saved", "Saved To Post"):
                        stats["shots_on_target"] += 1
                    if outcome == "Goal":
                        stats["goals"] += 1
                elif ev_type == "Pass":
                    stats["passes"] += 1
                    pass_data = ev.get("pass", {}) or {}
                    # outcome 为 None 表示传球成功
                    if pass_data.get("outcome") is None:
                        stats["passes_completed"] += 1
                    if pass_data.get("goal_assist"):
                        stats["assists"] += 1
                elif ev_type == "Foul Committed":
                    card = (ev.get("foul_committed") or {}).get("card", {})
                    card_name = card.get("name") if card else None
                    if card_name == "Yellow Card":
                        stats["yellow_cards"] += 1
                    elif card_name in ("Red Card", "Second Yellow"):
                        stats["red_cards"] += 1

        # 最终聚合
        results = []
        for (pid, pname), stats in stats_map.items():
            appearances = len(stats["matches_played_set"])
            # minutes_played 简化估算：每场按 90 分钟（精确计算需 substitution 事件分析）
            minutes_played = appearances * 90
            pass_accuracy = (
                round(stats["passes_completed"] / stats["passes"], 3)
                if stats["passes"] > 0 else 0.0
            )
            results.append({
                "source": "statsbomb",
                "league": league_name,
                "season": season_name or str(season_id),
                "player_id_sb": pid,
                "name": pname,
                "team": stats["team"],
                "position": stats["position"],
                "appearances": appearances,
                "minutes_played": minutes_played,
                "goals": stats["goals"],
                "assists": stats["assists"],
                "shots": stats["shots"],
                "shots_on_target": stats["shots_on_target"],
                "xg": round(stats["xg"], 3),
                "passes": stats["passes"],
                "passes_completed": stats["passes_completed"],
                "pass_accuracy": pass_accuracy,
                "yellow_cards": stats["yellow_cards"],
                "red_cards": stats["red_cards"],
            })

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/statsbomb/player_stats/{league_name}_{season_name or season_id}_{ts}.json"
        try:
            self._save_raw_to_hdfs(results, hdfs_path)
        except Exception as e:
            logger.warning("[statsbomb] HDFS 写入失败: %s", e)

        logger.info("[statsbomb] 球员统计聚合完成: %d 条", len(results))
        return results

    # ──────────────────────────────────────────────────────
    # 4. 射门事件
    # ──────────────────────────────────────────────────────

    def _crawl_shots(self, comp_id: int, season_id: int,
                     season_name: str | None = None) -> list[dict]:
        """从 events 提取射门事件

        返回字段（标准字段名）：
            match_id_sb, player_name, player_id_sb, team, side,
            minute, second, x_coord, y_coord, x_coord_100, y_coord_100,
            result, shot_type, situation, xg, period
        """
        match_rows = self._fetch_json(f"matches/{comp_id}/{season_id}.json")
        match_meta = {
            row.get("match_id"): row
            for row in (match_rows or [])
            if isinstance(row, dict) and row.get("match_id")
        }
        events_map = self._download_all_events(comp_id, season_id)
        if not events_map:
            return []

        league_name = self.COMPETITION_NAMES.get(comp_id, "Unknown")
        results = []
        for mid, events in events_map.items():
            match_row = match_meta.get(mid, {})
            match_date = match_row.get("match_date")
            # 先确定主客队（用第一周期的 team 字段）
            home_team = None
            away_team = None
            for ev in events:
                if ev.get("period") == 1 and ev.get("team"):
                    team_name = ev["team"].get("name")
                    if home_team is None:
                        home_team = team_name
                    elif team_name != home_team:
                        away_team = team_name
                        break

            for ev in events:
                if ev.get("type", {}).get("name") != "Shot":
                    continue
                player = ev.get("player", {}) or {}
                team = ev.get("team", {}) or {}
                shot = ev.get("shot", {}) or {}
                location = ev.get("location") or [None, None]
                team_name = team.get("name")
                side = "home" if team_name == home_team else "away"

                results.append({
                    "source": "statsbomb",
                    "league": league_name,
                    "season": season_name or str(season_id),
                    "match_id": mid,
                    "match_id_sb": mid,
                    "player_name": player.get("name"),
                    "player_id_sb": player.get("id"),
                    "team": team_name,
                    "side": side,
                    "minute": ev.get("minute"),
                    "second": ev.get("second"),
                    # StatsBomb 坐标系：0-120 (length), 0-80 (width)
                    "x_coord": location[0] if location else None,
                    "y_coord": location[1] if location else None,
                    # 转 0-100 标准化（便于前端可视化）
                    "x_coord_100": round(location[0] / 1.2, 2) if location[0] is not None else None,
                    "y_coord_100": round(location[1] / 0.8, 2) if location[1] is not None else None,
                    "result": shot.get("outcome", {}).get("name"),
                    "shot_type": (shot.get("body_part") or {}).get("name"),
                    "situation": (shot.get("type") or {}).get("name"),
                    "xg": shot.get("statsbomb_xg"),
                    "period": ev.get("period"),
                    "home_team": home_team,
                    "away_team": away_team,
                    "date": match_date,
                    "event_timestamp": ev.get("timestamp"),
                    "source_id": ev.get("id"),
                })

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/statsbomb/shots/{league_name}_{season_name or season_id}_{ts}.json"
        try:
            self._save_raw_to_hdfs(results, hdfs_path)
        except Exception as e:
            logger.warning("[statsbomb] HDFS 写入失败: %s", e)

        logger.info("[statsbomb] 射门事件采集完成: %d 条", len(results))
        return results
