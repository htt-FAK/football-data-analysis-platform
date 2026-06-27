"""TeamRankings 爬虫 — 采集球队排名与评分数据"""

import logging
from bs4 import BeautifulSoup

from app.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


class TeamRankingsCrawler(BaseCrawler):
    """TeamRankings 数据爬虫，主要采集排名与评分"""

    # 联赛 slug 映射
    LEAGUE_SLUG = {
        "epl": "soccer/england/premier-league",
        "laliga": "soccer/spain/laliga",
        "serie-a": "soccer/italy/serie-a",
        "bundesliga": "soccer/germany/bundesliga",
        "ligue-1": "soccer/france/ligue-1",
    }

    def __init__(self):
        super().__init__(source_code="teamrankings",
                         base_url="https://www.teamrankings.com/")

    def crawl(self, target: str = "rankings", league: str = "epl", **kwargs) -> list[dict]:
        """采集入口

        Args:
            target: 采集目标，支持 rankings / ratings
            league: 联赛简称（如 "epl" 表示英超）
        """
        if target == "rankings":
            return self._crawl_rankings(league, **kwargs)
        elif target == "ratings":
            return self._crawl_ratings(league, **kwargs)
        else:
            logger.warning("不支持的目标: %s", target)
            return []

    def _league_url(self, league: str) -> str:
        """构造联赛主页 URL"""
        slug = self.LEAGUE_SLUG.get(league, f"soccer/{league}")
        return f"{self.base_url}{slug}"

    def _crawl_rankings(self, league: str, **kwargs) -> list[dict]:
        """采集球队排名"""
        url = f"{self._league_url(league)}/rankings/"
        resp = self._fetch(url)
        soup = BeautifulSoup(resp.text, "lxml")
        results: list[dict] = []
        # TODO: 解析排名表格，提取排名、队名、胜率、近期表现等字段
        return results

    def _crawl_ratings(self, league: str, **kwargs) -> list[dict]:
        """采集球队评分（power ratings）"""
        url = f"{self._league_url(league)}/power-ratings/"
        resp = self._fetch(url)
        soup = BeautifulSoup(resp.text, "lxml")
        results: list[dict] = []
        # TODO: 解析评分表格，提取队名、评分、攻防数据等字段
        return results
