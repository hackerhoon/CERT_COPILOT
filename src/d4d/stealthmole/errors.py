"""Typed exceptions for the StealthMole client.

The API returns a small set of status codes documented in
`wiki/StealthMole_API_QUICK_REFERENCE.md`. We map them to explicit exception
types so callers (and the collector) can react — e.g. fall back to mock data
on a 426 quota error instead of crashing.
"""

from __future__ import annotations


class StealthMoleError(Exception):
    """Base class for all StealthMole client errors."""

    def __init__(self, message: str, *, status: int | None = None, detail: str | None = None):
        super().__init__(message)
        self.status = status
        self.detail = detail


class AuthError(StealthMoleError):
    """401 — invalid, expired, or reused JWT."""


class PermissionDenied(StealthMoleError):
    """403 / 404 Unauthorized — the account lacks access to the service."""


class NotFound(StealthMoleError):
    """404 — resource / service / indicator not found."""


class BadRequest(StealthMoleError):
    """400 / 422 — invalid parameters."""


class QuotaExceeded(StealthMoleError):
    """426 — monthly query limit exceeded."""


class ExportInProgress(StealthMoleError):
    """406 — export file is still being prepared."""


class SearchTimeout(StealthMoleError):
    """408 — async search timed out for a target."""


class RateLimited(StealthMoleError):
    """429 — too many requests; caller should back off and retry."""


def from_response(status: int, detail: str | None) -> StealthMoleError:
    """Map an HTTP status + `detail` message to a typed exception."""
    text = detail or ""
    lowered = text.lower()
    if status == 400:
        return BadRequest(f"Bad request: {text}", status=status, detail=detail)
    if status == 401:
        return AuthError(f"Authentication failed: {text}", status=status, detail=detail)
    if status == 403:
        return PermissionDenied(f"Permission denied: {text}", status=status, detail=detail)
    if status == 404:
        # A 404 with "Unauthorized." is an access issue, not a missing path.
        if "unauthorized" in lowered:
            return PermissionDenied(f"Unauthorized: {text}", status=status, detail=detail)
        return NotFound(f"Not found: {text}", status=status, detail=detail)
    if status == 406:
        return ExportInProgress(f"Export in progress: {text}", status=status, detail=detail)
    if status == 408:
        return SearchTimeout(f"Search timeout: {text}", status=status, detail=detail)
    if status == 422:
        return BadRequest(f"Validation error: {text}", status=status, detail=detail)
    if status == 426:
        return QuotaExceeded(f"Quota exceeded: {text}", status=status, detail=detail)
    if status == 429:
        return RateLimited(f"Rate limited: {text}", status=status, detail=detail)
    return StealthMoleError(f"HTTP {status}: {text}", status=status, detail=detail)
