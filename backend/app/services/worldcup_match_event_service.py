"""World Cup match event backfill service for the presentation workflow."""

from __future__ import annotations

import logging
import unicodedata
from datetime import date

from sqlalchemy import exists, func
from sqlalchemy.orm import Session

from app.crawlers.dongqiudi import DongqiudiCrawler
from app.models.league import League
from app.models.match import Match
from app.models.match_event import MatchEvent
from app.models.team import Team
from app.models.season import Season
from app.services.ingest_service import ingest_events
from app.services.season_resolver import resolve_latest_season

logger = logging.getLogger(__name__)

WORLD_CUP_LEAGUE_NAMES = ("世界杯", "FIFA World Cup™", "FIFA World Cup", "World Cup")
GROUP_STAGE_NAMES = {"firststage", "first stage", "groupstage", "group stage"}
WORLD_CUP_TEAM_ALIASES = {
    "korearepublic": "southkorea",
    "southkorea": "southkorea",
    "czechia": "czech",
    "czechrepublic": "czech",
    "usa": "unitedstates",
    "unitedstatesofamerica": "unitedstates",
    "unitedstates": "unitedstates",
    "turkiye": "turkey",
    "tuerkiye": "turkey",
    "türkiye": "turkey",
    "bosniaandherzegovina": "bosniaherzegovina",
    "bosnia-herzegovina": "bosniaherzegovina",
    "curacao": "curacao",
    "curaçao": "curacao",
    "iriran": "iran",
    "caboverde": "capeverde",
    "cotedivoire": "ivorycoast",
}


