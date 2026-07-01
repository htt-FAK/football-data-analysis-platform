"""Shot-driven xG aggregation helpers."""

from __future__ import annotations

from typing import Any

from app.services.shot_utils import (
    coerce_float,
    coerce_int,
    has_xg_timeline_fields,
    serialize_shot,
    shot_sort_key,
)


class XGModel:
    """Build honest, shot-derived xG timeline payloads."""

    def build_match_xg_timeline(
        self,
        *,
        match_id: int,
        shots: list[Any],
        home_team_id: int | None,
        away_team_id: int | None,
        home_team_name: str | None = None,
        away_team_name: str | None = None,
        home_goals: int | None = None,
        away_goals: int | None = None,
    ) -> dict:
        total_shots = len(shots)
        valid_shots = [shot for shot in shots if has_xg_timeline_fields(shot)]
        invalid_shot_count = total_shots - len(valid_shots)

        if not valid_shots:
            reason = (
                "当前比赛尚未采集到真实逐脚射门数据，因此无法生成真实 xG 时间线。"
                if total_shots == 0
                else "已有射门记录，但缺少生成真实 xG 时间线所需的关键字段。"
            )
            return self._empty_result(
                match_id=match_id,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                home_team_name=home_team_name,
                away_team_name=away_team_name,
                home_goals=home_goals,
                away_goals=away_goals,
                note=reason,
                total_shots=total_shots,
                invalid_shot_count=invalid_shot_count,
            )

        timeline = {"home": [], "away": []}
        home_cumulative = 0.0
        away_cumulative = 0.0

        for shot in sorted(valid_shots, key=shot_sort_key):
            shot_team_id = coerce_int(self._value(shot, "team_id"))
            minute = coerce_int(self._value(shot, "minute")) or 0
            xg = coerce_float(self._value(shot, "xg")) or 0.0
            serialized = serialize_shot(shot, match_id=match_id)

            point = {
                "shot_id": serialized["id"],
                "minute": minute,
                "xg": round(xg, 3),
                "result": serialized["result"],
                "x": serialized["x"],
                "y": serialized["y"],
                "player_id": serialized["player_id"],
                "team_id": serialized["team_id"],
                "shot_type": serialized["shot_type"],
                "situation": serialized["situation"],
                "cumulative": 0.0,
                "cumulative_xg": 0.0,
            }
            if shot_team_id == home_team_id:
                home_cumulative += xg
                point["cumulative"] = round(home_cumulative, 3)
                point["cumulative_xg"] = round(home_cumulative, 3)
                timeline["home"].append(point)
            elif shot_team_id == away_team_id:
                away_cumulative += xg
                point["cumulative"] = round(away_cumulative, 3)
                point["cumulative_xg"] = round(away_cumulative, 3)
                timeline["away"].append(point)

        if not timeline["home"] and not timeline["away"]:
            return self._empty_result(
                match_id=match_id,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                home_team_name=home_team_name,
                away_team_name=away_team_name,
                home_goals=home_goals,
                away_goals=away_goals,
                note="已有射门记录，但暂时无法可靠归属到本场比赛双方。",
                total_shots=total_shots,
                invalid_shot_count=invalid_shot_count,
            )

        note = None
        if invalid_shot_count > 0:
            note = f"有 {invalid_shot_count} 条射门记录因字段不完整，未纳入 xG 时间线。"

        return {
            "match_id": match_id,
            "home_team": {
                "id": home_team_id,
                "name": home_team_name,
                "goals": home_goals,
                "final_xg": round(home_cumulative, 3),
                "performance": self.calculate_xg_performance(home_goals, home_cumulative),
            },
            "away_team": {
                "id": away_team_id,
                "name": away_team_name,
                "goals": away_goals,
                "final_xg": round(away_cumulative, 3),
                "performance": self.calculate_xg_performance(away_goals, away_cumulative),
            },
            "timeline": timeline,
            "available": True,
            "shot_count": len(valid_shots),
            "source": "shots",
            "coverage": {
                "total_rows": total_shots,
                "timeline_ready_rows": len(valid_shots),
                "excluded_rows": invalid_shot_count,
            },
            "note": note,
        }

    def calculate_xg_performance(self, goals: int | None, xg: float | None) -> str:
        if goals is None or xg is None:
            return "unknown"
        if xg <= 0:
            return "no_real_shots" if goals == 0 else "outperformed_xg"
        diff = float(goals) - float(xg)
        if diff >= 0.5:
            return "outperformed_xg"
        if diff <= -0.5:
            return "underperformed_xg"
        return "met_expectation"

    @staticmethod
    def _empty_result(
        *,
        match_id: int,
        home_team_id: int | None,
        away_team_id: int | None,
        home_team_name: str | None,
        away_team_name: str | None,
        home_goals: int | None,
        away_goals: int | None,
        note: str,
        total_shots: int,
        invalid_shot_count: int,
    ) -> dict:
        return {
            "match_id": match_id,
            "home_team": {
                "id": home_team_id,
                "name": home_team_name,
                "goals": home_goals,
                "final_xg": None,
                "performance": "unknown",
            },
            "away_team": {
                "id": away_team_id,
                "name": away_team_name,
                "goals": away_goals,
                "final_xg": None,
                "performance": "unknown",
            },
            "timeline": {"home": [], "away": []},
            "available": False,
            "shot_count": 0,
            "source": None,
            "coverage": {
                "total_rows": total_shots,
                "timeline_ready_rows": 0,
                "excluded_rows": invalid_shot_count,
            },
            "note": note,
        }

    @staticmethod
    def _value(shot: Any, field: str):
        if isinstance(shot, dict):
            return shot.get(field)
        return getattr(shot, field, None)
