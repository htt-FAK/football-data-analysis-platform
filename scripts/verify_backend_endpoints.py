"""Hit representative backend GET endpoints and verify they return structured responses."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _shape_of(payload) -> str:
    if isinstance(payload, list):
        return f"list[{len(payload)}]"
    if isinstance(payload, dict):
        keys = ",".join(list(payload.keys())[:5])
        return f"dict[{keys}]"
    return type(payload).__name__


def main() -> int:
    os.environ["ENABLE_SCHEDULER"] = "false"
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "backend"))

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    paths = [
        "/",
        "/api/v1/health",
        "/api/v1/leagues/",
        "/api/v1/leagues/3",
        "/api/v1/leagues/3/standings?season=2026",
        "/api/v1/leagues/3/standings?season=2026&stage=Group%20Stage&group=Group%20A",
        "/api/v1/leagues/3/schedule?season=2026",
        "/api/v1/leagues/3/schedule?season=2026&stage=Group%20Stage&group=Group%20A",
        "/api/v1/leagues/3/trends?season=2026",
        "/api/v1/teams/",
        "/api/v1/teams?league_id=3&season=2026",
        "/api/v1/teams/34",
        "/api/v1/teams/34/stats?season=2026",
        "/api/v1/teams/34/radar?season=2026",
        "/api/v1/teams/34/shots?season=2026",
        "/api/v1/players/",
        "/api/v1/players?league_id=3&season=2026&limit=5",
        "/api/v1/players/top-scorers?limit=5&season=2026",
        "/api/v1/players/693",
        "/api/v1/players/693/stats?season=2026",
        "/api/v1/players/693/radar?season=2026",
        "/api/v1/players/693/position-rank?season=2026",
        "/api/v1/players/compare?player_a=693&player_b=698&season=2026",
        "/api/v1/players/position-stats?position=MF&season=2026",
        "/api/v1/matches/",
        "/api/v1/matches?league_id=3&stage=Group%20Stage&group=Group%20A&limit=5",
        "/api/v1/matches/1521",
        "/api/v1/matches/1521/events",
        "/api/v1/matches/1521/shots",
        "/api/v1/matches/1521/xg-timeline",
        "/api/v1/matches/1521/report",
        "/api/v1/live/",
        "/api/v1/live/status",
        "/api/v1/live/1521",
        "/api/v1/data-sources/health",
        "/api/v1/data-sources/logs?limit=5",
        "/api/v1/crawl/1",
        "/api/v1/worldcup/summary?season=2026",
        "/api/v1/worldcup/leaders?season=2026&limit=5",
        "/api/v1/worldcup/players?season=2026&limit=5",
        "/api/v1/worldcup/players/693/radar?season=2026",
        "/api/v1/worldcup/coverage?season=2026",
        "/api/v1/worldcup/upcoming?season=2026&limit=5",
    ]

    results: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    for path in paths:
        response = client.get(path)
        item: dict[str, object] = {
            "path": path,
            "status_code": response.status_code,
        }
        if response.status_code != 200:
            item["ok"] = False
            item["body"] = response.text[:500]
            failures.append(item)
            results.append(item)
            continue

        payload = response.json()
        item["ok"] = True
        item["shape"] = _shape_of(payload)
        results.append(item)

    summary = {
        "total": len(results),
        "passed": sum(1 for item in results if item["ok"]),
        "failed": len(failures),
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if failures:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
