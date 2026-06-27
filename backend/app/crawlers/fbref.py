"""FBref 爬虫 — 采集球队统计、球员统计、积分榜、比赛报告

FBref 页面结构：
- /comps/{id}/{season}/{season}-{league}-Stats  联赛主页（含积分榜+球队统计）
- /comps/{id}/{season}/players/{season}-{league}-Stats  球员统计页
- /matches/{match_id}/...  比赛报告页

所有数据以 HTML 表格形式呈现，使用 pandas.read_html 解析。
"""

import logging
from datetime import datetime

import pandas as pd

from app.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


class FBrefCrawler(BaseCrawler):
    """FBref 数据爬虫，使用 pandas.read_html 解析 HTML 表格"""

    # FBref 联赛标识映射
    LEAGUE_ID = {
        "Premier League": "9",
        "La Liga": "12",
        "Serie A": "11",
        "Bundesliga": "20",
        "Ligue 1": "13",
    }

    def __init__(self):
        super().__init__(source_code="fbref", base_url="https://fbref.com/en/")

    def crawl(self, target: str, league: str = "Premier League",
              season: str = "2025-2026", **kwargs) -> list[dict]:
        """采集入口

        Args:
            target: 采集目标，支持 team_stats / standings / player_stats / match_report
            league: 联赛名称（如 "Premier League"）
            season: 赛季（如 "2025-2026"）
        """
        dispatch = {
            "team_stats": self._crawl_team_stats,
            "standings": self._crawl_standings,
            "player_stats": self._crawl_player_stats,
            "match_report": self._crawl_match_report,
        }
        handler = dispatch.get(target)
        if not handler:
            logger.warning("不支持的目标: %s", target)
            return []
        return handler(league, season, **kwargs)

    def _league_url(self, league: str, season: str) -> str:
        """根据联赛与赛季构造 FBref 联赛主页 URL"""
        league_id = self.LEAGUE_ID.get(league, "9")
        league_slug = league.replace(" ", "-")
        return f"{self.base_url}comps/{league_id}/{season}/{season}-{league_slug}-Stats"

    def _player_stats_url(self, league: str, season: str) -> str:
        """球员统计页 URL"""
        league_id = self.LEAGUE_ID.get(league, "9")
        league_slug = league.replace(" ", "-")
        return f"{self.base_url}comps/{league_id}/{season}/players/{season}-{league_slug}-Stats"

    @staticmethod
    def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
        """将多级列名展平为单级

        pandas.read_html 解析 FBref 表格时会产生多级列名，
        如 ('Performance', 'Gls') → 'Performance_Gls'
        """
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [
                "_".join(str(c) for c in col if c and str(c) != "nan")
                for col in df.columns.values
            ]
        return df

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
    # 1. 球队统计
    # ──────────────────────────────────────────────────────

    def _crawl_team_stats(self, league: str, season: str, **kwargs) -> list[dict]:
        """采集球队统计数据

        从联赛主页解析 "Squad Standard Stats" 表格，
        包含 xG/xGA/poss/shots 等高级统计。
        """
        url = self._league_url(league, season)
        try:
            resp = self._fetch(url)
        except Exception as e:
            logger.error("FBref 球队统计页请求失败: %s", e)
            return []

        results: list[dict] = []
        try:
            tables = pd.read_html(resp.text)
        except ValueError as e:
            logger.warning("FBref team_stats 表格解析失败: %s", e)
            return []

        for df in tables:
            df = self._flatten_columns(df)
            cols_lower = " ".join(str(c) for c in df.columns).lower()

            # 识别包含 Squad + MP + xG 的表格（球队标准统计表）
            if "squad" not in cols_lower:
                continue
            if "mp" not in cols_lower and "playing" not in cols_lower:
                continue

            for _, row in df.iterrows():
                record = {
                    "source": "fbref",
                    "league": league,
                    "season": season,
                }
                # 遍历所有列，尝试匹配标准字段
                for col in df.columns:
                    col_lower = str(col).lower().strip()
                    val = row[col]

                    if col_lower in ("squad", "team"):
                        record["team_name"] = str(val)
                    elif col_lower in ("rk", "rank"):
                        record["position"] = self._safe_int(val)
                    elif col_lower in ("mp", "playing time_mp"):
                        record["played"] = self._safe_int(val)
                    elif col_lower in ("w", "playing time_w"):
                        record["won"] = self._safe_int(val)
                    elif col_lower in ("d", "playing time_d"):
                        record["drawn"] = self._safe_int(val)
                    elif col_lower in ("l", "playing time_l"):
                        record["lost"] = self._safe_int(val)
                    elif col_lower in ("gf", "performance_gf"):
                        record["goals_for"] = self._safe_int(val)
                    elif col_lower in ("ga", "performance_ga"):
                        record["goals_against"] = self._safe_int(val)
                    elif col_lower in ("gd", "performance_gd"):
                        record["goal_diff"] = self._safe_int(val)
                    elif col_lower in ("pts", "points"):
                        record["points"] = self._safe_int(val)
                    elif "xg" == col_lower or "standard_xg" in col_lower:
                        record["xg_for"] = self._safe_float(val)
                    elif "xga" == col_lower or "standard_xga" in col_lower:
                        record["xg_against"] = self._safe_float(val)
                    elif "poss" in col_lower or "possession" in col_lower:
                        record["possession"] = self._safe_float(val)

                if record.get("team_name"):
                    results.append(record)

            if results:
                break  # 找到球队统计表后不再继续

        # 保存到 HDFS
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/fbref/team_stats/{league}_{season}_{ts}.json"
        try:
            self._save_raw_to_hdfs(results, hdfs_path)
        except Exception as e:
            logger.warning("HDFS 写入失败: %s", e)

        logger.info("[fbref] 球队统计采集完成: %d 条 (league=%s, season=%s)",
                     len(results), league, season)
        return results

    # ──────────────────────────────────────────────────────
    # 2. 积分榜
    # ──────────────────────────────────────────────────────

    def _crawl_standings(self, league: str, season: str, **kwargs) -> list[dict]:
        """采集积分榜

        从联赛主页解析 "Premier League Table" 表格。
        """
        url = self._league_url(league, season)
        try:
            resp = self._fetch(url)
        except Exception as e:
            logger.error("FBref 积分榜页请求失败: %s", e)
            return []

        results: list[dict] = []
        try:
            tables = pd.read_html(resp.text)
        except ValueError as e:
            logger.warning("FBref standings 表格解析失败: %s", e)
            return []

        for df in tables:
            df = self._flatten_columns(df)
            cols = [str(c).lower() for c in df.columns]

            # 识别积分榜表格（必须同时有 Rk + Squad + Pts）
            if "rk" not in cols and "rank" not in cols:
                continue
            if "pts" not in cols and "points" not in cols:
                continue

            for _, row in df.iterrows():
                record = {"source": "fbref", "league": league, "season": season}
                for col in df.columns:
                    col_lower = str(col).lower().strip()
                    val = row[col]

                    if col_lower in ("rk", "rank"):
                        record["position"] = self._safe_int(val)
                    elif col_lower in ("squad", "team"):
                        record["team_name"] = str(val)
                    elif col_lower == "mp":
                        record["played"] = self._safe_int(val)
                    elif col_lower == "w":
                        record["won"] = self._safe_int(val)
                    elif col_lower == "d":
                        record["drawn"] = self._safe_int(val)
                    elif col_lower == "l":
                        record["lost"] = self._safe_int(val)
                    elif col_lower == "gf":
                        record["goals_for"] = self._safe_int(val)
                    elif col_lower == "ga":
                        record["goals_against"] = self._safe_int(val)
                    elif col_lower == "gd":
                        record["goal_diff"] = self._safe_int(val)
                    elif col_lower in ("pts", "points"):
                        record["points"] = self._safe_int(val)
                    elif col_lower == "pts/mp":
                        record["pts_per_mp"] = self._safe_float(val)
                    elif "attendance" in col_lower:
                        record["attendance"] = self._safe_int(val)

                if record.get("team_name") and record.get("position"):
                    results.append(record)

            if results:
                break

        # 保存到 HDFS
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/fbref/standings/{league}_{season}_{ts}.json"
        try:
            self._save_raw_to_hdfs(results, hdfs_path)
        except Exception as e:
            logger.warning("HDFS 写入失败: %s", e)

        logger.info("[fbref] 积分榜采集完成: %d 条 (league=%s)", len(results), league)
        return results

    # ──────────────────────────────────────────────────────
    # 3. 球员统计
    # ──────────────────────────────────────────────────────

    def _crawl_player_stats(self, league: str, season: str, **kwargs) -> list[dict]:
        """采集球员统计数据

        从球员统计页解析 "Player Standard Stats" 表格。
        包含 goals/assists/xg/xa/minutes 等字段。
        """
        url = self._player_stats_url(league, season)
        try:
            resp = self._fetch(url)
        except Exception as e:
            logger.error("FBref 球员统计页请求失败: %s", e)
            return []

        results: list[dict] = []
        try:
            tables = pd.read_html(resp.text)
        except ValueError as e:
            logger.warning("FBref player_stats 表格解析失败: %s", e)
            return []

        for df in tables:
            df = self._flatten_columns(df)
            cols_lower = " ".join(str(c) for c in df.columns).lower()

            # 识别球员统计表（必须同时有 Player + 90s 或 Player + MP）
            if "player" not in cols_lower:
                continue

            for _, row in df.iterrows():
                record = {"source": "fbref", "league": league, "season": season}
                for col in df.columns:
                    col_lower = str(col).lower().strip()
                    val = row[col]

                    if col_lower == "player":
                        record["name"] = str(val)
                    elif col_lower in ("nation", "nationality"):
                        record["nationality"] = str(val)
                    elif col_lower in ("pos", "position"):
                        record["position"] = str(val)
                    elif col_lower in ("squad", "team"):
                        record["team_name"] = str(val)
                    elif col_lower == "age":
                        record["age"] = self._safe_int(val)
                    elif col_lower in ("born", "birth_year"):
                        record["birth_year"] = self._safe_int(val)
                    elif col_lower in ("mp", "playing time_mp"):
                        record["appearances"] = self._safe_int(val)
                    elif col_lower in ("playing time_min", "min"):
                        record["minutes_played"] = self._safe_int(val)
                    elif col_lower in ("90s", "playing time_90s"):
                        record["ninety_mins"] = self._safe_float(val)
                    elif col_lower in ("performance_gls", "gls"):
                        record["goals"] = self._safe_int(val)
                    elif col_lower in ("performance_ast", "ast"):
                        record["assists"] = self._safe_int(val)
                    elif col_lower in ("performance_g+a", "g+a"):
                        record["goals_plus_assists"] = self._safe_int(val)
                    elif col_lower in ("performance_g-pk", "g-pk"):
                        record["goals_non_penalty"] = self._safe_int(val)
                    elif col_lower in ("performance_pk", "pk"):
                        record["penalties_scored"] = self._safe_int(val)
                    elif col_lower in ("performance_pkatt", "pkatt"):
                        record["penalties_attempted"] = self._safe_int(val)
                    elif col_lower in ("performance_crdy", "crdy"):
                        record["yellow_cards"] = self._safe_int(val)
                    elif col_lower in ("performance_crdr", "crdr"):
                        record["red_cards"] = self._safe_int(val)
                    elif col_lower in ("expected_xg", "xg"):
                        record["xg"] = self._safe_float(val)
                    elif col_lower in ("expected_npxg", "npxg"):
                        record["npxg"] = self._safe_float(val)
                    elif col_lower in ("expected_xag", "xag"):
                        record["xa"] = self._safe_float(val)
                    elif col_lower in ("expected_npxg+xag", "npxg+xag"):
                        record["npxg_plus_xag"] = self._safe_float(val)
                    elif col_lower in ("progression_prgc", "prgc"):
                        record["progressive_carries"] = self._safe_int(val)
                    elif col_lower in ("progression_prgp", "prgp"):
                        record["progressive_passes"] = self._safe_int(val)
                    elif col_lower in ("progression_prgdist", "prgdist"):
                        record["progressive_distance"] = self._safe_float(val)

                # 只保留有球员名的记录
                if record.get("name") and record["name"] != "Player":
                    results.append(record)

            if results:
                break

        # 保存到 HDFS
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/fbref/player_stats/{league}_{season}_{ts}.json"
        try:
            self._save_raw_to_hdfs(results, hdfs_path)
        except Exception as e:
            logger.warning("HDFS 写入失败: %s", e)

        logger.info("[fbref] 球员统计采集完成: %d 条 (league=%s, season=%s)",
                     len(results), league, season)
        return results

    # ──────────────────────────────────────────────────────
    # 4. 比赛报告
    # ──────────────────────────────────────────────────────

    def _crawl_match_report(self, league: str, season: str, **kwargs) -> list[dict]:
        """采集比赛报告

        从 /matches/{match_id}/... 页面解析双方统计对比表。
        """
        match_id = kwargs.get("match_id")
        if not match_id:
            logger.warning("match_report 需要提供 match_id 参数")
            return []

        url = f"{self.base_url}matches/{match_id}/"
        try:
            resp = self._fetch(url)
        except Exception as e:
            logger.error("FBref 比赛报告页请求失败: %s", e)
            return []

        results: list[dict] = []
        try:
            tables = pd.read_html(resp.text)
        except ValueError as e:
            logger.warning("FBref match_report 表格解析失败: %s", e)
            return []

        # 比赛报告通常有一个 "Team Stats" 表格，对比双方数据
        for df in tables:
            df = self._flatten_columns(df)
            cols_lower = " ".join(str(c) for c in df.columns).lower()

            # 识别比赛统计对比表（通常包含 possession 或 shots）
            if "possession" not in cols_lower and "shots" not in cols_lower:
                continue

            record = {"match_id": match_id, "source": "fbref"}
            for col in df.columns:
                col_lower = str(col).lower().strip()
                val = df.iloc[0][col] if len(df) > 0 else None

                if col_lower == "possession":
                    record["possession"] = self._safe_float(val)
                elif col_lower in ("shots", "sh", "total shots"):
                    record["shots_total"] = self._safe_int(val)
                elif col_lower in ("shots on target", "sot", "st"):
                    record["shots_on_target"] = self._safe_int(val)
                elif col_lower in ("saves", "sv"):
                    record["saves"] = self._safe_int(val)
                elif col_lower in ("passes", "pass"):
                    record["passes"] = self._safe_int(val)
                elif col_lower in ("pass accuracy", "pass cmp%"):
                    record["pass_accuracy"] = self._safe_float(val)
                elif col_lower in ("corners", "ck"):
                    record["corners"] = self._safe_int(val)
                elif col_lower in ("fouls", "fl"):
                    record["fouls"] = self._safe_int(val)
                elif col_lower in ("xg", "expected goals"):
                    record["xg"] = self._safe_float(val)
                elif col_lower in ("xga", "expected goals against"):
                    record["xga"] = self._safe_float(val)

            if len(record) > 2:
                results.append(record)

        # 保存到 HDFS
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/fbref/match_report/{match_id}_{ts}.json"
        try:
            self._save_raw_to_hdfs(results, hdfs_path)
        except Exception as e:
            logger.warning("HDFS 写入失败: %s", e)

        logger.info("[fbref] 比赛报告采集完成: match_id=%s, %d 条统计",
                     match_id, len(results))
        return results
