"""Load sanitized StealthMole collection runs from disk.

The collector writes one directory per run under
`data/stealthmole/sanitized/<run_id>/`. These helpers find and load a run so
the report and scenario builders can consume masked view models (never raw
responses).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def default_sanitized_dir() -> Path:
    """`<repo>/data/stealthmole/sanitized` — parent of per-run folders."""
    return Path(__file__).resolve().parents[3] / "data" / "stealthmole" / "sanitized"


def find_latest_run(sanitized_dir: Path | None = None) -> Path | None:
    """Return the newest run directory (run ids sort lexically by UTC time)."""
    base = sanitized_dir or default_sanitized_dir()
    if not base.exists():
        return None
    runs = sorted(p for p in base.iterdir() if p.is_dir())
    return runs[-1] if runs else None


def load_run(run_dir: Path) -> dict[str, Any]:
    """Load every `*.json` in a run directory into a `{step_name: view}` map."""
    data: dict[str, Any] = {}
    for path in sorted(run_dir.glob("*.json")):
        try:
            data[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            data[path.stem] = {"_error": f"could not read {path.name}"}
    return data


def load_latest_run(sanitized_dir: Path | None = None) -> tuple[str | None, dict[str, Any]]:
    """Convenience: return `(run_id, run_data)` for the newest run."""
    run_dir = find_latest_run(sanitized_dir)
    if run_dir is None:
        return None, {}
    return run_dir.name, load_run(run_dir)
