"""Export FIFA World Cup group-stage player attachments from HDFS raw snapshots."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.export.fifa_worldcup_export import export_group_stage_artifacts  # noqa: E402


def main() -> int:
    export_dir = PROJECT_ROOT / "export" / "worldcup_fifa"
    outputs = export_group_stage_artifacts(export_dir)
    for key, path in outputs.items():
        print(f"{key.upper()}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
