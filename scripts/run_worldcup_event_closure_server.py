"""Server-oriented wrapper for World Cup event cleanup, backfill, and verification."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


SCRIPT_SEQUENCE = [
    "scripts/verify_worldcup_event_closure.py",
    "scripts/cleanup_worldcup_empty_match_events.py",
    "scripts/run_worldcup_match_events_backfill.py",
    "scripts/verify_worldcup_event_closure.py",
]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    python_exe = _resolve_python(repo_root)
    log_dir = repo_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"worldcup_event_closure_{timestamp}.log"

    summary: list[dict] = []
    exit_code = 0

    with log_path.open("w", encoding="utf-8") as log_file:
        _write_line(log_file, f"# World Cup event closure started at {timestamp}")
        _write_line(log_file, f"# Python: {python_exe}")
        _write_line(log_file, f"# Repo: {repo_root}")

        for relative_script in SCRIPT_SEQUENCE:
            script_path = repo_root / relative_script
            _write_line(log_file, "")
            _write_line(log_file, f"## Running {relative_script}")
            result = subprocess.run(
                [str(python_exe), str(script_path)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if result.stdout:
                _write_line(log_file, result.stdout.rstrip())
            if result.stderr:
                _write_line(log_file, "[stderr]")
                _write_line(log_file, result.stderr.rstrip())

            summary.append(
                {
                    "script": relative_script,
                    "returncode": result.returncode,
                }
            )
            if result.returncode != 0:
                exit_code = result.returncode
                _write_line(log_file, f"## Aborted because {relative_script} failed")
                break

        _write_line(log_file, "")
        _write_line(log_file, "## Summary")
        _write_line(log_file, json.dumps(summary, ensure_ascii=False, indent=2))

    print(
        json.dumps(
            {
                "log_path": str(log_path),
                "python": str(python_exe),
                "steps": summary,
                "status": "ok" if exit_code == 0 else "failed",
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return exit_code


def _resolve_python(repo_root: Path) -> Path:
    candidates = [
        repo_root / ".venv" / "Scripts" / "python.exe",
        repo_root / ".venv" / "bin" / "python",
        Path(sys.executable),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(sys.executable)


def _write_line(handle, line: str):
    handle.write(line)
    handle.write("\n")
    handle.flush()


if __name__ == "__main__":
    raise SystemExit(main())
