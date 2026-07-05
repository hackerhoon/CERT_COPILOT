"""Operations Mode reuse router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from d4d.api.envelope import ok
from d4d.services.mission_runtime import runtime_service

router = APIRouter(prefix="/api/ops/cases", tags=["ops-cases"])


@router.post("/from-training-session")
def create_from_training_session(body: dict[str, Any]) -> dict:
    return ok(runtime_service.create_ops_case(body), request_id_prefix="req-ops-from-training")
