"""Understat 爬虫 — 采集射门数据与 xG 时间线

Understat 页面结构：
- /league/shots/{league_id}/{season}  联赛射门数据页（含 shotsData 变量）
- /match/{match_id}                   比赛页（含 shotsData + away_shotsData 两个变量）

Understat 使用 JSONP-like 格式返回数据：
``var shotsData = JSON.parse('{...}');``
需用正则提取 JSON 字符串后解析。
"""

import logging
import json
import re
from datetime import datetime

from app.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


class UnderstatCrawler(BaseCrawler):
    """Understat 数据爬虫"""

    # Understat 联赛标识
    LEAGUE_ID = {
        "EPL": 1,
        "La Liga": 2,
        "Serie A": 3,
        "Bundesliga": 4,
        "Ligue 1": 5,
        "RFPL": 6,
    }

    def __init__(self):
        super().__init__(source_code="understat", base_url="https://understat.com/")

    def crawl(self, target: str, league: str = "EPL",
              season: str = "2025", **kwargs) -> list[dict]:
        """采集入口

        Args:
            target: 采集目标，支持 shots / xg_timeline
            league: 联赛简称（如 "EPL"）
            season: 赛季起始年份（如 "2025" 表示 2025-2026 赛季）
        """
        if target == "shots":
            return self._crawl_shots(league, season, **kwargs)
        elif target == "xg_timeline":
            return self._crawl_xg_timeline(league, season, **kwargs)
        else:
            logger.warning("不支持的目标: %s", target)
            return []

    @staticmethod
    def _parse_jsonp(text: str, var_name: str) -> list | dict:
        """从 Understat 返回的 JSONP-like 字符串中提取 JSON 数据

        Args:
            text: 响应文本
            var_name: JavaScript 变量名（如 "shotsData"）

        Returns:
            解析后的 list 或 dict
        """
        pattern = rf"{var_name}\s*=\s*JSON\.parse\('(.+?)'\)"
        match = re.search(pattern, text, re.DOTALL)
        if not match:
            logger.warning("未能在响应中匹配到变量: %s", var_name)
            return []
        # Understat 在 JSON 中对单引号做了 \\x27 转义
        raw = match.group(1).encode().decode("unicode_escape")
        return json.loads(raw)

    @staticmethod
    def _safe_int(val) -> int | None:
        """安全转换为 int"""
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_float(val) -> float | None:
        """安全转换为 float"""
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    # ──────────────────────────────────────────────────────
    # 1. 射门数据
    # ──────────────────────────────────────────────────────

    def _crawl_shots(self, league: str, season: str, **kwargs) -> list[dict]:
        """采集射门数据

        从 /league/shots/{league_id}/{season} 页面解析 shotsData 变量，
        字段标准化后写入 HDFS。

        字段映射：
            id        → shot_id     (避免与 player_id 冲突)
            X / Y     → x_coord / y_coord  (原 0-1 相对坐标 ×100)
            xG        → xg
            player    → player_name (对齐 field_mapping)
            h_a       → side        (h/a → home/away，供 xg_model 使用)
            h_team    → home_team
            a_team    → away_team
            shotType  → shot_type
        """
        league_id = self.LEAGUE_ID.get(league, 1)
        url = f"{self.base_url}league/shots/{league_id}/{season}"
        try:
            resp = self._fetch(url)
        except Exception as e:
            logger.error("Understat 射门数据页请求失败: %s", e)
            return []

        data = self._parse_jsonp(resp.text, "shotsData")
        raw_shots = data if isinstance(data, list) else []

        results: list[dict] = []
        for shot in raw_shots:
            if not isinstance(shot, dict):
                continue
            player_name = shot.get("player")
            match_id = self._safe_int(shot.get("match_id"))
            # 过滤无效记录
            if not player_name or match_id is None:
                continue

            h_a = shot.get("h_a")
            side = "home" if h_a == "h" else ("away" if h_a == "a" else None)

            x_raw = self._safe_float(shot.get("X"))
            y_raw = self._safe_float(shot.get("Y"))

            record = {
                "source": "understat",
                "league": league,
                "season": season,
                "shot_id": shot.get("id"),
                "match_id": match_id,
                "player_id": self._safe_int(shot.get("player_id")),
                "player_name": str(player_name),
                "minute": self._safe_int(shot.get("minute")),
                "x_coord": round(x_raw * 100, 3) if x_raw is not None else None,
                "y_coord": round(y_raw * 100, 3) if y_raw is not None else None,
                "xg": self._safe_float(shot.get("xG")),
                "result": shot.get("result"),
                "situation": shot.get("situation"),
                "shot_type": shot.get("shotType"),
                "side": side,
                "home_team": shot.get("h_team"),
                "away_team": shot.get("a_team"),
                "date": shot.get("date"),
                # 保留原始辅助字段，供后续分析使用
                "home_goals": self._safe_int(shot.get("h_goals")),
                "away_goals": self._safe_int(shot.get("a_goals")),
                "player_assisted": shot.get("player_assisted"),
                "last_action": shot.get("lastAction"),
            }
            results.append(record)

        # 保存到 HDFS
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/understat/shots/{league}_{season}_{ts}.json"
        try:
            self._save_raw_to_hdfs(results, hdfs_path)
        except Exception as e:
            logger.warning("HDFS 写入失败: %s", e)

        logger.info("[understat] 射门数据采集完成: %d 条 (league=%s, season=%s)",
                    len(results), league, season)
        return results

    # ──────────────────────────────────────────────────────
    # 2. xG 时间线
    # ──────────────────────────────────────────────────────

    def _crawl_xg_timeline(self, league: str, season: str, **kwargs) -> list[dict]:
        """采集 xG 时间线数据

        从 /match/{match_id} 页面解析主客两队 shotsData 变量，
        按分钟排序生成累计 xG 时间线。

        Returns:
            list 仅含一个比赛记录：
            [{
                "match_id": int,
                "home_team": str,
                "away_team": str,
                "final_home_xg": float,
                "final_away_xg": float,
                "timeline": [{minute, side, home_xg_cum, away_xg_cum, event}],
                "source": "understat"
            }]
        """
        match_id = kwargs.get("match_id")
        if not match_id:
            logger.warning("xg_timeline 需要提供 match_id 参数")
            return []

        url = f"{self.base_url}match/{match_id}"
        try:
            resp = self._fetch(url)
        except Exception as e:
            logger.error("Understat 比赛页请求失败: %s", e)
            return []

        home_shots = self._parse_jsonp(resp.text, "shotsData")
        away_shots = self._parse_jsonp(resp.text, "away_shotsData")
        home_list = home_shots if isinstance(home_shots, list) else []
        away_list = away_shots if isinstance(away_shots, list) else []

        # 合并主客并标注 side
        merged: list[dict] = []
        for s in home_list:
            if isinstance(s, dict):
                merged.append({**s, "side": "home"})
        for s in away_list:
            if isinstance(s, dict):
                merged.append({**s, "side": "away"})

        if not merged:
            logger.warning("[understat] match_id=%s 未解析到射门数据", match_id)
            return []

        # 按分钟升序排序
        merged.sort(key=lambda s: self._safe_int(s.get("minute")) or 0)

        # 累计 xG 时间线
        home_cum = 0.0
        away_cum = 0.0
        timeline: list[dict] = []
        home_team = ""
        away_team = ""

        for s in merged:
            minute = self._safe_int(s.get("minute")) or 0
            xg = self._safe_float(s.get("xG")) or 0.0
            side = s.get("side")

            if side == "home":
                home_cum += xg
                if not home_team:
                    home_team = s.get("h_team", "") or ""
            else:
                away_cum += xg
                if not away_team:
                    away_team = s.get("a_team", "") or ""

            timeline.append({
                "minute": minute,
                "side": side,
                "home_xg_cum": round(home_cum, 3),
                "away_xg_cum": round(away_cum, 3),
                "event": {
                    "player": s.get("player"),
                    "result": s.get("result"),
                    "xg": round(xg, 3),
                    "shot_type": s.get("shotType"),
                    "situation": s.get("situation"),
                },
            })

        record = {
            "match_id": self._safe_int(match_id),
            "home_team": home_team,
            "away_team": away_team,
            "final_home_xg": round(home_cum, 3),
            "final_away_xg": round(away_cum, 3),
            "timeline": timeline,
            "source": "understat",
        }

        # 保存到 HDFS
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/understat/xg_timeline/{match_id}_{ts}.json"
        try:
            self._save_raw_to_hdfs([record], hdfs_path)
        except Exception as e:
            logger.warning("HDFS 写入失败: %s", e)

        logger.info("[understat] xG 时间线采集完成: match_id=%s, %s %.2f vs %s %.2f (%d 个事件)",
                    match_id, home_team, home_cum, away_team, away_cum, len(timeline))
        return [record]