class WorldCupMatchEventBackfillService:
    """Backfill key match events for finished World Cup matches."""

    def __init__(self, crawler: DongqiudiCrawler | None = None):
        self.crawler = crawler or DongqiudiCrawler()

    def backfill_finished_match_events(
        self,
        db: Session,
        season_name: str = "2026",
        limit: int | None = None,
        match_ids: list[int] | None = None,
        skip_existing: bool = True,
    ) -> dict:
        league, season = self._resolve_worldcup_context(db, season_name)
        matches = self._select_target_matches(
            db,
            league.id,
            season.id,
            match_ids=match_ids,
            limit=limit,
            skip_existing=skip_existing,
        )
        schedule_cache = self._load_schedule_cache(matches)
        teams_map = self._load_team_names(db, matches)

        summary = {
            "league_name": league.name,
            "league_id": league.id,
            "season": season.name,
            "season_id": season.id,
            "scanned_matches": len(matches),
            "processed_matches": 0,
            "already_present": 0,
            "mapped_matches": 0,
            "fetched_matches": 0,
            "empty_overviews": 0,
            "created_matches": 0,
            "updated_matches": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "skip_existing": skip_existing,
            "requested_match_ids": match_ids or [],
            "unmatched_matches": [],
            "failed_matches": [],
        }

        for match in matches:
            if skip_existing and self._match_has_real_events(db, match.id):
                summary["already_present"] += 1
                continue

            summary["processed_matches"] += 1
            mapped = self._match_schedule_row(match, teams_map, schedule_cache)
            if not mapped:
                summary["unmatched_matches"].append(self._serialize_match_label(match, teams_map))
                continue

            summary["mapped_matches"] += 1

            try:
                overview = self.crawler.fetch_match_overview(mapped["match_id"])
                raw_events = self.crawler.normalize_overview_events(mapped["match_id"], overview)
                summary["fetched_matches"] += 1
                if not raw_events:
                    summary["empty_overviews"] += 1
                    db.rollback()
                    continue

                ingest_result = ingest_events(db, raw_events, match_id=match.id, source="dongqiudi")
                db.commit()
                for key in ("created", "updated", "skipped", "failed"):
                    summary[key] += ingest_result.get(key, 0)
                if ingest_result.get("created", 0) > 0:
                    summary["created_matches"] += 1
                if ingest_result.get("updated", 0) > 0:
                    summary["updated_matches"] += 1
            except Exception as exc:
                db.rollback()
                logger.exception("World Cup match event backfill failed for match_id=%s: %s", match.id, exc)
                summary["failed"] += 1
                summary["failed_matches"].append(
                    {
                        **self._serialize_match_label(match, teams_map),
                        "error": str(exc),
                    }
                )

        return summary

    def backfill_group_stage_events(
        self,
        db: Session,
        season_name: str = "2026",
        limit: int | None = None,
        match_ids: list[int] | None = None,
        skip_existing: bool = True,
    ) -> dict:
        return self.backfill_finished_match_events(
            db,
            season_name=season_name,
            limit=limit,
            match_ids=match_ids,
            skip_existing=skip_existing,
        )

    def _resolve_worldcup_context(self, db: Session, season_name: str) -> tuple[League, Season]:
        league = (
            db.query(League)
            .filter(League.name.in_(WORLD_CUP_LEAGUE_NAMES))
            .order_by(League.id.desc())
            .first()
        )
        if not league:
            raise ValueError("World Cup league not found in database")

        season = resolve_latest_season(db, league_id=league.id, season_name=season_name)
        if not season:
            raise ValueError(f"World Cup season {season_name} not found in database")

        return league, season

    def _select_target_matches(
        self,
        db: Session,
        league_id: int,
        season_id: int,
        match_ids: list[int] | None = None,
        limit: int | None = None,
        skip_existing: bool = False,
    ) -> list[Match]:
        query = (
            db.query(Match)
            .filter(
                Match.league_id == league_id,
                Match.season_id == season_id,
                Match.status == "finished",
            )
            .order_by(Match.match_date.asc(), Match.id.asc())
        )
        if match_ids:
            query = query.filter(Match.id.in_(match_ids))
        elif skip_existing:
            query = query.filter(
                ~exists().where(
                    MatchEvent.match_id == Match.id,
                    MatchEvent.data_source != "match_result_summary",
                )
            )
        if limit:
            query = query.limit(limit)
        rows = query.all()
        return rows

    @staticmethod
    def _match_has_real_events(db: Session, match_id: int) -> bool:
        count = (
            db.query(func.count(MatchEvent.id))
            .filter(
                MatchEvent.match_id == match_id,
                MatchEvent.data_source != "match_result_summary",
            )
            .scalar()
        )
        return bool(count)

    @staticmethod
    def _is_group_stage(stage: str | None, group_name: str | None) -> bool:
        if not group_name:
            return False
        normalized_stage = (stage or "").strip().lower()
        return normalized_stage in GROUP_STAGE_NAMES or bool(group_name.strip())

    def _load_schedule_cache(self, matches: list[Match]) -> dict[date, list[dict]]:
        schedule_cache: dict[date, list[dict]] = {}
        for match in matches:
            match_day = match.match_date.date() if match.match_date else None
            if not match_day or match_day in schedule_cache:
                continue
            rows = self.crawler.fetch_schedule_list_api(match_day.isoformat())
            schedule_cache[match_day] = [
                row
                for row in rows
                if self._normalize_name(((row.get("competition") or {}).get("name") or "")) == "worldcup"
            ]
        return schedule_cache

    @staticmethod
    def _load_team_names(db: Session, matches: list[Match]) -> dict[int, str]:
        team_ids = {match.home_team_id for match in matches if match.home_team_id}
        team_ids |= {match.away_team_id for match in matches if match.away_team_id}
        rows = db.query(Team).filter(Team.id.in_(team_ids)).all() if team_ids else []
        return {team.id: team.name for team in rows}

    def _match_schedule_row(
        self,
        match: Match,
        teams_map: dict[int, str],
        schedule_cache: dict[date, list[dict]],
    ) -> dict | None:
        match_day = match.match_date.date() if match.match_date else None
        if not match_day:
            return None

        home_name = teams_map.get(match.home_team_id or -1, "")
        away_name = teams_map.get(match.away_team_id or -1, "")
        home_norm = self._normalize_name(home_name)
        away_norm = self._normalize_name(away_name)
        candidates = schedule_cache.get(match_day, [])

        matched = []
        for candidate in candidates:
            candidate_home = self._normalize_name(((candidate.get("team_A") or {}).get("name") or ""))
            candidate_away = self._normalize_name(((candidate.get("team_B") or {}).get("name") or ""))
            if candidate_home == home_norm and candidate_away == away_norm:
                matched.append(candidate)

        if len(matched) == 1:
            return matched[0]

        if len(matched) > 1:
            logger.warning("Multiple Dongqiudi candidates found for match_id=%s; skipping", match.id)
        else:
            logger.warning(
                "No Dongqiudi candidate found for match_id=%s (%s vs %s on %s)",
                match.id,
                home_name,
                away_name,
                match_day.isoformat(),
            )
        return None

    def _serialize_match_label(self, match: Match, teams_map: dict[int, str]) -> dict:
        return {
            "match_id": match.id,
            "match_date": match.match_date.isoformat() if match.match_date else None,
            "home_team": teams_map.get(match.home_team_id or -1),
            "away_team": teams_map.get(match.away_team_id or -1),
            "group": match.group_name,
            "stage": match.stage,
        }

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized = unicodedata.normalize("NFKD", name or "")
        normalized = normalized.encode("ascii", "ignore").decode("ascii")
        normalized = normalized.lower().replace("&", "and")
        compact = "".join(ch for ch in normalized if ch.isalnum())
        return WORLD_CUP_TEAM_ALIASES.get(compact, compact)
