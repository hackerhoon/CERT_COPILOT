"""StealthMole external threat-intelligence adapter.

Public surface:
    StealthMoleClient   — authenticated API client (sync + async + monitoring)
    load_stealthmole_config — resolve credentials from env / .env
    errors              — typed exceptions (QuotaExceeded, AuthError, ...)
    sanitize            — raw response -> masked, demo-safe view models
"""

from __future__ import annotations

from ..config import StealthMoleConfig, load_stealthmole_config
from .client import StealthMoleClient
from . import errors, redaction, sanitize

__all__ = [
    "StealthMoleClient",
    "StealthMoleConfig",
    "load_stealthmole_config",
    "errors",
    "redaction",
    "sanitize",
]
