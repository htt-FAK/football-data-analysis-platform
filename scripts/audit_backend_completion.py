from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ["ENABLE_SCHEDULER"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi.testclient import TestClient

from app.main import app


def main():
    client = TestClient(app)

    paths = {
        "worldcup_summary": "/api/v1/worldcup/summary?season=2026",
        "worldcup_coverage": "/api/v1/worldcup/coverage?season=2026",
        "worldcup_upcoming": "/api/v1/worldcup/upcoming?season=2026&limit=8",
        "league_detail": "/api/v1/leagues/3",
        "league_standings": "/api/v1/leagues/3/standings?season=2026",
        "league_schedule": "/api/v1/leagues/3/schedule?season=2026",
        "league_trends": "/api/v1/leagues/3/trends?season=2026",
        "team_stats": "/api/v1/teams/34/stats?season=2026",
        "team_radar": "/api/v1/teams/34/radar?season=2026",
        "match_events": "/api/v1/matches/1521/events",
        "match_report": "/api/v1/matches/1521/report",
        "match_shots": "/api/v1/matches/1521/shots",
        "player_compare": "/api/v1/players/compare?player_a=693&player_b=698&season=2026",
        "player_compare_eventful": "/api/v1/players/compare?player_a=1249&player_b=1257&season=2026",
        "data_sources_health": "/api/v1/data-sources/health",
    }

    responses: dict[str, dict] = {}
    for key, path in paths.items():
        resp = client.get(path)
        responses[key] = {
            "path": path,
            "status_code": resp.status_code,
            "ok": resp.status_code == 200,
            "payload": resp.json() if resp.status_code == 200 else resp.text,
        }

    coverage_items = responses["worldcup_coverage"]["payload"].get("coverage", [])
    coverage_map = {item["module"]: item for item in coverage_items}
    health_rows = responses["data_sources_health"]["payload"]
    warning_sources = [
        row["source_code"]
        for row in health_rows
        if isinstance(row, dict)
        and (
            row.get("health") == "warning"
            or (row.get("last_log") or {}).get("status") == "partial"
            or (row.get("last_log") or {}).get("raw_status") == "partial"
            or (row.get("last_log") or {}).get("raw_status") == "failed"
        )
    ]

    report_payload = responses["match_report"]["payload"]
    result = {
        "routes": {
            key: {"ok": value["ok"], "status_code": value["status_code"], "path": value["path"]}
            for key, value in responses.items()
        },
        "worldcup": {
            "summary": responses["worldcup_summary"]["payload"],
            "coverage": coverage_items,
            "upcoming_match_count": len(responses["worldcup_upcoming"]["payload"].get("matches", [])),
            "upcoming_ready_count": sum(
                1
                for row in responses["worldcup_upcoming"]["payload"].get("matches", [])
                if row.get("is_ready_for_prediction")
            ),
        },
        "team_stats_quality": {
            "team_34_stats": {
                key: responses["team_stats"]["payload"].get(key)
                for key in ("season", "xg_for", "xg_against", "shots_total", "passes_total", "overall_score")
            },
            "team_34_radar": responses["team_radar"]["payload"],
        },
        "events_quality": {
            "match_1521_event_count": len(responses["match_events"]["payload"]),
            "report_event_count": len(report_payload.get("events", [])),
            "report_shots_total": (report_payload.get("shots") or {}).get("total"),
            "impact_key_events": (report_payload.get("impact_summary") or {}).get("key_events_count"),
        },
        "players_compare": {
            "recommended_visualization": responses["player_compare"]["payload"].get("recommended_visualization"),
            "player_a_key_events": len((responses["player_compare"]["payload"].get("key_events") or {}).get("player_a", [])),
            "player_b_key_events": len((responses["player_compare"]["payload"].get("key_events") or {}).get("player_b", [])),
            "eventful_sample_visualization": responses["player_compare_eventful"]["payload"].get("recommended_visualization"),
            "eventful_sample_player_a_key_events": len((responses["player_compare_eventful"]["payload"].get("key_events") or {}).get("player_a", [])),
            "eventful_sample_player_b_key_events": len((responses["player_compare_eventful"]["payload"].get("key_events") or {}).get("player_b", [])),
        },
        "data_source_observability": {
            "source_count": len(health_rows) if isinstance(health_rows, list) else 0,
            "warning_sources": warning_sources,
            "warning_count": len(warning_sources),
        },
        "completion_matrix": [
            {
                "module": "世界杯 standings/schedule",
                "status": "ready"
                if responses["league_standings"]["ok"] and responses["league_schedule"]["ok"]
                else "missing",
                "evidence": "league standings + schedule routes return 200",
            },
            {
                "module": "世界杯 player stats / ratings",
                "status": "ready"
                if coverage_map.get("球员评分榜", {}).get("status") == "ready"
                and coverage_map.get("球员六维能力雷达", {}).get("status") == "ready"
                else "partial",
                "evidence": coverage_map.get("球员评分榜", {}).get("detail"),
            },
            {
                "module": "世界杯 team_stats / team radar",
                "status": "ready"
                if coverage_map.get("球队攻防雷达", {}).get("status") == "ready"
                and (responses["team_stats"]["payload"].get("shots_total") or 0) > 0
                and (responses["team_stats"]["payload"].get("passes_total") or 0) > 0
                else "partial",
                "evidence": coverage_map.get("球队攻防雷达", {}).get("detail"),
            },
            {
                "module": "世界杯 match_events timeline",
                "status": "ready"
                if coverage_map.get("关键事件影响分析", {}).get("status") == "ready"
                and len(responses["match_events"]["payload"]) > 0
                else "missing",
                "evidence": coverage_map.get("关键事件影响分析", {}).get("detail"),
            },
            {
                "module": "世界杯 shots/xG timeline",
                "status": coverage_map.get("射门热图 / xG 时间线", {}).get("status", "missing"),
                "evidence": coverage_map.get("射门热图 / xG 时间线", {}).get("detail"),
            },
            {
                "module": "世界杯 upcoming fixtures / AI predict backend",
                "status": "ready" if responses["worldcup_upcoming"]["ok"] else "missing",
                "evidence": f"upcoming={len(responses['worldcup_upcoming']['payload'].get('matches', []))}",
            },
            {
                "module": "league trends / historical momentum",
                "status": "ready"
                if responses["league_trends"]["ok"]
                and responses["league_trends"]["payload"].get("trends")
                and "timeline" in responses["league_trends"]["payload"]["trends"][0]
                else ("partial" if responses["league_trends"]["ok"] else "missing"),
                "evidence": responses["league_trends"]["payload"].get("note")
                if responses["league_trends"]["ok"]
                else "league trends route unavailable",
            },
            {
                "module": "data source health / scheduler observability",
                "status": "ready"
                if responses["data_sources_health"]["ok"] and not warning_sources
                else ("partial" if responses["data_sources_health"]["ok"] else "missing"),
                "evidence": (
                    f"health_rows={len(health_rows) if isinstance(health_rows, list) else 0}, "
                    f"warning_sources={warning_sources}"
                ),
            },
        ],
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
