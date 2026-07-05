"""Common API response and error envelope helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse


DEFAULT_MODE = "fixture"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request_id(prefix: str = "req") -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


def ok(data: Any, *, request_id_prefix: str = "req", warnings: list[str] | None = None) -> dict[str, Any]:
    """Wrap successful responses in the API_SPEC response envelope."""
    return {
        "request_id": request_id(request_id_prefix),
        "data": data,
        "warnings": warnings or [],
        "meta": {
            "mode": DEFAULT_MODE,
            "generated_at": _now(),
        },
    }


class ApiError(Exception):
    """Application error that renders as the API_SPEC error envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "request_id": request_id("req-error"),
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
                "details": exc.details,
            },
        },
    )
