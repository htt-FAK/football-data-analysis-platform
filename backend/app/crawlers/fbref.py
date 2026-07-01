"""FBref 爬虫 — 使用 undetected-chromedriver 绕过 Cloudflare

FBref 启用了 Cloudflare JS challenge，requests / cloudscraper / Playwright(headless/有头/stealth)
均被拦截（识别 CDP 指纹）。本爬虫采用 undetected-chromedriver（修补 CDP 指纹的真实 Chrome）绕过。

页面结构：
- /comps/{id}/{season}/{season}-{league}-Stats        联赛主页（含积分榜 + 球队统计）
- /comps/{id}/{season}/players/{season}-{league}-Stats 球员统计页

返回字段直接使用标准字段名（goals/assists/xg/...），
ingest_player_stats / ingest_team_stats 对 source=fbref 跳过 map_fields。
"""

import logging
import os
import time
from datetime import datetime
from typing import Optional

import pandas as pd

from app.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────
# UC Patcher monkey-patch（跳过网络下载）
# ──────────────────────────────────────────────────────

_UC_PATCHED = False


def _patch_uc_auto(uc_module):
    """Monkey-patch Patcher.auto() 跳过网络下载，直接用本地 chromedriver

    UC 3.5.5 的 auto() 默认会调用 fetch_release_number() 去访问
    googlechromelabs.github.io，国内网络不稳定。
    改为：检测 chromedriver 是否已存在，存在则直接 patch() 修补 CDP 指纹。
    幂等：多次调用只 patch 一次。
    """
    global _UC_PATCHED
    if _UC_PATCHED:
        return

    from undetected_chromedriver.patcher import Patcher

    def _patched_auto(self, force=None):
        if not os.path.exists(self.executable_path):
            raise FileNotFoundError(
                f"chromedriver 不存在: {self.executable_path}，"
                "请先运行 backend/_install_chromedriver.py 下载"
            )
        try:
            if self.is_binary_patched():
                return True
        except PermissionError:
            # 文件被占用（其他 Chrome 实例在用），假设已 patched
            return True
        return self.patch()

    Patcher.auto = _patched_auto
    _UC_PATCHED = True
    logger.info("[fbref] 已 monkey-patch Patcher.auto() 跳过网络下载")


