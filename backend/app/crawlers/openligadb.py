"""OpenLigaDB crawler for match and team data."""

from __future__ import annotations

import logging
from datetime import datetime

from app.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


class OpenLigaDBCrawler(BaseCrawler):
    """Normalize OpenLigaDB payloads into project-friendly structures."""

    def __init__(self):
        super().__init__(source_code="openligadb", base_url="https://api.openligadb.de/")

    def crawl(self, target: str, league: str = "bl1", season: str = "2025", **kwargs) -> list[dict]:
        if target == "matches":
            return self._crawl_matches(league, season, **kwargs)
        if target == "teams":
            return self._crawl_teams(league, season, **kwargs)
        logger.warning("[openligadb] 不支持的采集目标: %s", target)
        return []

    def _crawl_matches(self, league: str, season: str, **kwargs) -> list[dict]:
        response = self._fetch(f"{self.base_url}getmatchdata/{league}/{season}")
        try:
            payload = response.json()
        except ValueError as exc:
            logger.error("[%s] matches JSON parse failed: %s", self.source_code, exc)
            return []
        raw_matches = payload if isinstance(payload, list) else []
        return [self._normalize_match(match, league, season) for match in raw_matches]

    def _crawl_teams(self, league: str, season: str, **kwargs) -> list[dict]:
        response = self._fetch(f"{self.base_url}getavailableteams/{league}/{season}")
        try:
            payload = response.json()
        except ValueError as exc:
            logger.error("[%s] teams JSON parse failed: %s", self.source_code, exc)
            return []
        raw_teams = payload if isinstance(payload, list) else []
        return [self._normalize_team(team, league, season) for team in raw_teams]

    def _normalize_match(self, match: dict, league: str, season: str) -> dict:
        date_text, time_text = self._split_datetime(match.get("matchDateTime") or match.get("matchDateTimeUTC"))
        home_score, away_score = self._extract_final_result(match.get("matchResults") or [])
        return {
            **match,
            "source": self.source_code,
            "source_id": match.get("matchID"),
            "match_id": match.get("matchID"),
            "league": match.get("leagueName") or league,
            "league_shortcut": match.get("leagueShortcut") or league,
            "season": str(match.get("leagueSeason") or season),
            "date": date_text,
            "time": time_text,
            "matchday": self._to_int((match.get("group") or {}).get("groupOrderID")),
            "stage": (match.get("group") or {}).get("groupName"),
            "group": (match.get("group") or {}).get("groupName"),
            "home_team": (match.get("team1") or {}).get("teamName"),
            "away_team": (match.get("team2") or {}).get("teamName"),
            "home_team_source_id": (match.get("team1") or {}).get("teamId"),
            "away_team_source_id": (match.get("team2") or {}).get("teamId"),
            "home_score": home_score,
            "away_score": away_score,
            "status": self._normalize_status(match),
            "venue": (match.get("location") or {}).get("locationStadium"),
        }

    def _normalize_team(self, team: dict, league: str, season: str) -> dict:
        return {
            **team,
            "source": self.source_code,
            "source_id": team.get("teamId"),
            "team_id": team.get("teamId"),
            "league": league,
            "season": str(season),
            "name": team.get("teamName"),
            "team": team.get("teamName"),
            "short_name": team.get("shortName"),
            "logo_url": team.get("teamIconUrl"),
        }

    @staticmethod
    def _extract_final_result(results: list[dict]) -> tuple[int | None, int | None]:
        if not results:
            return None, None
        final = next((row for row in results if row.get("resultTypeID") == 2), None) or results[-1]
        return OpenLigaDBCrawler._to_int(final.get("pointsTeam1")), OpenLigaDBCrawler._to_int(final.get("pointsTeam2"))

    @staticmethod
    def _split_datetime(value: str | None) -> tuple[str | None, str | None]:
        if not value:
            return None, None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.strftime("%Y-%m-%d"), parsed.strftime("%H:%M:%S")
        except ValueError:
            return str(value)[:10], None

    @staticmethod
    def _to_int(value) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_status(match: dict) -> str:
        if match.get("matchIsFinished") is True:
            return "finished"
        status = str(match.get("matchStatus") or "").strip().lower()
        if status in {"live", "inprogress", "in_progress"}:
            return "live"
        return "scheduled"
