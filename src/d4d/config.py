"""Configuration loading for the D4D intelligence core.

Secrets are read from the environment first, then from a project-root `.env`
file. Never hardcode keys here; `.env` is git-ignored and `.env.tmpl` only
lists variable names.

Two naming conventions are accepted so the code works with either the
documented `STEALTHMOLE_*` names or the shorter `ACCESS_KEY` / `SECRET_KEY`
form that may already be present in a local `.env`:

    STEALTHMOLE_BASE_URL   (default: https://hackathon.stealthmole.com)
    STEALTHMOLE_ACCESS_KEY  | ACCESS_KEY
    STEALTHMOLE_SECRET_KEY  | SECRET_KEY
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "https://hackathon.stealthmole.com"


def project_root() -> Path:
    """Return the repository root (the parent of `src/`)."""
    # config.py lives at <root>/src/d4d/config.py
    return Path(__file__).resolve().parents[2]


def load_dotenv(path: Path) -> dict[str, str]:
    """Minimal `.env` parser.

    Supports `KEY=VALUE` and `KEY = VALUE` lines, `#` comments, and quoted
    values. Intentionally dependency-free so the tool runs without
    `python-dotenv` installed.
    """
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            values[key] = val
    return values


def _first(env: dict[str, str], *names: str, default: str | None = None) -> str | None:
    """Return the first non-empty value among `names`, env taking priority."""
    for name in names:
        val = os.environ.get(name) or env.get(name)
        if val:
            return val
    return default


@dataclass(frozen=True)
class StealthMoleConfig:
    """Resolved StealthMole connection settings."""

    base_url: str
    access_key: str
    secret_key: str

    def redacted(self) -> dict[str, str]:
        """A safe-to-log view of the config (keys masked)."""
        return {
            "base_url": self.base_url,
            "access_key": _mask_key(self.access_key),
            "secret_key": _mask_key(self.secret_key),
        }


def _mask_key(value: str) -> str:
    if not value:
        return "<missing>"
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:4]}...{value[-2:]}"


def load_stealthmole_config(dotenv_path: Path | None = None) -> StealthMoleConfig:
    """Build a `StealthMoleConfig` from env vars and the project `.env`.

    Raises `RuntimeError` if the access/secret keys cannot be found.
    """
    root = project_root()
    env = load_dotenv(dotenv_path or (root / ".env"))

    base_url = _first(env, "STEALTHMOLE_BASE_URL", default=DEFAULT_BASE_URL) or DEFAULT_BASE_URL
    access_key = _first(env, "STEALTHMOLE_ACCESS_KEY", "ACCESS_KEY")
    secret_key = _first(env, "STEALTHMOLE_SECRET_KEY", "SECRET_KEY")

    missing = [
        name
        for name, val in (
            ("STEALTHMOLE_ACCESS_KEY/ACCESS_KEY", access_key),
            ("STEALTHMOLE_SECRET_KEY/SECRET_KEY", secret_key),
        )
        if not val
    ]
    if missing:
        raise RuntimeError(
            "Missing StealthMole credentials: "
            + ", ".join(missing)
            + ". Set them in the environment or in the project .env file."
        )

    return StealthMoleConfig(
        base_url=base_url.rstrip("/"),
        access_key=access_key,  # type: ignore[arg-type]
        secret_key=secret_key,  # type: ignore[arg-type]
    )
