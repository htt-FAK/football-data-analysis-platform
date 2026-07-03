"""Fotmob 爬虫 — 抓取世界杯单场 xG（基于 undetected-chromedriver + API）

实现要点（已对照真实结构验证）：
1. UC 浏览器访问主页拿 cookie（绕过 Cloudflare），后续用浏览器内 fetch 调 API
2. 联赛页 __NEXT_DATA__ 提取比赛列表（数字 matchId + 队名 + 日期 + status.finished）
3. 对已结束比赛，调用 ``/api/data/matchDetails?matchId={数字id}`` 拿 JSON
4. xG 路径：``content.stats.Periods.All.stats`` → 找 title=="Expected goals (xG)" 的组
   → 组内 stats 数组里找 ``key=="expected_goals"`` 且 ``type=="text"`` 的项
   → 该项 stats=[主队值, 客队值]

输出标准字段（供 ingest_match_xg 消费）：
    home_team, away_team, date(ISO), home_xg, away_xg, source_match_id

注意：Fotmob 提供的是单场汇总 xG（主 X.XX / 客 Y.YY），不是逐脚射门，
因此只能点亮"主队/客队 xG"卡片，无法生成逐脚 xG 时间线。
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

from app.crawlers.base import BaseCrawler
from app.crawlers.fbref import _patch_uc_auto  # 复用 fbref 的 UC patch

logger = logging.getLogger(__name__)


WORLD_CUP_LEAGUE_ID = 77
DEFAULT_LOOKBACK_DAYS = 14
DEFAULT_MATCH_CAP = 40


class FotmobCrawler(BaseCrawler):
    """Fotmob 数据爬虫，使用 undetected-chromedriver 调内部 API"""

    def __init__(self):
        super().__init__(source_code="fotmob", base_url="https://www.fotmob.com/")
        self._driver = None

    # ──────────────────────────────────────────────────────
    # UC 浏览器管理
    # ──────────────────────────────────────────────────────

    def _get_driver(self):
        if self._driver is not None and self._is_alive(self._driver):
            return self._driver
        # 上一个会话挂了，重建
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:  # noqa: BLE001
                pass
            self._driver = None

        try:
            import undetected_chromedriver as uc
        except ImportError as e:
            raise RuntimeError(
                "缺少 undetected-chromedriver，请执行: pip install undetected-chromedriver"
            ) from e

        _patch_uc_auto(uc)

        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-popup-blocking")

        user_data_dir = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "fotmob_uc_profile",
        )
        os.makedirs(user_data_dir, exist_ok=True)

        self._driver = uc.Chrome(options=options, user_data_dir=user_data_dir)
        # 先访问主页拿 cookie，过 Cloudflare
        self._driver.get(self.base_url)
        self._wait_for_render(self._driver, 15)
        return self._driver

    @staticmethod
    def _is_alive(driver) -> bool:
        try:
            _ = driver.current_url  # noqa: F841
            return True
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _wait_for_render(driver, seconds: int = 15):
        """等待页面渲染（非 Cloudflare 挑战页时即可）"""
        for _ in range(seconds):
            title = (driver.title or "").lower()
            if "just a moment" not in title and "请稍候" not in title:
                time.sleep(1)
                return True
            time.sleep(1)
        return False

    def close(self):
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:  # noqa: BLE001
                pass
            self._driver = None

    def __del__(self):
        self.close()

    # ──────────────────────────────────────────────────────
    # 浏览器内 fetch（绕过 x-fm-req）
    # ──────────────────────────────────────────────────────

    def _fetch_json_via_browser(self, url: str, timeout: int = 30) -> dict | None:
        """用浏览器内 fetch 调 API，返回 JSON dict。失败返回 None。

        浏览器原生带 x-fm-req header，能拿到纯 requests 被挡的 API。
        """
        driver = self._get_driver()
        try:
            result = driver.execute_async_script(
                """
                const uri = arguments[0];
                const timeoutMs = arguments[1];
                const done = arguments[arguments.length - 1];
                const ctrl = new AbortController();
                const t = setTimeout(() => ctrl.abort(), timeoutMs);
                fetch(uri, {credentials: 'include', signal: ctrl.signal})
                    .then(r => r.json())
                    .then(j => { clearTimeout(t); done({ok: true, data: j}); })
                    .catch(e => { clearTimeout(t); done({ok: false, err: String(e)}); });
                """,
                url,
                timeout * 1000,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("[fotmob] 浏览器 fetch 执行异常: %s | url=%s", e, url)
            return None

        if not result or not result.get("ok"):
            logger.warning("[fotmob] API fetch 失败: %s | url=%s", result, url)
            return None
        return result.get("data")

    # ──────────────────────────────────────────────────────
    # 采集入口
    # ──────────────────────────────────────────────────────

    def crawl(
        self,
        target: str = "match_xg",
        league_id: int = WORLD_CUP_LEAGUE_ID,
        season: str | None = None,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        match_cap: int = DEFAULT_MATCH_CAP,
        **kwargs,
    ) -> list[dict]:
        if target != "match_xg":
            logger.warning("[fotmob] 不支持的目标: %s", target)
            return []
        try:
            return self._crawl_match_xg(
                league_id=league_id,
                season=season,
                lookback_days=lookback_days,
                match_cap=match_cap,
            )
        finally:
            self.close()

    def _crawl_match_xg(
        self,
        league_id: int,
        season: str | None,
        lookback_days: int,
        match_cap: int,
    ) -> list[dict]:
        results: list[dict] = []

        # 1. 联赛页 → 比赛列表
        league_url = f"{self.base_url}leagues/{league_id}"
        driver = self._get_driver()
        driver.get(league_url)
        self._wait_for_render(driver, 15)
        html = driver.page_source
        matches = self._extract_recent_finished_matches(html, lookback_days)
        logger.info(
            "[fotmob] 联赛页解析到 %d 场近期已结束比赛 (league_id=%s)",
            len(matches), league_id,
        )

        if not matches:
            return results

        # 2. 逐场调 matchDetails API 提取 xG
        for entry in matches[:match_cap]:
            self._delay()
            match_id = str(entry.get("source_match_id") or "")
            if not match_id:
                continue
            api_url = f"{self.base_url}api/data/matchDetails?matchId={match_id}"
            data = self._fetch_json_via_browser(api_url, timeout=30)
            if not data:
                logger.info("[fotmob] 比赛 %s 未拿到 API 数据，跳过", match_id)
                continue
            xg = self._extract_xg_from_match_details(data)
            if xg is None:
                logger.info("[fotmob] 比赛 %s 未解析到 xG（可能尚未生成）", match_id)
                continue
            record = {
                "source": "fotmob",
                "league": "World Cup",
                "season": season,
                "home_team": entry.get("home_team"),
                "away_team": entry.get("away_team"),
                "date": entry.get("date"),
                "home_xg": xg.get("home_xg"),
                "away_xg": xg.get("away_xg"),
                "source_match_id": match_id,
            }
            if record["home_team"] and record["away_team"] and (
                record["home_xg"] is not None or record["away_xg"] is not None
            ):
                results.append(record)

        # 3. HDFS 落盘
        if results:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            hdfs_path = f"/sports/raw/fotmob/match_xg/{league_id}_{ts}.json"
            try:
                self._save_raw_to_hdfs(results, hdfs_path)
            except Exception as e:  # noqa: BLE001
                logger.warning("[fotmob] HDFS 写入失败: %s", e)

        logger.info("[fotmob] 单场 xG 采集完成: %d 条", len(results))
        return results

    # ──────────────────────────────────────────────────────
    # 联赛页比赛列表解析
    # ──────────────────────────────────────────────────────

    _NEXT_DATA_RE = re.compile(
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
    )

    @classmethod
    def _extract_next_data(cls, html: str) -> dict | None:
        match = cls._NEXT_DATA_RE.search(html or "")
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except (ValueError, TypeError) as e:
            logger.warning("[fotmob] __NEXT_DATA__ JSON 解析失败: %s", e)
            return None

    def _extract_recent_finished_matches(
        self, html: str, lookback_days: int
    ) -> list[dict]:
        """从联赛页 HTML 提取近期已结束比赛（真实结构：id/home/away/status.finished）"""
        next_data = self._extract_next_data(html)
        if not next_data:
            return []

        cutoff = datetime.now(timezone.utc).timestamp() - lookback_days * 86400
        collected: list[dict] = []
        seen: set[str] = set()

        def _walk(node: Any):
            if isinstance(node, dict):
                if self._looks_like_match(node):
                    m = self._match_from_node(node)
                    if m:
                        mid = str(m.get("source_match_id") or "")
                        ts = m.get("_ts") or 0
                        if (
                            mid and mid not in seen
                            and m.get("_finished")
                            and ts >= cutoff
                        ):
                            collected.append(m)
                            seen.add(mid)
                for v in node.values():
                    _walk(v)
            elif isinstance(node, list):
                for v in node:
                    _walk(v)

        _walk(next_data)
        collected.sort(key=lambda m: m.get("_ts") or 0, reverse=True)
        return collected

    @staticmethod
    def _looks_like_match(node: dict) -> bool:
        """判断是否像比赛节点：有 id + home.name + away.name + status"""
        return (
            isinstance(node.get("id"), (str, int))
            and isinstance(node.get("home"), dict)
            and isinstance(node.get("away"), dict)
            and bool(node["home"].get("name"))
            and bool(node["away"].get("name"))
            and isinstance(node.get("status"), dict)
        )

    @staticmethod
    def _match_from_node(node: dict) -> dict | None:
        mid = node.get("id")
        home = node.get("home") or {}
        away = node.get("away") or {}
        status = node.get("status") or {}

        # 时间
        ts = None
        utc = status.get("utcTime")
        if isinstance(utc, str):
            try:
                ts = datetime.fromisoformat(utc.replace("Z", "+00:00")).timestamp()
            except ValueError:
                ts = None
        date_iso = (
            datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            if ts else None
        )

        # finished 判定：优先用 status.finished 布尔；没有则看 reason
        finished = bool(status.get("finished"))
        if not finished:
            reason = status.get("reason") or {}
            if isinstance(reason, dict):
                long_key = str(reason.get("longKey") or "").lower()
                short = str(reason.get("short") or "").lower()
                finished = long_key == "finished" or short in {"ft", "aet", "ap"}

        return {
            "source_match_id": str(mid),
            "home_team": home.get("name"),
            "away_team": away.get("name"),
            "date": date_iso,
            "_finished": finished,
            "_ts": ts,
        }

    # ──────────────────────────────────────────────────────
    # matchDetails API 的 xG 提取（已对照真实结构）
    # ──────────────────────────────────────────────────────

    def _extract_xg_from_match_details(self, data: dict) -> dict | None:
        """从 matchDetails JSON 提取 {home_xg, away_xg}

        真实路径（已诊断确认）：
            content.stats.Periods.All.stats  →  list[group]
            group.title == "Expected goals (xG)"
            group.stats  →  list[item]
            item.key == "expected_goals" and item.type == "text"
            item.stats == ["1.46", "0.07"]   # [主队, 客队]
        （跳过 type=="title" 的占位项，其 stats 为 [null, null]）
        """
        try:
            groups = (
                data["content"]["stats"]["Periods"]["All"]["stats"]
            )
        except (KeyError, TypeError):
            logger.warning("[fotmob] xG 路径缺失: content.stats.Periods.All.stats")
            return None

        for group in groups:
            if not isinstance(group, dict):
                continue
            title = str(group.get("title") or "").lower()
            if "expected goals" not in title and title != "xg":
                continue
            items = group.get("stats")
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                # 只取真实的 text 项，跳过 title 占位
                if item.get("key") != "expected_goals":
                    continue
                if item.get("type") not in ("text", None):
                    # type=="title" 是占位，跳过；但要容忍没有 type 字段的情况
                    if item.get("type") == "title":
                        continue
                vals = item.get("stats")
                pair = self._parse_xg_pair(vals)
                if pair:
                    return pair
        return None

    @staticmethod
    def _parse_xg_pair(stats: Any) -> dict | None:
        """把 ['1.46', '0.07'] 解析成 {home_xg, away_xg}"""
        if not isinstance(stats, list) or len(stats) < 2:
            return None
        nums = []
        for s in stats[:2]:
            if s is None or s == "":
                nums.append(None)
                continue
            try:
                nums.append(float(s))
            except (TypeError, ValueError):
                nums.append(None)
        if all(n is None for n in nums):
            return None
        return {"home_xg": nums[0], "away_xg": nums[1]}
