"""API-Football v3 爬虫 — 采集赛程、积分榜、球员数据"""

import logging

from app.crawlers.base import BaseCrawler
from app.config import API_FOOTBALL_KEY, API_FOOTBALL_BASE

logger = logging.getLogger(__name__)


class APIFootballCrawler(BaseCrawler):
    """API-Football v3 接口爬虫

    需要在 .env 中配置 API_FOOTBALL_KEY。
    """

    # 端点路径映射
    ENDPOINTS = {
        "fixtures": "/fixtures",
        "standings": "/standings",
        "players": "/players",
    }

    def __init__(self):
        super().__init__(source_code="api_football", base_url=API_FOOTBALL_BASE)
        # API-Football 要求通过特定请求头传递 key
        self.session.headers.update({
            "x-apisports-key": API_FOOTBALL_KEY,
            "x-rapidapi-host": "v3.football.api-sports.io",
        })

    def crawl(self, target: str, league_id: int = 39,
              season: int = 2025, **kwargs) -> list[dict]:
        """采集入口

        Args:
            target: 采集目标，支持 fixtures / standings / players
            league_id: 联赛 ID（如 39 表示英超）
            season: 赛季起始年份（如 2025 表示 2025-2026 赛季）
        """
        if not API_FOOTBALL_KEY:
            logger.error("未配置 API_FOOTBALL_KEY，无法调用 API-Football")
            return []

        endpoint = self.ENDPOINTS.get(target)
        if not endpoint:
            logger.warning("不支持的目标: %s", target)
            return []

        params = {"league": league_id, "season": season}
        params.update(kwargs)
        return self._request(endpoint, params)

    def _request(self, endpoint: str, params: dict) -> list[dict]:
        """调用 API-Football 接口并返回响应中的数据列表"""
        url = f"{self.base_url}{endpoint}"
        resp = self._fetch(url, params=params)
        results: list[dict] = []
        try:
            payload = resp.json()
            # API-Football 返回结构：{"get": ..., "response": [...], ...}
            results = payload.get("response", [])
            # TODO: 对返回数据做字段标准化与清洗
        except ValueError as e:
            logger.error("[%s] JSON 解析失败: %s", self.source_code, e)
        return results
