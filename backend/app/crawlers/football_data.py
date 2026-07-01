"""Football-Data.co.uk importer for historical match CSV datasets."""

from __future__ import annotations

import io
import logging
import re
from datetime import datetime

import pandas as pd
import requests

from app.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


class FootballDataImporter(BaseCrawler):
    """Download and normalize football-data.co.uk match CSVs."""

    LEAGUE_CODE = {
        "E0": "EPL",
        "E1": "EFL Championship",
        "SP1": "La Liga",
        "I1": "Serie A",
        "D1": "Bundesliga",
        "F1": "Ligue 1",
    }

    def __init__(self):
        super().__init__(source_code="football_data", base_url="https://www.football-data.co.uk/")
        self.csv_base_path = "mmz4281"

    def crawl(self, target: str = "matches", league: str = "E0", season: str = "2526", **kwargs) -> list[dict]:
        if target == "matches":
            return self._download_matches(league, season, **kwargs)
        logger.warning("[football_data] 不支持的采集目标: %s", target)
        return []

    @staticmethod
    def _normalize_season(season: str) -> str:
        season_text = str(season).strip()
        if re.fullmatch(r"\d{4}", season_text):
            return season_text

        parts = re.findall(r"\d{2,4}", season_text)
        if len(parts) >= 2:
            return f"{int(parts[0]) % 100:02d}{int(parts[1]) % 100:02d}"
        return season_text

    def _candidate_urls(self, league: str, season: str) -> list[str]:
        normalized_season = self._normalize_season(season)
        return [
            f"{self.base_url}{self.csv_base_path}/{normalized_season}/{league}.csv",
            f"{self.base_url}mmz{normalized_season}/{league}.csv",
        ]

    def _download_matches(self, league: str, season: str, **kwargs) -> list[dict]:
        response = None
        for url in self._candidate_urls(league, season):
            try:
                response = self._fetch(url)
                logger.info("[%s] using CSV source %s", self.source_code, url)
                break
            except requests.RequestException:
                logger.warning("[%s] CSV source unavailable, trying fallback %s", self.source_code, url)

        if response is None:
            logger.error("[%s] no usable CSV source found for league=%s season=%s", self.source_code, league, season)
            return []

        try:
            frame = pd.read_csv(io.BytesIO(response.content))
        except Exception as exc:
            logger.error("[%s] CSV parse failed: %s", self.source_code, exc)
            return []

        return [self._normalize_match_record(record, league, season) for record in frame.to_dict(orient="records")]

    def _normalize_match_record(self, record: dict, league: str, season: str) -> dict:
        date_text = self._normalize_date(record.get("Date"))
        home_score = self._to_int(record.get("FTHG"))
        away_score = self._to_int(record.get("FTAG"))
        return {
            **record,
            "source": self.source_code,
            "source_id": self._build_source_id(record, date_text),
            "league": self.LEAGUE_CODE.get(league, league),
            "league_code": league,
            "season": season,
            "date": date_text,
            "time": self._clean_text(record.get("Time")),
            "home_team": self._clean_text(record.get("HomeTeam")),
            "away_team": self._clean_text(record.get("AwayTeam")),
            "home_score": home_score,
            "away_score": away_score,
            "result": self._clean_text(record.get("FTR")),
            "home_shots": self._to_int(record.get("HS")),
            "away_shots": self._to_int(record.get("AS")),
            "home_shots_on_target": self._to_int(record.get("HST")),
            "away_shots_on_target": self._to_int(record.get("AST")),
            "home_yellow": self._to_int(record.get("HY")),
            "away_yellow": self._to_int(record.get("AY")),
            "home_red": self._to_int(record.get("HR")),
            "away_red": self._to_int(record.get("AR")),
            "home_corners": self._to_int(record.get("HC")),
            "away_corners": self._to_int(record.get("AC")),
            "home_fouls": self._to_int(record.get("HF")),
            "away_fouls": self._to_int(record.get("AF")),
            "referee": self._clean_text(record.get("Referee")),
            "status": "finished" if home_score is not None and away_score is not None else "scheduled",
        }

    @staticmethod
    def _build_source_id(record: dict, date_text: str | None) -> str:
        return "|".join(
            [
                date_text or "",
                str(record.get("HomeTeam") or "").strip(),
                str(record.get("AwayTeam") or "").strip(),
            ]
        )

    @staticmethod
    def _to_int(value):
        if value is None or pd.isna(value):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clean_text(value):
        if value is None or pd.isna(value):
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def _normalize_date(cls, value) -> str | None:
        text = cls._clean_text(value)
        if not text:
            return None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return text


class FootballDataCrawler(FootballDataImporter):
    """Compatibility alias for older imports."""

    pass
