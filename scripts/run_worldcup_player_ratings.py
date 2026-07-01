"""Compute and persist World Cup player dimension ratings."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.services.worldcup_player_rating_service import WorldCupPlayerRatingService  # noqa: E402


def main() -> int:
    db = SessionLocal()
    try:
        result = WorldCupPlayerRatingService().refresh(db)
        print(f"RATING_REFRESH={result}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
