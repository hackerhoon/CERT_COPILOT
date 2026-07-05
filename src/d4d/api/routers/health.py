"""Health and readiness endpoints for local smoke tests."""

from __future__ import annotations

from fastapi import APIRouter

from d4d.api.envelope import ok
from d4d.services.mission_runtime import runtime_service

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict:
    return ok(
        {
            "status": "ok",
            "service": "cyber-defense-readiness-api",
            "mode": "fixture",
            "storage_backend": runtime_service.repository.backend_name,
        },
        request_id_prefix="req-health",
    )