class FBrefCrawler(BaseCrawler):
    """FBref 数据爬虫，使用 undetected-chromedriver 绕过 Cloudflare"""

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
        self._driver = None  # 延迟初始化 UC 浏览器

    # ──────────────────────────────────────────────────────
    # UC 浏览器管理
    # ──────────────────────────────────────────────────────

    def _get_driver(self):
        """延迟初始化 undetected-chromedriver（首次调用时启动浏览器）"""
        if self._driver is not None:
            return self._driver
        try:
            import undetected_chromedriver as uc
        except ImportError as e:
            raise RuntimeError(
                "缺少 undetected-chromedriver，请执行: pip install undetected-chromedriver"
            ) from e

        # ─── monkey-patch Patcher.auto() 跳过网络下载 ───
        # UC 3.5.5 的 auto() 会去 googlechromelabs.github.io 拉版本信息，
        # 国内网络不稳定。改为：假设 chromedriver 已手动下载到 UC 期望位置，
        # 直接调用 patch() 修补 CDP 指纹，跳过 fetch_release_number。
        _patch_uc_auto(uc)

        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-popup-blocking")
        # 注意：headless 会被 Cloudflare 识别，必须使用有头模式

        # 固定 user_data_dir 让 Cloudflare cf_clearance cookie 持久化
        # 第一次访问过 challenge 后，后续访问带着 cookie 更容易过
        user_data_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                                     "fbref_uc_profile")
        os.makedirs(user_data_dir, exist_ok=True)

        self._driver = uc.Chrome(
            options=options,
            user_data_dir=user_data_dir,
            version_main=137,
        )
        return self._driver

    def _fetch_html(self, url: str, wait_seconds: int = 30,
                    max_retries: int = 3) -> str:
        """用 UC 浏览器访问 URL，返回完整 HTML 文本

        Cloudflare challenge 检测策略：
        - 访问后每秒检测 title，若不是"请稍候…"/"Just a moment"则通过
        - 未通过则刷新重试，最多 max_retries 次
        - 全部失败则返回最后的页面（让上层解析失败时报错）

        Args:
            url: 目标 URL
            wait_seconds: 单次尝试最长等待秒数
            max_retries: 最大重试次数
        """
        driver = self._get_driver()
        for attempt in range(1, max_retries + 1):
            logger.info("[fbref] UC 访问 %s (尝试 %d/%d)", url, attempt, max_retries)
            if attempt == 1:
                driver.get(url)
            else:
                driver.refresh()  # 重试时刷新，触发新的 challenge
            # 每秒检测 title 是否还是 Cloudflare challenge 页
            for sec in range(wait_seconds):
                title = driver.title or ""
                if "请稍候" not in title and "Just a moment" not in title:
                    logger.info("[fbref] Cloudflare 已通过 (等待 %ds, title=%s)", sec, title)
                    # 再等 2 秒让 JS 渲染表格
                    time.sleep(2)
                    return driver.page_source
                time.sleep(1)
            logger.warning("[fbref] 第 %d 次未通过 Cloudflare (title=%s)",
                           attempt, driver.title)
        logger.error("[fbref] Cloudflare 全部 %d 次重试失败", max_retries)
        return driver.page_source

    def close(self):
        """关闭 UC 浏览器，释放资源"""
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    def __del__(self):
        self.close()

    # ──────────────────────────────────────────────────────
    # 采集入口
    # ──────────────────────────────────────────────────────

    def crawl(self, target: str, league: str = "Premier League",
              season: str = "2024-2025", **kwargs) -> list[dict]:
        """采集入口

        Args:
            target: 采集目标，支持 team_stats / standings / player_stats
            league: 联赛名称（如 "Premier League"）
            season: 赛季（如 "2024-2025"）
        """
        dispatch = {
            "team_stats": self._crawl_team_stats,
            "standings": self._crawl_standings,
            "player_stats": self._crawl_player_stats,
        }
        handler = dispatch.get(target)
        if not handler:
            logger.warning("[fbref] 不支持的目标: %s", target)
            return []
        try:
            return handler(league, season, **kwargs)
        finally:
            self.close()  # 每次采集完关闭浏览器，避免长期占用

    # ──────────────────────────────────────────────────────
    # URL 构造
    # ──────────────────────────────────────────────────────

    def _league_url(self, league: str, season: str) -> str:
        """联赛主页 URL（含积分榜 + 球队统计）"""
        league_id = self.LEAGUE_ID.get(league, "9")
        league_slug = league.replace(" ", "-")
        return f"{self.base_url}comps/{league_id}/{season}/{season}-{league_slug}-Stats"

    def _player_stats_url(self, league: str, season: str) -> str:
        """球员统计页 URL"""
        league_id = self.LEAGUE_ID.get(league, "9")
        league_slug = league.replace(" ", "-")
        return f"{self.base_url}comps/{league_id}/{season}/players/{season}-{league_slug}-Stats"

    # ──────────────────────────────────────────────────────
    # 工具方法
    # ──────────────────────────────────────────────────────

    @staticmethod
    def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
        """将多级列名展平为单级，如 ('Performance', 'Gls') → 'Performance_Gls'"""
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [
                "_".join(str(c) for c in col if c and str(c) != "nan")
                for col in df.columns.values
            ]
        return df

    @staticmethod
    def _safe_int(val) -> Optional[int]:
        try:
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            return int(float(val))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_float(val) -> Optional[float]:
        try:
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            return float(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _find_table(tables: list[pd.DataFrame], required_cols: list[str]) -> Optional[pd.DataFrame]:
        """从 read_html 结果中找到第一个包含所有必需列（不区分大小写）的表"""
        for df in tables:
            df = FBrefCrawler._flatten_columns(df)
            cols_lower = {str(c).lower().strip() for c in df.columns}
            if all(any(rc in c for c in cols_lower) for rc in required_cols):
                return df
        return None

    # ──────────────────────────────────────────────────────
    # 1. 球员统计
    # ──────────────────────────────────────────────────────

    def _crawl_player_stats(self, league: str, season: str, **kwargs) -> list[dict]:
        """采集球员标准统计表（stats_standard）

        返回字段（直接使用标准字段名）：
            name, team, position, age, birth_year, nationality,
            appearances, minutes_played, ninety_mins,
            goals, assists, goals_plus_assists, goals_non_penalty,
            penalties_scored, penalties_attempted, yellow_cards, red_cards,
            xg, npxg, xa, npxg_plus_xag,
            progressive_carries, progressive_passes, progressive_passes_received
        """
        url = self._player_stats_url(league, season)
        try:
            html = self._fetch_html(url)
        except Exception as e:
            logger.error("[fbref] 球员统计页请求失败: %s", e)
            return []

        try:
            tables = pd.read_html(html, flavor="html5lib")
        except ValueError as e:
            logger.warning("[fbref] player_stats 表格解析失败: %s", e)
            return []

        # 球员标准统计表的特征：含 player + 90s + xg
        df = self._find_table(tables, ["player", "90s"])
        if df is None:
            logger.warning("[fbref] 未找到球员统计表")
            return []

        results: list[dict] = []
        for _, row in df.iterrows():
            record = {"source": "fbref", "league": league, "season": season}
            for col in df.columns:
                col_lower = str(col).lower().strip()
                val = row[col]

                if col_lower == "player":
                    record["name"] = str(val)
                elif col_lower in ("nation", "nationality"):
                    # FBref Nation 字段格式如 "eng ENG"，取后部分代码
                    nation = str(val).strip()
                    record["nationality"] = nation.split()[-1] if nation else None
                elif col_lower in ("pos", "position"):
                    record["position"] = str(val)
                elif col_lower == "squad":
                    record["team"] = str(val)
                elif col_lower == "age":
                    record["age"] = self._safe_int(val)
                elif col_lower == "born":
                    record["birth_year"] = self._safe_int(val)
                elif col_lower in ("playing time_mp", "mp"):
                    record["appearances"] = self._safe_int(val)
                elif col_lower in ("playing time_min", "min"):
                    record["minutes_played"] = self._safe_int(val)
                elif col_lower in ("playing time_90s", "90s"):
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
                elif col_lower in ("progression_prgr", "prgr"):
                    record["progressive_passes_received"] = self._safe_int(val)

            # 过滤掉 "Player" 表头行（FBref 表格中间会重复出现表头）
            if record.get("name") and record["name"] != "Player":
                results.append(record)

        # 保存到 HDFS
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/fbref/player_stats/{league}_{season}_{ts}.json"
        try:
            self._save_raw_to_hdfs(results, hdfs_path)
        except Exception as e:
            logger.warning("[fbref] HDFS 写入失败: %s", e)

        logger.info("[fbref] 球员统计采集完成: %d 条 (league=%s, season=%s)",
                    len(results), league, season)
        return results

    # ──────────────────────────────────────────────────────
    # 2. 球队统计
    # ──────────────────────────────────────────────────────

    def _crawl_team_stats(self, league: str, season: str, **kwargs) -> list[dict]:
        """采集球队标准统计表（Squad Standard Stats）

        返回字段（标准字段名）：
            team, position, played, won, drawn, lost,
            goals_for, goals_against, goal_diff, points,
            xg_for, xg_against, possession
        """
        url = self._league_url(league, season)
        try:
            html = self._fetch_html(url)
        except Exception as e:
            logger.error("[fbref] 球队统计页请求失败: %s", e)
            return []

        try:
            tables = pd.read_html(html, flavor="html5lib")
        except ValueError as e:
            logger.warning("[fbref] team_stats 表格解析失败: %s", e)
            return []

        # 球队统计表特征：squad + mp + xg
        df = self._find_table(tables, ["squad", "mp", "xg"])
        if df is None:
            logger.warning("[fbref] 未找到球队统计表")
            return []

        results: list[dict] = []
        for _, row in df.iterrows():
            record = {"source": "fbref", "league": league, "season": season}
            for col in df.columns:
                col_lower = str(col).lower().strip()
                val = row[col]

                if col_lower in ("squad", "team"):
                    record["team"] = str(val)
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
                elif col_lower in ("xg", "standard_xg"):
                    record["xg_for"] = self._safe_float(val)
                elif col_lower in ("xga", "standard_xga"):
                    record["xg_against"] = self._safe_float(val)
                elif col_lower in ("poss", "possession"):
                    record["possession"] = self._safe_float(val)

            if record.get("team") and record["team"] != "Squad":
                results.append(record)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/fbref/team_stats/{league}_{season}_{ts}.json"
        try:
            self._save_raw_to_hdfs(results, hdfs_path)
        except Exception as e:
            logger.warning("[fbref] HDFS 写入失败: %s", e)

        logger.info("[fbref] 球队统计采集完成: %d 条", len(results))
        return results

    # ──────────────────────────────────────────────────────
    # 3. 积分榜
    # ──────────────────────────────────────────────────────

    def _crawl_standings(self, league: str, season: str, **kwargs) -> list[dict]:
        """采集积分榜表（Premier League Table）

        返回字段（标准字段名）：
            position, team, played, won, drawn, lost,
            goals_for, goals_against, goal_diff, points
        """
        url = self._league_url(league, season)
        try:
            html = self._fetch_html(url)
        except Exception as e:
            logger.error("[fbref] 积分榜页请求失败: %s", e)
            return []

        try:
            tables = pd.read_html(html, flavor="html5lib")
        except ValueError as e:
            logger.warning("[fbref] standings 表格解析失败: %s", e)
            return []

        # 积分榜表特征：rk + squad + pts
        df = None
        for t in tables:
            t = self._flatten_columns(t)
            cols = {str(c).lower().strip() for c in t.columns}
            if "rk" in cols and "pts" in cols and "squad" in cols:
                df = t
                break
        if df is None:
            logger.warning("[fbref] 未找到积分榜表")
            return []

        results: list[dict] = []
        for _, row in df.iterrows():
            record = {"source": "fbref", "league": league, "season": season}
            for col in df.columns:
                col_lower = str(col).lower().strip()
                val = row[col]

                if col_lower == "rk":
                    record["position"] = self._safe_int(val)
                elif col_lower == "squad":
                    record["team"] = str(val)
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
                elif col_lower == "pts":
                    record["points"] = self._safe_int(val)

            if record.get("team") and record.get("position"):
                results.append(record)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        hdfs_path = f"/sports/raw/fbref/standings/{league}_{season}_{ts}.json"
        try:
            self._save_raw_to_hdfs(results, hdfs_path)
        except Exception as e:
            logger.warning("[fbref] HDFS 写入失败: %s", e)

        logger.info("[fbref] 积分榜采集完成: %d 条", len(results))
        return results
