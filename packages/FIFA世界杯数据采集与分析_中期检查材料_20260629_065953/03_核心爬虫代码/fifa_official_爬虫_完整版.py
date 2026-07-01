"""FIFA official World Cup crawler using FIFA public JSON endpoints."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Any

from app.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


class FIFAOfficialCrawler(BaseCrawler):
    """Fetch World Cup schedule and standings from FIFA public APIs."""

    API_BASE_URL = "https://api.fifa.com/api/v3"
    SITE_BASE_URL = "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/"
    COMPETITION_ID = "17"
    SEASON_ID = "285023"
    GROUP_STAGE_ID = "289273"
    DEFAULT_FROM_DATE = "2026-06-11"
    DEFAULT_TO_DATE = "2026-07-19"
    DEFAULT_LEAGUE = "FIFA World Cup"
    DEFAULT_SEASON = "2026"
    FDH_API_BASE_URL = "https://fdh-api.fifa.com/v1"
    GAME_DAY_TOKEN_URL = "https://cxm-api.fifa.com/fifaplusweb/api/external/gameDay/token"
    GAME_DAY_API_BASE_URL = "https://gameday-prod.fifa.mangodev.co.uk/1-0"
    STAFF_PAGE_SIZE = 20
    STAFF_SORT = "_externalSportsPersonId:asc"
    STAFF_COMPETITION_QUERY = (
        "(and role==`urn:gd:staff:role:pla` "
        "tags.name==`urn:gd:tag:staff:fdcp:competition_id` "
        "tags.value==`17`)"
    )
    SUPPORTED_TARGETS = {"live", "schedule", "standings", "players", "player_stats", "statistics"}
    POSITION_MAP = {
        0: "GK",
        1: "DF",
        2: "MF",
        3: "FW",
    }

    MATCH_STATUS_MAP = {
        0: "finished",
        1: "scheduled",
        2: "scheduled",
        3: "scheduled",
        4: "playing",
        5: "playing",
        6: "finished",
        7: "cancelled",
    }

    def __init__(self):
        super().__init__(source_code="fifa_official", base_url=self.SITE_BASE_URL)
        self._gameday_token: str | None = None
        self._gameday_token_expires_at: float = 0.0
        self.session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Accept-Encoding": "gzip, deflate",
                "Origin": "https://www.fifa.com",
                "Pragma": "no-cache",
                "Cache-Control": "no-cache",
                "Referer": self.SITE_BASE_URL,
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
            }
        )

    def _delay(self):
        """Official JSON APIs tolerate a much shorter pause than page scrapers."""
        time.sleep(0.05)

    def crawl(self, target: str, **kwargs):
        """Dispatch supported official targets with real endpoint fetching."""

        if target not in self.SUPPORTED_TARGETS:
            logger.warning("[%s] unsupported target requested: %s", self.source_code, target)
            return []

        if target == "live":
            return self._crawl_schedule(live_only=True, **kwargs)
        if target == "schedule":
            return self._crawl_schedule(**kwargs)
        if target == "standings":
            return self._crawl_standings(**kwargs)
        if target in {"players", "player_stats"}:
            return self._crawl_players(**kwargs)
        if target == "statistics":
            return self._crawl_statistics(**kwargs)
        return []

    def _crawl_schedule(self, live_only: bool = False, **kwargs):
        params = {
            "count": kwargs.get("count", 200),
            "from": kwargs.get("date_from", self.DEFAULT_FROM_DATE),
            "to": kwargs.get("date_to", self.DEFAULT_TO_DATE),
            "idCompetition": kwargs.get("competition_id", self.COMPETITION_ID),
            "language": kwargs.get("language", "en"),
        }
        payload = self._get_json(f"{self.API_BASE_URL}/calendar/matches", params=params)
        matches = payload.get("Results", [])
        normalized = []
        for item in matches:
            record = self._normalize_match(item)
            if not record:
                continue
            if live_only and record.get("status") != "playing":
                continue
            normalized.append(record)
        if live_only:
            if kwargs.get("persist_live_raw", False):
                self._persist_raw_snapshot("live", normalized, params["from"], params["to"], params["idCompetition"])
        else:
            self._persist_raw_snapshot("schedule", normalized, params["from"], params["to"], params["idCompetition"])
        logger.info("[%s] fetched %d FIFA matches", self.source_code, len(normalized))
        return normalized

    def _crawl_standings(self, **kwargs):
        season_id = kwargs.get("season_id", self.SEASON_ID)
        stage_id = kwargs.get("stage_id", self.GROUP_STAGE_ID)
        params = {
            "language": kwargs.get("language", "en"),
            "count": kwargs.get("count", 200),
        }
        url = f"{self.API_BASE_URL}/calendar/{self.COMPETITION_ID}/{season_id}/{stage_id}/standing"
        payload = self._get_json(url, params=params)
        results = payload.get("Results", [])
        normalized = [record for record in (self._normalize_standing(item) for item in results) if record]
        self._persist_raw_snapshot("standings", normalized, self.COMPETITION_ID, season_id, stage_id)
        logger.info("[%s] fetched %d FIFA standings rows", self.source_code, len(normalized))
        return normalized

    def _crawl_players(self, **kwargs):
        language = kwargs.get("language", "en")
        team_pages = self._get_team_pages(language=language)
        squad_records, squad_by_player_id, squad_by_merge_key, team_name_by_external = self._build_squad_master(
            team_pages,
            language=language,
        )
        staff_records = self._fetch_staff_players(
            squad_by_player_id=squad_by_player_id,
            team_name_by_external=team_name_by_external,
        )
        records = self._merge_player_sources(
            squad_records=squad_records,
            squad_by_player_id=squad_by_player_id,
            squad_by_merge_key=squad_by_merge_key,
            staff_records=staff_records,
        )
        logger.info(
            "[%s] built FIFA player snapshot squad=%d staff=%d merged=%d",
            self.source_code,
            len(squad_records),
            len(staff_records),
            len(records),
        )
        self._persist_raw_snapshot("player_stats", records, self.COMPETITION_ID, self.SEASON_ID, "snapshot")
        return records

    def _crawl_statistics(self, **kwargs):
        language = kwargs.get("language", "en")
        standings = self._crawl_standings(language=language)
        schedule = self._crawl_schedule(language=language)
        if not standings:
            logger.warning("[%s] no standings available for statistics crawl", self.source_code)
            return []

        team_pages = self._get_team_pages(language=language)
        _, squad_by_player_id, _, _ = self._build_squad_master(team_pages, language=language)

        finished_group_matches = [
            match
            for match in schedule
            if match.get("status") == "finished" and self._is_group_stage_match(match)
        ]

        team_stats = self._build_team_statistics(standings, finished_group_matches, squad_by_player_id)
        self._persist_raw_snapshot("statistics", team_stats, self.COMPETITION_ID, self.SEASON_ID, self.GROUP_STAGE_ID)
        logger.info(
            "[%s] aggregated %d FIFA team statistics rows across %d finished group matches",
            self.source_code,
            len(team_stats),
            len(finished_group_matches),
        )
        return team_stats

    def _build_team_statistics(
        self,
        standings: list[dict[str, Any]],
        matches: list[dict[str, Any]],
        squad_by_player_id: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        stats_by_team: dict[str, dict[str, Any]] = {}
        team_order: list[str] = []
        team_ids_by_name: dict[str, str] = {}

        for row in standings:
            team_name = str(row.get("team") or "").strip()
            if not team_name:
                continue
            if team_name not in stats_by_team:
                team_order.append(team_name)
            stats_by_team[team_name] = {
                "team": team_name,
                "played": row.get("played", 0) or 0,
                "won": row.get("won", 0) or 0,
                "drawn": row.get("drawn", 0) or 0,
                "lost": row.get("lost", 0) or 0,
                "goals_for": row.get("goals_for", 0) or 0,
                "goals_against": row.get("goals_against", 0) or 0,
                "xg_for": 0.0,
                "xg_against": 0.0,
                "possession": 0.0,
                "shots_total": 0,
                "shots_on_target_total": 0,
                "passes_total": 0,
                "pass_accuracy": 0.0,
                "corners": 0,
                "fouls": 0,
                "clean_sheets": 0,
                "league": row.get("league") or self.DEFAULT_LEAGUE,
                "season": row.get("season") or self.DEFAULT_SEASON,
                "source": self.source_code,
                "_pass_attempts": 0.0,
                "_pass_completed": 0.0,
                "_possession_sum": 0.0,
                "_possession_samples": 0,
            }

        for match in matches:
            home_name = str(match.get("home_team") or "").strip()
            away_name = str(match.get("away_team") or "").strip()
            if not home_name or not away_name:
                continue
            if home_name not in stats_by_team or away_name not in stats_by_team:
                continue

            home_team_id = match.get("home_team_id")
            away_team_id = match.get("away_team_id")
            if home_team_id is not None:
                team_ids_by_name[home_name] = str(home_team_id)
            if away_team_id is not None:
                team_ids_by_name[away_name] = str(away_team_id)

            per_team = self._aggregate_match_team_statistics(match, team_ids_by_name, squad_by_player_id)
            if not per_team:
                continue

            home_metrics = per_team.get(home_name)
            away_metrics = per_team.get(away_name)
            if not home_metrics or not away_metrics:
                continue

            self._apply_match_team_statistics(
                stats_by_team[home_name],
                own_metrics=home_metrics,
                opp_metrics=away_metrics,
                goals_against=match.get("away_score"),
            )
            self._apply_match_team_statistics(
                stats_by_team[away_name],
                own_metrics=away_metrics,
                opp_metrics=home_metrics,
                goals_against=match.get("home_score"),
            )

        rows: list[dict[str, Any]] = []
        for team_name in team_order:
            row = dict(stats_by_team[team_name])
            pass_attempts = float(row.pop("_pass_attempts", 0.0) or 0.0)
            pass_completed = float(row.pop("_pass_completed", 0.0) or 0.0)
            possession_sum = float(row.pop("_possession_sum", 0.0) or 0.0)
            possession_samples = int(row.pop("_possession_samples", 0) or 0)
            row["xg_for"] = round(float(row.get("xg_for") or 0.0), 4)
            row["xg_against"] = round(float(row.get("xg_against") or 0.0), 4)
            row["pass_accuracy"] = round((pass_completed / pass_attempts * 100) if pass_attempts > 0 else 0.0, 2)
            row["possession"] = round((possession_sum / possession_samples) if possession_samples > 0 else 0.0, 2)
            row["shots_total"] = int(row.get("shots_total") or 0)
            row["shots_on_target_total"] = int(row.get("shots_on_target_total") or 0)
            row["passes_total"] = int(row.get("passes_total") or 0)
            row["clean_sheets"] = int(row.get("clean_sheets") or 0)
            rows.append(row)
        return rows

    def _aggregate_match_team_statistics(
        self,
        match: dict[str, Any],
        team_ids_by_name: dict[str, str],
        squad_by_player_id: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, float]]:
        fdh_match_id = match.get("fdh_match_id")
        if not fdh_match_id:
            return {}
        stats_payload = self._fetch_fdh_player_stats(str(fdh_match_id), match.get("match_id"))
        if not stats_payload:
            return {}

        per_team: dict[str, dict[str, float]] = defaultdict(
            lambda: {
                "xg": 0.0,
                "shots": 0.0,
                "shots_on_target": 0.0,
                "passes": 0.0,
                "passes_completed": 0.0,
            }
        )

        home_name = str(match.get("home_team") or "").strip()
        away_name = str(match.get("away_team") or "").strip()
        home_team_key = team_ids_by_name.get(home_name)
        away_team_key = team_ids_by_name.get(away_name)

        for player_id, player_stats in stats_payload.items():
            metric_map = self._stat_rows_to_map(player_stats)
            team_name = self._resolve_match_stat_team_name(
                metric_map,
                home_name,
                away_name,
                home_team_key,
                away_team_key,
                squad_by_player_id.get(str(player_id)),
            )
            if not team_name:
                continue
            per_team[team_name]["xg"] += self._to_number(metric_map.get("XG"))
            per_team[team_name]["shots"] += self._to_number(metric_map.get("AttemptAtGoal"))
            per_team[team_name]["shots_on_target"] += self._to_number(metric_map.get("AttemptAtGoalOnTarget"))
            passes = self._to_number(metric_map.get("Passes"))
            per_team[team_name]["passes"] += passes
            per_team[team_name]["passes_completed"] += self._first_non_null(
                self._to_number(metric_map.get("PassesCompleted")),
                passes * self._to_number(metric_map.get("PassCompletedRate")) / 100 if passes > 0 else 0.0,
            )
        return per_team

    def _resolve_match_stat_team_name(
        self,
        metric_map: dict[str, Any],
        home_name: str,
        away_name: str,
        home_team_key: str | None,
        away_team_key: str | None,
        squad_player: dict[str, Any] | None = None,
    ) -> str | None:
        squad_team = str((squad_player or {}).get("team") or "").strip()
        if squad_team in {home_name, away_name}:
            return squad_team

        for key in ("TeamName", "Team", "teamName", "team"):
            value = metric_map.get(key)
            if value:
                team_name = str(value).strip()
                if team_name in {home_name, away_name}:
                    return team_name

        for key in ("IdTeam", "TeamId", "teamId", "_teamId"):
            value = metric_map.get(key)
            if value is None:
                continue
            team_id = str(value).strip()
            if home_team_key and team_id == home_team_key:
                return home_name
            if away_team_key and team_id == away_team_key:
                return away_name

        home_hint = self._to_number(metric_map.get("Home"))
        away_hint = self._to_number(metric_map.get("Away"))
        if home_hint and not away_hint:
            return home_name
        if away_hint and not home_hint:
            return away_name
        return None

    def _apply_match_team_statistics(
        self,
        row: dict[str, Any],
        own_metrics: dict[str, float],
        opp_metrics: dict[str, float],
        goals_against: Any,
    ):
        own_passes = float(own_metrics.get("passes") or 0.0)
        opp_passes = float(opp_metrics.get("passes") or 0.0)
        total_passes = own_passes + opp_passes

        row["xg_for"] = float(row.get("xg_for") or 0.0) + float(own_metrics.get("xg") or 0.0)
        row["xg_against"] = float(row.get("xg_against") or 0.0) + float(opp_metrics.get("xg") or 0.0)
        row["shots_total"] = int(row.get("shots_total") or 0) + int(round(float(own_metrics.get("shots") or 0.0)))
        row["shots_on_target_total"] = int(row.get("shots_on_target_total") or 0) + int(
            round(float(own_metrics.get("shots_on_target") or 0.0))
        )
        row["passes_total"] = int(row.get("passes_total") or 0) + int(round(own_passes))
        row["_pass_attempts"] = float(row.get("_pass_attempts") or 0.0) + own_passes
        row["_pass_completed"] = float(row.get("_pass_completed") or 0.0) + float(own_metrics.get("passes_completed") or 0.0)

        if total_passes > 0:
            row["_possession_sum"] = float(row.get("_possession_sum") or 0.0) + (own_passes / total_passes * 100)
            row["_possession_samples"] = int(row.get("_possession_samples") or 0) + 1

        if self._safe_int(goals_against) == 0:
            row["clean_sheets"] = int(row.get("clean_sheets") or 0) + 1

    @staticmethod
    def _is_group_stage_match(match: dict[str, Any]) -> bool:
        group_name = str(match.get("group") or "").strip()
        stage_name = str(match.get("stage") or "").strip().lower()
        if group_name.lower().startswith("group"):
            return True
        return "group" in stage_name

    def _persist_raw_snapshot(self, category: str, data: Any, *parts: Any):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = self._slugify("_".join(str(part) for part in parts if part not in (None, "")))
        hdfs_path = f"/sports/raw/{self.source_code}/{category}/{slug}_{ts}.json"
        try:
            self._save_raw_to_hdfs(data, hdfs_path)
        except Exception as exc:
            logger.warning("[%s] failed to write %s raw snapshot to HDFS: %s", self.source_code, category, exc)

    def _get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._fetch(url, params=params)
        try:
            return response.json()
        except ValueError as exc:
            logger.error("[%s] failed to decode JSON from %s: %s", self.source_code, url, exc)
            return {}

    def _get_team_pages(self, language: str = "en", team_ids: set[str] | None = None) -> list[dict[str, Any]]:
        url = f"https://cxm-api.fifa.com/fifaplusweb/api/getAllTeamPages/{self.SEASON_ID}"
        response = self._fetch(url, params={"locale": language})
        try:
            payload = response.json()
        except ValueError as exc:
            logger.error("[%s] failed to decode team pages JSON: %s", self.source_code, exc)
            return []
        if not isinstance(payload, list):
            return []
        if not team_ids:
            return payload
        return [page for page in payload if str(page.get("teamPageId")) in team_ids]

    def _build_squad_master(
        self,
        team_pages: list[dict[str, Any]],
        language: str = "en",
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, str]]:
        squad_records: list[dict[str, Any]] = []
        squad_by_player_id: dict[str, dict[str, Any]] = {}
        squad_by_merge_key: dict[str, dict[str, Any]] = {}
        team_name_by_external: dict[str, str] = {}
        for page in team_pages:
            team_id = page.get("teamPageId")
            if not team_id:
                continue
            squad_payload = self._get_json(
                f"{self.API_BASE_URL}/teams/{team_id}/squad",
                params={
                    "idCompetition": self.COMPETITION_ID,
                    "idSeason": self.SEASON_ID,
                    "language": language,
                },
            )
            team_name = self._localized_text(squad_payload.get("TeamName"))
            external_team_id = self._build_external_team_id(squad_payload.get("IdTeam"))
            if external_team_id and team_name:
                team_name_by_external[external_team_id] = team_name
            for player in squad_payload.get("Players", []):
                player_id = player.get("IdPlayer")
                if not player_id:
                    continue
                normalized = self._with_default_player_metrics(self._normalize_squad_player(player, team_name))
                normalized["_team_external_id"] = external_team_id
                normalized["_merge_key"] = self._build_merge_key(external_team_id, normalized.get("shirt_number"))
                squad_records.append(normalized)
                squad_by_player_id[str(player_id)] = normalized
                if normalized["_merge_key"]:
                    squad_by_merge_key[normalized["_merge_key"]] = normalized
        return squad_records, squad_by_player_id, squad_by_merge_key, team_name_by_external

    def _fetch_staff_players(
        self,
        squad_by_player_id: dict[str, dict[str, Any]],
        team_name_by_external: dict[str, str],
    ) -> list[dict[str, Any]]:
        raw_records: list[dict[str, Any]] = []
        skip = 0
        total = None

        while True:
            payload = self._get_gameday_json(
                "/staff",
                params={
                    "query": self.STAFF_COMPETITION_QUERY,
                    "limit": self.STAFF_PAGE_SIZE,
                    "skip": skip,
                    "sort": self.STAFF_SORT,
                },
            )
            if total is None:
                total = int(payload.get("matchCount") or 0)
            items = payload.get("items") or []
            if not items:
                break
            for item in items:
                normalized = self._normalize_staff_player(
                    item,
                    squad_by_player_id=squad_by_player_id,
                    team_name_by_external=team_name_by_external,
                )
                if normalized:
                    raw_records.append(normalized)
            skip += len(items)
            if total and skip >= total:
                break

        by_player_id: dict[str, dict[str, Any]] = {}
        for record in raw_records:
            player_id = record.get("player_source_id")
            if not player_id:
                continue
            current = by_player_id.get(player_id)
            if current is None or self._is_preferred_staff_record(record, current, squad_by_player_id):
                by_player_id[player_id] = record

        by_merge_key: dict[str, dict[str, Any]] = {}
        staff_records: list[dict[str, Any]] = []
        for record in by_player_id.values():
            merge_key = record.get("_merge_key")
            if not merge_key:
                staff_records.append(record)
                continue
            current = by_merge_key.get(merge_key)
            if current is None or self._is_preferred_staff_record(record, current, squad_by_player_id):
                by_merge_key[merge_key] = record

        staff_records.extend(by_merge_key.values())
        logger.info(
            "[%s] fetched %d FIFA staff rows, deduped to %d",
            self.source_code,
            len(raw_records),
            len(staff_records),
        )
        return staff_records

    def _merge_player_sources(
        self,
        squad_records: list[dict[str, Any]],
        squad_by_player_id: dict[str, dict[str, Any]],
        squad_by_merge_key: dict[str, dict[str, Any]],
        staff_records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged_by_player_id = {record["player_source_id"]: dict(record) for record in squad_records}
        merged_by_merge_key = {
            record.get("_merge_key"): merged_by_player_id[record["player_source_id"]]
            for record in squad_records
            if record.get("_merge_key")
        }
        unmatched_staff = 0

        for staff_record in staff_records:
            target = merged_by_player_id.get(staff_record["player_source_id"])
            if not target and staff_record.get("_merge_key"):
                target = merged_by_merge_key.get(staff_record["_merge_key"])
            if not target:
                unmatched_staff += 1
                continue
            self._overlay_player_record(target, staff_record)

        records = list(merged_by_player_id.values())
        for record in records:
            record.pop("_team_external_id", None)
            record.pop("_merge_key", None)
            record.pop("_minutes_present", None)
        records.sort(
            key=lambda item: (
                item.get("team") or "",
                self._position_rank(item.get("position")),
                item.get("shirt_number") if item.get("shirt_number") is not None else 999,
                item.get("name") or "",
            )
        )
        logger.info("[%s] unmatched staff overlays ignored=%d", self.source_code, unmatched_staff)
        return records

    def _aggregate_player_stats(
        self,
        matches: list[dict[str, Any]],
        squad_map: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        player_totals: dict[str, dict[str, Any]] = {}
        match_count = 0
        for match in matches:
            fdh_match_id = match.get("fdh_match_id")
            if not fdh_match_id:
                continue
            stats_payload = self._fetch_fdh_player_stats(str(fdh_match_id), match.get("match_id"))
            if not stats_payload:
                continue
            match_count += 1
            for player_id, stat_rows in stats_payload.items():
                base = dict(squad_map.get(str(player_id), {}))
                if not base:
                    base = {
                        "name": str(player_id),
                        "team": None,
                        "position": None,
                        "league": self.DEFAULT_LEAGUE,
                        "season": self.DEFAULT_SEASON,
                        "source": self.source_code,
                        "player_source_id": str(player_id),
                    }
                record = player_totals.setdefault(
                    str(player_id),
                    {
                        **base,
                        "appearances": 0,
                        "goals": 0,
                        "assists": 0,
                        "yellow_cards": 0,
                        "red_cards": 0,
                        "minutes_played": 0,
                        "shots": 0,
                        "shots_on_target": 0,
                        "xg": 0.0,
                        "xa": 0.0,
                        "passes": 0,
                        "pass_accuracy": 0.0,
                        "tackles": 0,
                        "interceptions": 0,
                        "rating": 0.0,
                        "_pass_completion_samples": 0,
                        "_rating_samples": 0,
                    },
                )
                metric_map = self._stat_rows_to_map(stat_rows)
                passes = self._to_number(metric_map.get("Passes"))
                passes_completed = self._to_number(metric_map.get("PassesCompleted"))
                attempts = self._to_number(metric_map.get("AttemptAtGoal"))
                on_target = self._to_number(metric_map.get("AttemptAtGoalOnTarget"))
                minutes = self._to_number(metric_map.get("TimePlayed"))
                defensive_pressures = self._to_number(metric_map.get("DefensivePressuresApplied"))
                forced_turnovers = self._to_number(metric_map.get("ForcedTurnovers"))
                rating = self._derive_rating(metric_map)

                record["appearances"] += 1 if minutes > 0 or self._to_number(metric_map.get("MatchesPlayed")) > 0 else 0
                record["goals"] += int(round(self._to_number(metric_map.get("Goals"))))
                record["assists"] += int(round(self._to_number(metric_map.get("Assists"))))
                record["yellow_cards"] += int(round(self._to_number(metric_map.get("YellowCards"))))
                record["red_cards"] += int(round(self._to_number(metric_map.get("RedCards"))))
                record["minutes_played"] += int(round(minutes))
                record["shots"] += int(round(attempts))
                record["shots_on_target"] += int(round(on_target))
                record["xg"] += float(self._to_number(metric_map.get("XG")))
                record["passes"] += int(round(passes))
                record["tackles"] += int(round(defensive_pressures))
                record["interceptions"] += int(round(forced_turnovers))
                if passes > 0:
                    record["pass_accuracy"] += (passes_completed / passes) * 100
                    record["_pass_completion_samples"] += 1
                if rating > 0:
                    record["rating"] += rating
                    record["_rating_samples"] += 1

        for record in player_totals.values():
            pass_samples = record.pop("_pass_completion_samples", 0)
            rating_samples = record.pop("_rating_samples", 0)
            if pass_samples:
                record["pass_accuracy"] = round(record["pass_accuracy"] / pass_samples, 2)
            else:
                record["pass_accuracy"] = 0.0
            if rating_samples:
                record["rating"] = round(record["rating"] / rating_samples, 2)
            else:
                record["rating"] = 0.0
            record["xg"] = round(record["xg"], 4)
            record["xa"] = round(record["xa"], 4)

        logger.info("[%s] aggregated player stats across %d FIFA matches", self.source_code, match_count)
        return player_totals

    def _get_gameday_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        token = self._get_gameday_token()
        response = self._fetch(
            f"{self.GAME_DAY_API_BASE_URL}{path}",
            params=params,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "Origin": "https://www.fifa.com",
                "Referer": self.SITE_BASE_URL,
                "Sec-Fetch-Site": "cross-site",
            },
        )
        try:
            return response.json()
        except ValueError as exc:
            logger.error("[%s] failed to decode gameday JSON from %s: %s", self.source_code, path, exc)
            return {}

    def _get_gameday_token(self) -> str:
        now = time.time()
        if self._gameday_token and now < self._gameday_token_expires_at - 60:
            return self._gameday_token

        response = self._fetch(
            self.GAME_DAY_TOKEN_URL,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://www.fifa.com",
                "Referer": self.SITE_BASE_URL,
                "Sec-Fetch-Site": "same-site",
            },
        )
        payload = response.json()
        self._gameday_token = payload.get("token")
        expires_at = payload.get("expiresAt")
        if expires_at:
            try:
                self._gameday_token_expires_at = datetime.fromisoformat(expires_at).timestamp()
            except ValueError:
                self._gameday_token_expires_at = now + 3600
        else:
            self._gameday_token_expires_at = now + 3600
        if not self._gameday_token:
            raise ValueError("FIFA gameday token missing from response")
        return self._gameday_token

    def _fetch_fdh_player_stats(self, fdh_match_id: str, match_id: str | None = None) -> dict[str, Any]:
        response = self._fetch(
            f"{self.FDH_API_BASE_URL}/stats/match/{fdh_match_id}/players.json",
            headers={
                "Referer": f"https://www.fifa.com/en/match-centre/match/{self.COMPETITION_ID}/{self.SEASON_ID}/{self.GROUP_STAGE_ID}/{match_id or ''}",
                "Origin": "https://www.fifa.com",
                "Sec-Fetch-Site": "cross-site",
            },
        )
        try:
            payload = response.json()
        except ValueError as exc:
            logger.error("[%s] failed to decode FDH player stats JSON for match=%s: %s", self.source_code, fdh_match_id, exc)
            return {}
        return payload if isinstance(payload, dict) else {}

    def _normalize_match(self, item: dict[str, Any]) -> dict[str, Any] | None:
        home = item.get("Home") or {}
        away = item.get("Away") or {}
        home_team = self._localized_text(home.get("TeamName"))
        away_team = self._localized_text(away.get("TeamName"))
        if not home_team or not away_team:
            return None

        date_text, time_text = self._split_iso_datetime(item.get("Date"))
        season_label = self._extract_season_label(item)
        stage_name = self._localized_text(item.get("StageName"))
        group_name = self._localized_text(item.get("GroupName"))
        venue_name = self._localized_text((item.get("Stadium") or {}).get("Name"))
        city_name = self._localized_text((item.get("Stadium") or {}).get("CityName"))
        venue = " - ".join(part for part in (venue_name, city_name) if part)

        return {
            "match_id": item.get("IdMatch"),
            "date": date_text,
            "time": time_text,
            "league": self._localized_text(item.get("CompetitionName")) or self.DEFAULT_LEAGUE,
            "season": season_label,
            "matchday": item.get("MatchDay") or item.get("MatchNumber"),
            "home_team": home_team,
            "home_team_id": home.get("IdTeam"),
            "away_team": away_team,
            "away_team_id": away.get("IdTeam"),
            "home_score": item.get("HomeTeamScore"),
            "away_score": item.get("AwayTeamScore"),
            "status": self._map_match_status(item.get("MatchStatus"), item.get("HomeTeamScore"), item.get("AwayTeamScore")),
            "venue": venue or None,
            "stage": stage_name or None,
            "group": group_name or None,
            "fdh_match_id": self._extract_fdh_match_id(item),
            "source": self.source_code,
        }

    def _normalize_standing(self, item: dict[str, Any]) -> dict[str, Any] | None:
        team = item.get("Team") or {}
        team_name = self._localized_text(team.get("Name"))
        if not team_name:
            return None

        season_label = self.DEFAULT_SEASON
        raw_date = item.get("Date") or item.get("StartDate")
        if raw_date:
            season_label = self._season_from_date(raw_date)

        group_name = self._localized_text(item.get("Group"))
        stage_name = self._localized_text(item.get("StageName"))

        return {
            "team": team_name,
            "position": item.get("Position"),
            "played": item.get("Played", 0),
            "won": item.get("Won", 0),
            "drawn": item.get("Drawn", 0),
            "lost": item.get("Lost", 0),
            "goals_for": item.get("For", 0),
            "goals_against": item.get("Against", 0),
            "goal_diff": item.get("GoalsDiference", 0),
            "points": item.get("Points", 0),
            "form": self._build_form(item.get("MatchResults") or [], item.get("IdTeam")),
            "league": self.DEFAULT_LEAGUE,
            "season": season_label,
            "group": group_name or None,
            "stage": stage_name or None,
            "qualification_status": item.get("QualificationStatus"),
            "source": self.source_code,
        }

    def _normalize_squad_player(self, player: dict[str, Any], team_name: str | None) -> dict[str, Any]:
        player_id = str(player.get("IdPlayer") or "")
        birth_date, _ = self._split_iso_datetime(player.get("BirthDate"))
        picture = player.get("PlayerPicture") or {}
        position = self._normalize_position(player)
        nationality = player.get("IdCountry")
        return {
            "player_source_id": player_id,
            "name": self._localized_text(player.get("PlayerName")) or self._localized_text(player.get("ShortName")) or player_id,
            "team": team_name,
            "position": position,
            "shirt_number": player.get("JerseyNum"),
            "nationality": nationality,
            "birth_date": birth_date,
            "height": self._safe_int(player.get("Height")),
            "weight": self._safe_int(player.get("Weight")),
            "photo_url": picture.get("PictureUrl") or player.get("PictureUrl"),
            "league": self.DEFAULT_LEAGUE,
            "season": self.DEFAULT_SEASON,
            "source": self.source_code,
        }

    def _normalize_staff_player(
        self,
        item: dict[str, Any],
        squad_by_player_id: dict[str, dict[str, Any]],
        team_name_by_external: dict[str, str],
    ) -> dict[str, Any] | None:
        player_source_id = str(item.get("_externalSportsPersonId") or "").strip()
        if not player_source_id:
            return None

        squad_base = squad_by_player_id.get(player_source_id)
        tag_map = self._tag_map(item.get("tags") or [])
        external_team_id = str(item.get("_externalTeamId") or "").strip() or None
        shirt_number = self._safe_int(item.get("jersey"))
        if shirt_number is None:
            shirt_number = self._safe_int(tag_map.get("urn:gd:tag:staff:shirt_number"))
        team_name = (squad_base or {}).get("team") or team_name_by_external.get(external_team_id or "")
        raw_minutes = self._first_non_null(
            tag_map.get("urn:gd:tag:football:stats:total_competition_minutes_played"),
            tag_map.get("urn:gd:tag:football:stats:total_competition_minutes_played_by_event"),
        )
        passes = self._safe_int(tag_map.get("urn:gd:tag:football:stats:passes")) or 0
        passes_completed = self._safe_int(tag_map.get("urn:gd:tag:football:stats:passes_completed")) or 0
        pass_accuracy = self._to_number(
            self._first_non_null(
                tag_map.get("urn:gd:tag:football:stats:passing_accuracy_rate"),
                tag_map.get("urn:gd:tag:football:stats:pass_completed_rate"),
            )
        )
        if pass_accuracy == 0 and passes > 0:
            pass_accuracy = round((passes_completed / passes) * 100, 2)

        record = self._with_default_player_metrics(
            {
                "player_source_id": player_source_id,
                "name": (squad_base or {}).get("name") or self._compose_staff_name(item),
                "team": team_name,
                "position": (squad_base or {}).get("position") or self._normalize_staff_position(tag_map),
                "shirt_number": shirt_number,
                "nationality": (squad_base or {}).get("nationality")
                or tag_map.get("urn:gd:tag:staff:fdcp:country_id"),
                "birth_date": (squad_base or {}).get("birth_date")
                or tag_map.get("urn:gd:tag:staff:date_of_birth"),
                "height": (squad_base or {}).get("height") or self._safe_int(item.get("height")),
                "weight": (squad_base or {}).get("weight") or self._safe_int(item.get("weight")),
                "photo_url": (squad_base or {}).get("photo_url") or self._extract_staff_photo(item),
                "league": self.DEFAULT_LEAGUE,
                "season": self.DEFAULT_SEASON,
                "source": self.source_code,
                "appearances": self._safe_int(
                    self._first_non_null(
                        tag_map.get("urn:gd:tag:football:stats:total_competition_matches_played"),
                        tag_map.get("urn:gd:tag:football:stats:matches_played"),
                    )
                )
                or 0,
                "goals": self._safe_int(
                    self._first_non_null(
                        tag_map.get("urn:gd:tag:football:stats:total_competition_goals_scored"),
                        tag_map.get("urn:gd:tag:football:stats:goals"),
                    )
                )
                or 0,
                "assists": self._safe_int(
                    self._first_non_null(
                        tag_map.get("urn:gd:tag:football:stats:total_competition_assists"),
                        tag_map.get("urn:gd:tag:football:stats:assists"),
                    )
                )
                or 0,
                "yellow_cards": self._safe_int(tag_map.get("urn:gd:tag:football:stats:yellow_cards")) or 0,
                "red_cards": self._safe_int(
                    self._first_non_null(
                        tag_map.get("urn:gd:tag:football:stats:red_cards"),
                        (self._safe_int(tag_map.get("urn:gd:tag:football:stats:direct_red_cards")) or 0)
                        + (self._safe_int(tag_map.get("urn:gd:tag:football:stats:indirect_red_cards")) or 0),
                    )
                )
                or 0,
                "minutes_played": self._safe_int(raw_minutes) or 0,
                "shots": self._safe_int(tag_map.get("urn:gd:tag:football:stats:attempt_at_goal")) or 0,
                "shots_on_target": self._safe_int(tag_map.get("urn:gd:tag:football:stats:attempt_at_goal_on_target")) or 0,
                "xg": round(self._to_number(tag_map.get("urn:gd:tag:football:stats:xg")), 4),
                "xa": 0.0,
                "passes": passes,
                "pass_accuracy": round(pass_accuracy, 2),
                "tackles": self._safe_int(tag_map.get("urn:gd:tag:football:stats:tackles")) or 0,
                "interceptions": self._safe_int(tag_map.get("urn:gd:tag:football:stats:interceptions")) or 0,
                "saves": self._safe_int(
                    self._first_non_null(
                        tag_map.get("urn:gd:tag:football:stats:goalkeeper_saves"),
                        tag_map.get("urn:gd:tag:football:stats:gk_saves"),
                    )
                )
                or 0,
                "save_rate": round(
                    self._to_number(
                        self._first_non_null(
                            tag_map.get("urn:gd:tag:football:stats:goalkeeper_save_percentage"),
                            tag_map.get("urn:gd:tag:football:stats:gk_save_percentage"),
                        )
                    ),
                    2,
                ),
                "xcs": 0.0,
                "sweeper_actions": self._safe_int(
                    self._first_non_null(
                        tag_map.get("urn:gd:tag:football:stats:goalkeeper_defensive_actions_outside_penalty_area"),
                        tag_map.get("urn:gd:tag:football:stats:goalkeeper_defensive_actions_inside_penalty_area"),
                    )
                )
                or 0,
            }
        )
        record["rating"] = self._derive_staff_rating(record)
        record["_team_external_id"] = external_team_id
        record["_merge_key"] = self._build_merge_key(external_team_id, shirt_number)
        record["_minutes_present"] = raw_minutes is not None
        return record

    def _normalize_position(self, player: dict[str, Any]) -> str | None:
        real_position = player.get("RealPosition")
        if real_position in self.POSITION_MAP:
            return self.POSITION_MAP[real_position]
        position = player.get("Position")
        return self.POSITION_MAP.get(position)

    @staticmethod
    def _stat_rows_to_map(stat_rows: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if not isinstance(stat_rows, list):
            return result
        for row in stat_rows:
            if isinstance(row, list) and len(row) >= 2:
                result[str(row[0])] = row[1]
        return result

    @staticmethod
    def _to_number(value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _first_non_null(*values: Any) -> Any:
        for value in values:
            if value is not None:
                return value
        return None

    @staticmethod
    def _build_external_team_id(team_id: Any) -> str | None:
        if team_id is None:
            return None
        return f"{FIFAOfficialCrawler.SEASON_ID}_{team_id}"

    @staticmethod
    def _build_merge_key(external_team_id: str | None, shirt_number: int | None) -> str | None:
        if not external_team_id or shirt_number is None:
            return None
        return f"{external_team_id}:{shirt_number}"

    @staticmethod
    def _tag_map(tags: list[dict[str, Any]]) -> dict[str, Any]:
        return {str(tag.get("name")): tag.get("value") for tag in tags if tag.get("name")}

    @staticmethod
    def _slugify(value: str) -> str:
        slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")
        while "__" in slug:
            slug = slug.replace("__", "_")
        return slug or "snapshot"

    @staticmethod
    def _localized_scalar(value: Any) -> str:
        if isinstance(value, dict):
            if "eng" in value and value["eng"]:
                return str(value["eng"]).strip()
            for inner in value.values():
                if inner:
                    return str(inner).strip()
            return ""
        if isinstance(value, list):
            for inner in value:
                localized = FIFAOfficialCrawler._localized_scalar(inner)
                if localized:
                    return localized
            return ""
        if value is None:
            return ""
        return str(value).strip()

    def _compose_staff_name(self, item: dict[str, Any]) -> str:
        first_name = self._localized_scalar(item.get("firstName"))
        last_name = self._localized_scalar(item.get("lastName"))
        full_name = " ".join(part for part in (first_name, last_name) if part).strip()
        return full_name or self._localized_scalar(item.get("displayName")) or self._localized_scalar(item.get("name"))

    def _normalize_staff_position(self, tag_map: dict[str, Any]) -> str | None:
        raw_position = str(tag_map.get("urn:gd:tag:staff:position") or "").strip().lower()
        if raw_position in {"goalkeeper", "keeper", "gk"}:
            return "GK"
        if raw_position in {"defender", "df", "centre-back", "full-back"}:
            return "DF"
        if raw_position in {"midfielder", "mf", "wing-back"}:
            return "MF"
        if raw_position in {"forward", "fw", "attacker", "striker"}:
            return "FW"
        return None

    @staticmethod
    def _extract_staff_photo(item: dict[str, Any]) -> str | None:
        images = item.get("images")
        if isinstance(images, list):
            for image in images:
                if isinstance(image, dict):
                    url = image.get("url") or image.get("href")
                    if url:
                        return str(url)
        if isinstance(images, dict):
            return str(images.get("url") or images.get("href") or "") or None
        return None

    @staticmethod
    def _with_default_player_metrics(base: dict[str, Any]) -> dict[str, Any]:
        record = {
            "appearances": 0,
            "goals": 0,
            "assists": 0,
            "yellow_cards": 0,
            "red_cards": 0,
            "minutes_played": 0,
            "shots": 0,
            "shots_on_target": 0,
            "xg": 0.0,
            "xa": 0.0,
            "passes": 0,
            "pass_accuracy": 0.0,
            "tackles": 0,
            "interceptions": 0,
            "rating": 0.0,
            "saves": 0,
            "save_rate": 0.0,
            "xcs": 0.0,
            "sweeper_actions": 0,
        }
        record.update(base)
        return record

    def _overlay_player_record(self, target: dict[str, Any], overlay: dict[str, Any]):
        bio_fields = ("team", "position", "shirt_number", "nationality", "birth_date", "height", "weight", "photo_url")
        for field in bio_fields:
            if not target.get(field) and overlay.get(field) is not None:
                target[field] = overlay.get(field)

        metric_fields = (
            "appearances",
            "goals",
            "assists",
            "yellow_cards",
            "red_cards",
            "minutes_played",
            "shots",
            "shots_on_target",
            "xg",
            "xa",
            "passes",
            "pass_accuracy",
            "tackles",
            "interceptions",
            "rating",
            "saves",
            "save_rate",
            "xcs",
            "sweeper_actions",
        )
        for field in metric_fields:
            target[field] = overlay.get(field, target.get(field))
        target["_minutes_present"] = overlay.get("_minutes_present", target.get("_minutes_present"))

    def _is_preferred_staff_record(
        self,
        candidate: dict[str, Any],
        current: dict[str, Any],
        squad_by_player_id: dict[str, dict[str, Any]],
    ) -> bool:
        return self._staff_preference_key(candidate, squad_by_player_id) > self._staff_preference_key(current, squad_by_player_id)

    def _staff_preference_key(
        self,
        record: dict[str, Any],
        squad_by_player_id: dict[str, dict[str, Any]],
    ) -> tuple[int, int, int, int, float]:
        player_id = record.get("player_source_id") or ""
        numeric_id = self._safe_int(player_id) or 0
        return (
            1 if player_id in squad_by_player_id else 0,
            1 if record.get("_minutes_present") else 0,
            self._safe_int(record.get("minutes_played")) or 0,
            self._safe_int(record.get("appearances")) or 0,
            -float(numeric_id),
        )

    @staticmethod
    def _position_rank(position: str | None) -> int:
        order = {"GK": 0, "DF": 1, "MF": 2, "FW": 3}
        return order.get(position or "", 9)

    @staticmethod
    def _derive_staff_rating(record: dict[str, Any]) -> float:
        goals = FIFAOfficialCrawler._to_number(record.get("goals"))
        assists = FIFAOfficialCrawler._to_number(record.get("assists"))
        xg = FIFAOfficialCrawler._to_number(record.get("xg"))
        shots_on_target = FIFAOfficialCrawler._to_number(record.get("shots_on_target"))
        pass_accuracy = FIFAOfficialCrawler._to_number(record.get("pass_accuracy"))
        tackles = FIFAOfficialCrawler._to_number(record.get("tackles"))
        saves = FIFAOfficialCrawler._to_number(record.get("saves"))
        if not any((goals, assists, xg, shots_on_target, pass_accuracy, tackles, saves)):
            return 0.0
        rating = (
            min(goals * 1.6, 4.0)
            + min(assists * 1.2, 2.4)
            + min(xg * 1.5, 1.5)
            + min(shots_on_target * 0.25, 1.0)
            + min(pass_accuracy / 25, 1.5)
            + min(tackles * 0.15, 1.2)
            + min(saves * 0.2, 1.5)
        )
        return round(min(10.0, rating), 2)

    @staticmethod
    def _derive_rating(metric_map: dict[str, Any]) -> float:
        threat = FIFAOfficialCrawler._to_number(metric_map.get("Threat"))
        xg = FIFAOfficialCrawler._to_number(metric_map.get("XG"))
        passes = FIFAOfficialCrawler._to_number(metric_map.get("Passes"))
        passes_completed = FIFAOfficialCrawler._to_number(metric_map.get("PassesCompleted"))
        defensive = FIFAOfficialCrawler._to_number(metric_map.get("DefensivePressuresApplied"))
        total_distance = FIFAOfficialCrawler._to_number(metric_map.get("TotalDistance"))
        if not any((threat, xg, passes, defensive, total_distance)):
            return 0.0
        pass_accuracy = (passes_completed / passes * 100) if passes > 0 else 0.0
        rating = (
            min(threat / 10, 3.0)
            + min(xg * 2.5, 2.5)
            + min(pass_accuracy / 20, 2.0)
            + min(defensive / 20, 1.5)
            + min(total_distance / 6000, 1.0)
        )
        return round(min(10.0, rating), 2)

    @staticmethod
    def _extract_fdh_match_id(item: dict[str, Any]) -> str | None:
        properties = item.get("Properties") or {}
        fdh_id = properties.get("IdIFES")
        return str(fdh_id) if fdh_id is not None else None

    @staticmethod
    def _localized_text(value: Any) -> str:
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict) and entry.get("Description"):
                    return str(entry["Description"]).strip()
            return ""
        if isinstance(value, dict):
            description = value.get("Description")
            return str(description).strip() if description else ""
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _split_iso_datetime(value: str | None) -> tuple[str | None, str | None]:
        if not value:
            return None, None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
        except ValueError:
            return value[:10], value[11:16] if len(value) >= 16 else None

    @staticmethod
    def _season_from_date(value: str) -> str:
        try:
            return str(datetime.fromisoformat(value.replace("Z", "+00:00")).year)
        except ValueError:
            return value[:4] if len(value) >= 4 else FIFAOfficialCrawler.DEFAULT_SEASON

    def _extract_season_label(self, item: dict[str, Any]) -> str:
        season_name = self._localized_text(item.get("SeasonName"))
        if season_name:
            for token in season_name.split():
                if token.isdigit() and len(token) == 4:
                    return token
        date_value = item.get("Date")
        if date_value:
            return self._season_from_date(date_value)
        return self.DEFAULT_SEASON

    def _map_match_status(self, status_code: Any, home_score: Any, away_score: Any) -> str:
        try:
            code = int(status_code)
        except (TypeError, ValueError):
            code = None
        if code in self.MATCH_STATUS_MAP:
            return self.MATCH_STATUS_MAP[code]
        if home_score is not None and away_score is not None:
            return "finished"
        return "scheduled"

    @staticmethod
    def _build_form(results: list[dict[str, Any]], team_id: Any) -> str | None:
        if not results or not team_id:
            return None
        form = []
        for result in sorted(results, key=lambda item: item.get("StartTime") or ""):
            home_id = str(result.get("HomeTeamId")) if result.get("HomeTeamId") is not None else None
            away_id = str(result.get("AwayTeamId")) if result.get("AwayTeamId") is not None else None
            home_score = result.get("HomeTeamScore")
            away_score = result.get("AwayTeamScore")
            if home_score is None or away_score is None:
                continue
            if str(team_id) == home_id:
                if home_score > away_score:
                    form.append("W")
                elif home_score < away_score:
                    form.append("L")
                else:
                    form.append("D")
            elif str(team_id) == away_id:
                if away_score > home_score:
                    form.append("W")
                elif away_score < home_score:
                    form.append("L")
                else:
                    form.append("D")
        return "".join(form[-5:]) or None
