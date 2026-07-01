"""Match service helpers reused by match-facing APIs."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from sqlalchemy import asc
from sqlalchemy.orm import Session

from app.analysis.event_impact import EventImpact
from app.analysis.xg_model import XGModel
from app.crawlers.fifa_official import FIFAOfficialCrawler
from app.models.league import League
from app.models.match import Match
from app.models.match_event import MatchEvent
from app.models.player import Player
from app.models.season import Season
from app.models.shot import Shot
from app.models.team import Team
from app.services.ingest_service import (
    FIFA_DEFAULT_LEAGUE_NAME,
    FIFA_DEFAULT_SEASON_NAME,
    ingest_matches,
)
from app.services.shot_utils import serialize_shot

MATCH_FINISHED_BUFFER_HOURS = 4
# 开赛后多少小时内判定为「进行中(live)」。足球含补时+中场约2h，留1h余量。
MATCH_LIVE_WINDOW_HOURS = 3
WORLD_CUP_REFRESH_TTL_SECONDS = 45
WORLD_CUP_STATUS_SET = {"finished", "live", "playing", "in_progress", "half_time", "postponed", "cancelled"}
_WORLD_CUP_SCHEDULE_CACHE: dict[str, object] = {
    "fetched_at": None,
    "rows_by_source_id": {},
}


def get_worldcup_reference_now() -> datetime:
    """Return a UTC-naive reference timestamp for FIFA World Cup rows."""
    return datetime.utcnow()


def resolve_effective_match_status(match: Match | None, now: datetime | None = None) -> str | None:
    """Return a user-facing status even when upstream rows are stale.

    优先级：
      1. 上游已明确的状态（finished/live/playing/in_progress/half_time/postponed/cancelled）直接透传
         —— playing 归一化为 live，便于前端统一展示
      2. 时间窗口推断（弥补上游回传延迟，保证比赛进行中始终显示「进行中」）：
         - 已开赛且未过 live 窗口（默认 3h）→ live
         - 过了 live 窗口且有比分 → finished
      3. 其余返回原始 status（如 scheduled）
    """
    if not match:
        return None

    status = (match.status or "").strip().lower()
    if status in WORLD_CUP_STATUS_SET:
        # playing 归一化为 live，便于前端统一处理
        return "live" if status == "playing" else status

    reference_now = now or get_worldcup_reference_now()
    match_date = match.match_date

    # 时间窗口推断：仅当有开赛时间时启用
    if match_date:
        elapsed = reference_now - match_date
        if elapsed.total_seconds() > 0:
            # 已开赛
            if elapsed < timedelta(hours=MATCH_LIVE_WINDOW_HOURS):
                # 未过 live 窗口 → 比赛进行中
                return "live"
            # 过了 live 窗口：有比分则判为已结束
            has_confirmed_score = match.home_score is not None or match.away_score is not None
            if has_confirmed_score and elapsed >= timedelta(hours=MATCH_FINISHED_BUFFER_HOURS):
                return "finished"
            # live 窗口与 finished 缓冲之间的灰区（3-4h）：有比分给 finished，没比分保持 live
            if has_confirmed_score:
                return "finished"
            return "live"

    return status or None


def refresh_worldcup_matches(db: Session, matches: Iterable[Match] | None) -> None:
    """Refresh nearby FIFA World Cup rows from the official schedule feed."""
    match_list = [match for match in (matches or []) if match]
    if not match_list:
        return

    now = get_worldcup_reference_now()
    candidates = [
        match
        for match in match_list
        if (match.data_source or "").strip().lower() == "fifa_official"
        and match.source_id
        and match.match_date
        and (
            now - timedelta(hours=6) <= match.match_date <= now + timedelta(hours=6)
            or (resolve_effective_match_status(match, now) != "finished" and (match.home_score is None or match.away_score is None))
        )
    ]
    if not candidates:
        return

    rows_by_source_id = _load_worldcup_schedule_index()
    if not rows_by_source_id:
        return

    refreshed_rows = [
        rows_by_source_id[str(match.source_id)]
        for match in candidates
        if str(match.source_id) in rows_by_source_id
    ]
    if not refreshed_rows:
        return

    ingest_matches(
        db,
        refreshed_rows,
        source="fifa_official",
        league_name=FIFA_DEFAULT_LEAGUE_NAME,
        season_name=FIFA_DEFAULT_SEASON_NAME,
    )
    db.expire_all()


def _load_worldcup_schedule_index() -> dict[str, dict]:
    fetched_at = _WORLD_CUP_SCHEDULE_CACHE.get("fetched_at")
    rows_by_source_id = _WORLD_CUP_SCHEDULE_CACHE.get("rows_by_source_id")
    if (
        isinstance(fetched_at, datetime)
        and isinstance(rows_by_source_id, dict)
        and datetime.now() - fetched_at < timedelta(seconds=WORLD_CUP_REFRESH_TTL_SECONDS)
    ):
        return rows_by_source_id

    try:
        rows = FIFAOfficialCrawler().crawl("schedule")
    except Exception:
        return rows_by_source_id if isinstance(rows_by_source_id, dict) else {}

    indexed_rows = {
        str(row.get("match_id")): row
        for row in rows
        if row.get("match_id") is not None
    }
    _WORLD_CUP_SCHEDULE_CACHE["fetched_at"] = datetime.now()
    _WORLD_CUP_SCHEDULE_CACHE["rows_by_source_id"] = indexed_rows
    return indexed_rows


class MatchService:
    """Reusable match query and serialization helpers."""

    def __init__(self):
        self.event_impact = EventImpact()
        self.xg_model = XGModel()

    def get_match_detail(self, db: Session, match_id: int) -> dict | None:
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            return None
        refresh_worldcup_matches(db, [match])
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            return None

        teams_map = self._load_team_map(db, [match.home_team_id, match.away_team_id])
        league_name = None
        season_name = None
        if match.league_id:
            league = db.query(League).filter(League.id == match.league_id).first()
            league_name = league.name if league else None
        if not league_name and (match.stage or match.group_name):
            league_name = "世界杯"
        if match.season_id:
            season = db.query(Season).filter(Season.id == match.season_id).first()
            season_name = season.name if season else None
        effective_status = resolve_effective_match_status(match)
        return {
            "id": match.id,
            "league_id": match.league_id,
            "league_name": league_name,
            "season_id": match.season_id,
            "season": season_name,
            "matchday": match.matchday,
            "date_time": match.match_date.isoformat() if match.match_date else None,
            "match_date": match.match_date.isoformat() if match.match_date else None,
            "status": effective_status,
            "home_team_id": match.home_team_id,
            "home_team_name": teams_map.get(match.home_team_id),
            "away_team_id": match.away_team_id,
            "away_team_name": teams_map.get(match.away_team_id),
            "home_score": match.home_score,
            "away_score": match.away_score,
            "home_score_ht": match.home_score_ht,
            "away_score_ht": match.away_score_ht,
            "home_ht_score": match.home_score_ht,
            "away_ht_score": match.away_score_ht,
            "venue": match.venue,
            "stage": match.stage,
            "group": match.group_name,
            "group_name": match.group_name,
            "minute": None,
            "referee": None,
            "attendance": None,
            "home_xg": None,
            "away_xg": None,
        }

    def get_match_events(self, db: Session, match_id: int) -> dict | None:
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            return None
        refresh_worldcup_matches(db, [match])
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            return None

        events = (
            db.query(MatchEvent)
            .filter(MatchEvent.match_id == match_id)
            .filter(MatchEvent.event_type.isnot(None))
            .order_by(asc(MatchEvent.minute), asc(MatchEvent.id))
            .all()
        )
        players_map = self._load_player_map(db, [event.player_id for event in events if event.player_id])
        teams_map = self._load_team_map(
            db,
            [match.home_team_id, match.away_team_id] + [event.team_id for event in events if event.team_id],
        )

        serialized_events = [
            {
                "id": event.id,
                "match_id": match_id,
                "minute": event.minute,
                "event_type": event.event_type,
                "team_id": event.team_id,
                "team_name": teams_map.get(event.team_id),
                "player_id": event.player_id,
                "player_name": players_map.get(event.player_id),
                "detail": self._localize_event_detail(
                    event.detail,
                    event.event_type,
                    players_map.get(event.player_id),
                ),
            }
            for event in events
        ]
        effective_status = resolve_effective_match_status(match)
        if not serialized_events:
            serialized_events = self._build_result_timeline(match, teams_map, effective_status)

        return {
            "match_id": match_id,
            "events": serialized_events,
            "available": bool(events),
            "source": "match_events" if events else "match_result_summary",
            "note": None if events else "当前没有真实逐分钟事件，已退化为基于赛果生成的比赛摘要时间线。",
        }

    def get_xg_timeline(self, db: Session, match_id: int) -> dict | None:
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            return None
        refresh_worldcup_matches(db, [match])
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            return None

        shots = self._load_match_shots(db, match_id)
        teams_map = self._load_team_map(db, [match.home_team_id, match.away_team_id])
        return self.xg_model.build_match_xg_timeline(
            match_id=match_id,
            shots=shots,
            home_team_id=match.home_team_id,
            away_team_id=match.away_team_id,
            home_team_name=teams_map.get(match.home_team_id),
            away_team_name=teams_map.get(match.away_team_id),
            home_goals=match.home_score,
            away_goals=match.away_score,
        )

    def get_match_shots(self, db: Session, match_id: int) -> dict | None:
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            return None
        refresh_worldcup_matches(db, [match])
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            return None

        shots = self._load_match_shots(db, match_id)
        team_ids = [shot.team_id for shot in shots if shot.team_id]
        player_ids = [shot.player_id for shot in shots if shot.player_id]
        teams_map = self._load_team_map(db, team_ids)
        players_map = self._load_player_map(db, player_ids)
        serialized_shots = [
            serialize_shot(
                shot,
                match_id=match_id,
                team_name=teams_map.get(shot.team_id),
                player_name=players_map.get(shot.player_id),
            )
            for shot in shots
        ]
        return {
            "match_id": match_id,
            "home_team_id": match.home_team_id,
            "away_team_id": match.away_team_id,
            "total": len(shots),
            "available": bool(shots),
            "source": "shots" if shots else None,
            "note": None if shots else "当前没有真实逐脚射门数据，不会用估算值伪造射门列表。",
            "shots": serialized_shots,
        }

    def get_match_report(self, db: Session, match_id: int) -> dict | None:
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            return None
        refresh_worldcup_matches(db, [match])
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            return None

        detail = self.get_match_detail(db, match_id)
        events = self.get_match_events(db, match_id)
        xg_timeline = self.get_xg_timeline(db, match_id)
        shots = self.get_match_shots(db, match_id)
        event_payload = events["events"] if events else []
        real_event_count = db.query(MatchEvent).filter(MatchEvent.match_id == match_id).count()
        real_shot_count = db.query(Shot).filter(Shot.match_id == match_id).count()
        impact_summary = self._build_event_impact_summary(match, event_payload)
        return {
            "match": {
                "id": match.id,
                "match_date": detail["match_date"],
                "status": detail["status"],
                "home_team": {"id": match.home_team_id, "name": detail["home_team_name"]},
                "away_team": {"id": match.away_team_id, "name": detail["away_team_name"]},
                "home_score": match.home_score,
                "away_score": match.away_score,
                "home_score_ht": match.home_score_ht,
                "away_score_ht": match.away_score_ht,
                "venue": match.venue,
                "stage": match.stage,
                "group": match.group_name,
                "league_id": match.league_id,
                "league_name": detail["league_name"],
                "season_id": match.season_id,
                "season": detail["season"],
            },
            "events": event_payload,
            "impact_summary": impact_summary,
            "xg_timeline": xg_timeline,
            "shots": shots,
            "data_availability": {
                "events": {
                    "available": real_event_count > 0,
                    "rows": real_event_count,
                    "source": events.get("source") if events else None,
                    "note": events.get("note") if events else None,
                },
                "shots": {
                    "available": real_shot_count > 0,
                    "rows": real_shot_count,
                    "source": shots.get("source") if shots else None,
                    "note": shots.get("note") if shots else None,
                },
                "xg_timeline": {
                    "available": bool(xg_timeline and xg_timeline.get("available")),
                    "rows": (xg_timeline.get("coverage") or {}).get("timeline_ready_rows") if xg_timeline else 0,
                    "source": xg_timeline.get("source") if xg_timeline else None,
                    "note": xg_timeline.get("note") if xg_timeline else None,
                },
                "report": {
                    "available": True,
                    "source": "match_result_summary",
                    "note": "聚合报告会如实返回赛果、赛程和数据覆盖情况；xG 与射门只会在真实明细存在时生成。",
                },
            },
        }

    @staticmethod
    def _load_team_map(db: Session, team_ids: list[int | None]) -> dict[int, str]:
        valid_ids = [team_id for team_id in team_ids if team_id]
        if not valid_ids:
            return {}
        return {team.id: team.name for team in db.query(Team).filter(Team.id.in_(valid_ids)).all()}

    @staticmethod
    def _load_player_map(db: Session, player_ids: list[int | None]) -> dict[int, str]:
        valid_ids = [player_id for player_id in player_ids if player_id]
        if not valid_ids:
            return {}
        return {player.id: player.name for player in db.query(Player).filter(Player.id.in_(valid_ids)).all()}

    @staticmethod
    def _build_result_timeline(
        match: Match,
        teams_map: dict[int, str],
        effective_status: str | None = None,
    ) -> list[dict]:
        events = [
            {
                "id": None,
                "match_id": match.id,
                "minute": 0,
                "event_type": "kickoff",
                "team_id": None,
                "team_name": None,
                "player_id": None,
                "player_name": None,
                "detail": "比赛开始",
                "derived": True,
                "source": "match_result_summary",
            }
        ]
        if (effective_status or match.status) == "finished":
            home_name = teams_map.get(match.home_team_id) or "主队"
            away_name = teams_map.get(match.away_team_id) or "客队"
            score = (
                f"{home_name} {match.home_score} - {match.away_score} {away_name}"
                if match.home_score is not None and match.away_score is not None
                else "比赛已结束"
            )
            events.append(
                {
                    "id": None,
                    "match_id": match.id,
                    "minute": 90,
                    "event_type": "full_time",
                    "team_id": None,
                    "team_name": None,
                    "player_id": None,
                    "player_name": None,
                    "detail": score,
                    "derived": True,
                    "source": "match_result_summary",
                }
            )
        return events

    @staticmethod
    def _load_match_shots(db: Session, match_id: int) -> list[Shot]:
        return (
            db.query(Shot)
            .filter(Shot.match_id == match_id)
            .order_by(Shot.minute.asc(), Shot.id.asc())
            .all()
        )

    def _build_event_impact_summary(self, match: Match, events: list[dict]) -> dict:
        if not events:
            return {
                "key_events_count": 0,
                "key_events": [],
                "momentum_curve": [],
                "event_type_breakdown": {},
            }

        normalized_events = []
        for event in events:
            side = self._resolve_event_side(match, event.get("team_id"))
            event_type = self.event_impact.normalize_event_type(event.get("event_type"))
            match_state = {
                "home_score": match.home_score or 0,
                "away_score": match.away_score or 0,
                "total_minutes": 90,
            }
            impact_score = self._calculate_event_impact_score(match_state, event_type, event.get("minute"))
            normalized_events.append(
                {
                    **event,
                    "type": event_type,
                    "side": side,
                    "impact_score": impact_score,
                }
            )

        key_events = self.event_impact.get_key_events(normalized_events)
        key_events = sorted(
            key_events,
            key=lambda item: (
                -(item.get("impact_score") or 0),
                item.get("minute") or 0,
                item.get("id") or 0,
            ),
        )
        event_type_breakdown: dict[str, int] = {}
        for item in normalized_events:
            event_type_breakdown[item["type"]] = event_type_breakdown.get(item["type"], 0) + 1

        return {
            "key_events_count": len(key_events),
            "key_events": key_events[:10],
            "momentum_curve": self.event_impact.get_momentum_curve(normalized_events),
            "event_type_breakdown": event_type_breakdown,
        }

    def _calculate_event_impact_score(self, match_state: dict, event_type: str, minute: int | None) -> float:
        event_minute = minute or 0
        if event_type == "goal":
            return self.event_impact.calculate_goal_impact(match_state, event_minute)
        if event_type in {"yellow", "yellow_card", "red", "red_card"}:
            return self.event_impact.calculate_card_impact(match_state, event_type)
        if event_type == "substitution":
            return 12.0
        if event_type == "penalty":
            return 65.0
        return 5.0

    @staticmethod
    def _resolve_event_side(match: Match, team_id: int | None) -> str:
        if not team_id:
            return "neutral"
        if match.home_team_id == team_id:
            return "home"
        if match.away_team_id == team_id:
            return "away"
        return "neutral"

    @staticmethod
    def _localize_event_detail(
        detail: str | None,
        event_type: str | None,
        player_name: str | None = None,
    ) -> str | None:
        if not detail:
            return detail

        text = detail.strip()
        player = player_name or ""

        if event_type == "goal":
            if " goal (" in text:
                prefix, score = text.split(" goal (", 1)
                score = score.rstrip(")")
                name = player or prefix.strip()
                return f"{name} 进球（{score}）"
            if text.endswith(" goal"):
                name = player or text[:-5].strip()
                return f"{name} 进球"

        if event_type == "yellow_card" and " yellow card" in text:
            prefix, suffix = text.split(" yellow card", 1)
            name = player or prefix.strip()
            reason = suffix.lstrip(":：)").strip()
            return f"{name} 黄牌" + (f"（{reason}）" if reason else "")

        if event_type == "red_card" and " red card" in text:
            prefix, suffix = text.split(" red card", 1)
            name = player or prefix.strip()
            reason = suffix.lstrip(":：)").strip()
            return f"{name} 红牌" + (f"（{reason}）" if reason else "")

        if event_type == "substitution" and text.lower().startswith("substitution:"):
            payload = text[len("Substitution:"):].strip()
            if " in, " in payload and payload.endswith(" out"):
                incoming, outgoing = payload[:-4].split(" in, ", 1)
                return f"换人：{incoming.strip()} 上，{outgoing.strip()} 下"

        return text
