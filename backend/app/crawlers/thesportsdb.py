"""TheSportsDB 爬虫 — 采集赛事、球队、球员信息（免费公共 API）"""

import logging

from app.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


class TheSportsDBCrawler(BaseCrawler):
    """TheSportsDB 公共 API 爬虫

    免费版 API key 固定为 "3"，无需注册。
    """

    def __init__(self):
        super().__init__(source_code="thesportsdb",
                         base_url="https://www.thesportsdb.com/api/v1/json/3/")

    def crawl(self, target: str, league_id: str = "4328",
              season: str = "2025-2026", **kwargs) -> list[dict]:
        """采集入口

        Args:
            target: 采集目标，支持 events / teams / players
            league_id: 联赛 ID（如 "4328" 表示英超）
            season: 赛季（如 "2025-2026"）
        """
        if target == "events":
            return self._crawl_events(league_id, season, **kwargs)
        elif target == "teams":
            return self._crawl_teams(league_id, **kwargs)
        elif target == "players":
            return self._crawl_players(league_id, **kwargs)
        else:
            logger.warning("不支持的目标: %s", target)
            return []

    def _crawl_events(self, league_id: str, season: str, **kwargs) -> list[dict]:
        """采集赛季内所有赛事"""
        url = f"{self.base_url}eventsseason.php?id={league_id}&s={season}"
        resp = self._fetch(url)
        results: list[dict] = []
        try:
            payload = resp.json()
            results = payload.get("events", []) or []
            # TODO: 字段标准化与清洗
        except ValueError as e:
            logger.error("[%s] events JSON 解析失败: %s", self.source_code, e)
        return results

    def _crawl_teams(self, league_id: str, **kwargs) -> list[dict]:
        """采集联赛下所有球队"""
        url = f"{self.base_url}lookup_all_teams.php?id={league_id}"
        resp = self._fetch(url)
        results: list[dict] = []
        try:
            payload = resp.json()
            results = payload.get("teams", []) or []
            # TODO: 字段标准化与清洗
        except ValueError as e:
            logger.error("[%s] teams JSON 解析失败: %s", self.source_code, e)
        return results

    def _crawl_players(self, league_id: str, **kwargs) -> list[dict]:
        """采集球员信息"""
        team_id = kwargs.get("team_id")
        if not team_id:
            logger.warning("players 需要提供 team_id 参数")
            return []
        url = f"{self.base_url}lookup_all_players.php?id={team_id}"
        resp = self._fetch(url)
        results: list[dict] = []
        try:
            payload = resp.json()
            results = payload.get("player", []) or []
            # TODO: 字段标准化与清洗
        except ValueError as e:
            logger.error("[%s] players JSON 解析失败: %s", self.source_code, e)
        return results
