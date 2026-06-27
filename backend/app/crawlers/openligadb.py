"""OpenLigaDB 爬虫 — 采集比赛与球队信息（免费 REST API）"""

import logging

from app.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


class OpenLigaDBCrawler(BaseCrawler):
    """OpenLigaDB 数据爬虫

    OpenLigaDB 提供免费的德国足球赛事数据 REST API。
    """

    def __init__(self):
        super().__init__(source_code="openligadb",
                         base_url="https://api.openligadb.de/")

    def crawl(self, target: str, league: str = "bl1",
              season: str = "2025", **kwargs) -> list[dict]:
        """采集入口

        Args:
            target: 采集目标，支持 matches / teams
            league: 联赛简称（如 "bl1" 表示德甲）
            season: 赛季（如 "2025" 表示 2025-2026 赛季）
        """
        if target == "matches":
            return self._crawl_matches(league, season, **kwargs)
        elif target == "teams":
            return self._crawl_teams(league, season, **kwargs)
        else:
            logger.warning("不支持的目标: %s", target)
            return []

    def _crawl_matches(self, league: str, season: str, **kwargs) -> list[dict]:
        """采集赛季内所有比赛"""
        url = f"{self.base_url}getmatchdata/{league}/{season}"
        resp = self._fetch(url)
        results: list[dict] = []
        try:
            payload = resp.json()
            results = payload if isinstance(payload, list) else []
            # TODO: 解析比赛结果、比赛日期、队伍信息等字段
        except ValueError as e:
            logger.error("[%s] matches JSON 解析失败: %s", self.source_code, e)
        return results

    def _crawl_teams(self, league: str, season: str, **kwargs) -> list[dict]:
        """采集联赛球队列表"""
        url = f"{self.base_url}getavailableteams/{league}/{season}"
        resp = self._fetch(url)
        results: list[dict] = []
        try:
            payload = resp.json()
            results = payload if isinstance(payload, list) else []
            # TODO: 解析球队 ID、名称、图标等字段
        except ValueError as e:
            logger.error("[%s] teams JSON 解析失败: %s", self.source_code, e)
        return results
