"""TeamRankings crawler for auxiliary rankings and probability data."""

from __future__ import annotations

import logging
from io import StringIO

from bs4 import BeautifulSoup
import pandas as pd

from app.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


class TeamRankingsCrawler(BaseCrawler):
    """Scrape TeamRankings tables where current public pages are available."""

    LEAGUE_SLUG = {
        "epl": "soccer/england/premier-league",
        "laliga": "soccer/spain/laliga",
        "serie-a": "soccer/italy/serie-a",
        "bundesliga": "soccer/germany/bundesliga",
        "ligue-1": "soccer/france/ligue-1",
        "worldcup": "soccer/world-cup",
        "world-cup": "soccer/world-cup",
        "international": "soccer",
    }

    def __init__(self):
        super().__init__(source_code="teamrankings", base_url="https://www.teamrankings.com/")

    def crawl(self, target: str = "rankings", league: str = "epl", **kwargs) -> list[dict]:
        if target == "rankings":
            return self._crawl_rankings(league, **kwargs)
        if target == "ratings":
            return self._crawl_ratings(league, **kwargs)
        logger.warning("[teamrankings] 不支持的采集目标: %s", target)
        return []

    def _league_url(self, league: str) -> str:
        slug = self.LEAGUE_SLUG.get(league, f"soccer/{league}")
        return f"{self.base_url}{slug}"

    def _crawl_rankings(self, league: str, **kwargs) -> list[dict]:
        if league in {"worldcup", "world-cup", "international"}:
            return self._crawl_worldcup_advancement()
        return self._parse_legacy_league_table(f"{self._league_url(league)}/rankings/", league, target="rankings")

    def _crawl_ratings(self, league: str, **kwargs) -> list[dict]:
        if league in {"worldcup", "world-cup", "international"}:
            return self._crawl_worldcup_market_odds()
        return self._parse_legacy_league_table(f"{self._league_url(league)}/power-ratings/", league, target="ratings")

    def _crawl_worldcup_advancement(self) -> list[dict]:
        response = self._fetch(f"{self.base_url}soccer/world-cup/advancement")
        rows = self._read_first_table(response.text)
        results: list[dict] = []
        for row in rows:
            team = row.get("Team")
            if not team:
                continue
            results.append(
                {
                    "source": self.source_code,
                    "league": "World Cup",
                    "season": "2026",
                    "team": team,
                    "group": row.get("Grp"),
                    "rank": self._to_int(row.get("#")),
                    "round_of_32_pct": self._to_percent(row.get("R32")),
                    "round_of_16_pct": self._to_percent(row.get("R16")),
                    "quarterfinal_pct": self._to_percent(row.get("QF")),
                    "semifinal_pct": self._to_percent(row.get("SF")),
                    "final_pct": self._to_percent(row.get("Final")),
                    "champion_pct": self._to_percent(row.get("Champ")),
                }
            )
        return results

    def _crawl_worldcup_market_odds(self) -> list[dict]:
        response = self._fetch(f"{self.base_url}soccer/world-cup/odds")
        rows = self._read_first_table(response.text)
        results: list[dict] = []
        for row in rows:
            team = row.get("Team")
            if not team:
                continue
            results.append(
                {
                    "source": self.source_code,
                    "league": "World Cup",
                    "season": "2026",
                    "team": team,
                    "rank": self._to_int(row.get("#")),
                    "model_pct": self._to_percent(row.get("Our Model")),
                    "consensus_pct": self._to_percent(row.get("Consensus")),
                    "sportsbook_pct": self._to_percent(row.get("Sportsbook")),
                    "polymarket_pct": self._to_percent(row.get("Polymarket")),
                    "market_diff_pct": self._to_signed_float(row.get("Diff")),
                }
            )
        return results

    def _parse_legacy_league_table(self, url: str, league: str, target: str) -> list[dict]:
        response = self._fetch(url)
        soup = BeautifulSoup(response.text, "lxml")
        page_title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
        if "not found" in page_title or "404" in page_title:
            logger.warning("[%s] %s page unavailable for league=%s url=%s", self.source_code, target, league, url)
            return []

        rows = self._read_first_table(response.text)
        results: list[dict] = []
        for row in rows:
            team = row.get("Team") or row.get("team")
            if not team:
                continue
            results.append(
                {
                    "source": self.source_code,
                    "league": league,
                    "team": team,
                    "rank": self._to_int(row.get("#") or row.get("Rank") or row.get("rank")),
                    "rating": self._to_signed_float(row.get("Rating") or row.get("rating")),
                }
            )
        return results

    @staticmethod
    def _read_first_table(html: str) -> list[dict]:
        try:
            tables = pd.read_html(StringIO(html))
        except ValueError:
            return []
        if not tables:
            return []
        frame = tables[0].copy()
        unnamed = [column for column in frame.columns if str(column).startswith("Unnamed:")]
        if unnamed:
            frame = frame.drop(columns=unnamed)
        return frame.to_dict(orient="records")

    @staticmethod
    def _to_int(value) -> int | None:
        if value is None:
            return None
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        if not digits:
            return None
        try:
            return int(digits)
        except ValueError:
            return None

    @staticmethod
    def _to_percent(value) -> float | None:
        if value is None:
            return None
        text = str(value).strip().replace("%", "").replace("<", "")
        if text in {"", "-", "—"}:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _to_signed_float(value) -> float | None:
        if value is None:
            return None
        text = str(value).strip().replace("%", "").replace("*", "")
        if text in {"", "-", "—"}:
            return None
        if text == "~":
            return 0.0
        try:
            return float(text)
        except ValueError:
            return None
