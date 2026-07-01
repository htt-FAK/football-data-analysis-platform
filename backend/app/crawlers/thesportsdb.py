"""TheSportsDB crawler for events, teams, and player metadata."""

from __future__ import annotations

import logging
from datetime import datetime

from app.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


class TheSportsDBCrawler(BaseCrawler):
    """Read normalized football metadata from TheSportsDB public API."""

    def __init__(self):
        super().__init__(source_code="thesportsdb", base_url="https://www.thesportsdb.com/api/v1/json/3/")

    def crawl(self, target: str, league_id: str = "4328", season: str = "2025-2026", **kwargs) -> list[dict]:
        if target == "events":
            return self._crawl_events(league_id, season, **kwargs)
        if target == "teams":
            return self._crawl_teams(league_id, **kwargs)
        if target == "players":
            return self._crawl_players(league_id, **kwargs)
        logger.warning("[thesportsdb] 不支持的采集目标: %s", target)
        return []

    def _crawl_events(self, league_id: str, season: str, **kwargs) -> list[dict]:
        response = self._fetch(f"{self.base_url}eventsseason.php?id={league_id}&s={season}")
        try:
            payload = response.json()
        except ValueError as exc:
            logger.error("[%s] events JSON parse failed: %s", self.source_code, exc)
            return []
        return [self._normalize_event(row, league_id, season) for row in (payload.get("events", []) or [])]

    def _crawl_teams(self, league_id: str, **kwargs) -> list[dict]:
        response = self._fetch(f"{self.base_url}lookup_all_teams.php?id={league_id}")
        try:
            payload = response.json()
        except ValueError as exc:
            logger.error("[%s] teams JSON parse failed: %s", self.source_code, exc)
            return []
        return [self._normalize_team(row, league_id) for row in (payload.get("teams", []) or [])]

    def _crawl_players(self, league_id: str, **kwargs) -> list[dict]:
        team_id = kwargs.get("team_id")
        if not team_id:
            logger.warning("TheSportsDB players crawl requires team_id")
            return []
        response = self._fetch(f"{self.base_url}lookup_all_players.php?id={team_id}")
        try:
            payload = response.json()
        except ValueError as exc:
            logger.error("[%s] players JSON parse failed: %s", self.source_code, exc)
            return []
        return [self._normalize_player(row, team_id) for row in (payload.get("player", []) or [])]

    def _normalize_event(self, event: dict, league_id: str, season: str) -> dict:
        date_text, time_text = self._split_timestamp(event.get("strTimestamp"))
        return {
            **event,
            "source": self.source_code,
            "source_id": event.get("idEvent"),
            "match_id": event.get("idEvent"),
            "league_id": event.get("idLeague") or league_id,
            "league": event.get("strLeague"),
            "season": event.get("strSeason") or season,
            "date": date_text,
            "time": time_text,
            "status": self._normalize_status(event.get("strStatus")),
            "matchday": self._to_int(event.get("intRound")),
            "home_team": event.get("strHomeTeam"),
            "away_team": event.get("strAwayTeam"),
            "home_score": self._to_int(event.get("intHomeScore")),
            "away_score": self._to_int(event.get("intAwayScore")),
            "home_team_source_id": event.get("idHomeTeam"),
            "away_team_source_id": event.get("idAwayTeam"),
            "venue": event.get("strVenue"),
        }

    def _normalize_team(self, team: dict, league_id: str) -> dict:
        return {
            **team,
            "source": self.source_code,
            "source_id": team.get("idTeam"),
            "team_id": team.get("idTeam"),
            "league_id": team.get("idLeague") or league_id,
            "league": team.get("strLeague"),
            "name": team.get("strTeam"),
            "team": team.get("strTeam"),
            "short_name": team.get("strTeamShort"),
            "country": team.get("strCountry"),
            "stadium": team.get("strStadium"),
            "coach": team.get("strManager"),
            "founded_year": self._to_int(team.get("intFormedYear")),
            "logo_url": team.get("strBadge"),
        }

    def _normalize_player(self, player: dict, team_id: str) -> dict:
        return {
            **player,
            "source": self.source_code,
            "source_id": player.get("idPlayer"),
            "player_id": player.get("idPlayer"),
            "team_source_id": player.get("idTeam") or team_id,
            "team": player.get("strTeam"),
            "name": player.get("strPlayer"),
            "position": player.get("strPosition"),
            "nationality": player.get("strNationality"),
            "birth_date": self._normalize_date(player.get("dateBorn")),
            "height": self._to_int(player.get("strHeight")),
            "weight": self._to_int(player.get("strWeight")),
            "photo_url": player.get("strThumb") or player.get("strCutout"),
        }

    @staticmethod
    def _split_timestamp(timestamp: str | None) -> tuple[str | None, str | None]:
        if not timestamp:
            return None, None
        try:
            parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            return parsed.strftime("%Y-%m-%d"), parsed.strftime("%H:%M:%S")
        except ValueError:
            return str(timestamp)[:10], None

    @staticmethod
    def _normalize_date(value: str | None) -> str | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            return value

    @staticmethod
    def _to_int(value) -> int | None:
        if value is None or value == "":
            return None
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        if not digits:
            return None
        try:
            return int(digits)
        except ValueError:
            return None

    @staticmethod
    def _normalize_status(status: str | None) -> str | None:
        mapping = {
            "match finished": "finished",
            "finished": "finished",
            "not started": "scheduled",
            "postponed": "postponed",
            "cancelled": "cancelled",
            "live": "live",
            "in play": "live",
            "halftime": "half_time",
        }
        if not status:
            return None
        normalized = str(status).strip().lower()
        return mapping.get(normalized, normalized.replace(" ", "_"))
