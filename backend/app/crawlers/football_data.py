"""Football-Data.co.uk 数据导入器 — 下载并解析 CSV 赛事数据"""

import io
import logging
import pandas as pd

from app.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


class FootballDataImporter(BaseCrawler):
    """football-data.co.uk CSV 数据导入

    提供历年联赛比赛结果的 CSV 下载与解析。
    """

    # 联赛代码映射（football-data.co.uk 约定的 league code）
    LEAGUE_CODE = {
        "E0": "EPL",      # 英超
        "E1": "EFL Championship",
        "SP1": "La Liga",
        "I1": "Serie A",
        "D1": "Bundesliga",
        "F1": "Ligue 1",
    }

    def __init__(self):
        super().__init__(source_code="football_data",
                         base_url="https://www.football-data.co.uk/")

    def crawl(self, target: str = "matches", league: str = "E0",
              season: str = "2526", **kwargs) -> list[dict]:
        """采集入口

        Args:
            target: 采集目标，仅支持 "matches"（下载 CSV）
            league: 联赛代码（如 "E0" 表示英超）
            season: 赛季（如 "2526" 表示 2025-2026 赛季）
        """
        if target == "matches":
            return self._download_matches(league, season, **kwargs)
        else:
            logger.warning("不支持的目标: %s", target)
            return []

    def _download_matches(self, league: str, season: str, **kwargs) -> list[dict]:
        """下载并解析 CSV 赛事数据"""
        # 拼接 CSV 文件 URL，例如 mmz2526/E0.csv
        url = f"{self.base_url}mmz{season}/{league}.csv"
        resp = self._fetch(url)
        results: list[dict] = []
        try:
            # 用 pandas 直接从响应内容读取 CSV
            df = pd.read_csv(io.StringIO(resp.text))
            # TODO: 字段标准化与清洗（日期格式、空值处理、列名统一）
            results = df.to_dict(orient="records")
        except Exception as e:
            logger.error("[%s] CSV 解析失败: %s", self.source_code, e)
        return results
