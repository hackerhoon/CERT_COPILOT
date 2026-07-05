"""Adapter status router."""

from __future__ import annotations

from fastapi import APIRouter

from d4d.api.envelope import ok
from d4d.services.scenario_catalog import AdapterStatusService

router = APIRouter(prefix="/api/adapters", tags=["adapters"])
service = AdapterStatusService()


@router.get("/status")
def get_adapter_status() -> dict:
    return ok(service.get_status(), request_id_prefix="req-adapters")
