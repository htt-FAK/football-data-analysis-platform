"""Offline verification for backend route prefixes and OpenAPI generation."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "backend"))

    from app.main import app

    expected_paths = {
        "/api/v1/leagues/",
        "/api/v1/teams/",
        "/api/v1/players/",
        "/api/v1/matches/",
        "/api/v1/live/",
        "/api/v1/data-sources/health",
        "/api/v1/crawl/trigger",
        "/api/v1/health",
    }

    openapi_paths = sorted(app.openapi().get("paths", {}).keys())
    duplicated_prefix_paths = [
        path
        for path in openapi_paths
        if any(
            token in path
            for token in (
                "/leagues/leagues",
                "/teams/teams",
                "/players/players",
                "/matches/matches",
                "/live/live",
                "/data-sources/data-sources",
                "/crawl/crawl",
            )
        )
    ]
    if duplicated_prefix_paths:
        raise AssertionError(
            f"Found duplicated API prefixes: {duplicated_prefix_paths}"
        )

    missing_openapi_paths = sorted(expected_paths.difference(openapi_paths))
    if missing_openapi_paths:
        raise AssertionError(
            f"OpenAPI missing expected paths: {missing_openapi_paths}"
        )

    print(
        json.dumps(
            {
                "openapi_path_count": len(openapi_paths),
                "verified_paths": sorted(expected_paths),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
