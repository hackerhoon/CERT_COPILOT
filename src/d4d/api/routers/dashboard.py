"""Cyber defense dashboard router."""

from __future__ import annotations

from fastapi import APIRouter

from d4d.api.envelope import ok
from d4d.services.dashboard_service import dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
def overview(unit_id: str | None = None) -> dict:
    return ok(dashboard_service.overview({"unit_id": unit_id}), request_id_prefix="req-dashboard-overview")


@router.get("/equipment")
def equipment() -> dict:
    return ok(dashboard_service.equipment(), request_id_prefix="req-dashboard-equipment")


@router.get("/threats")
def threats() -> dict:
    return ok(dashboard_service.threats(), request_id_prefix="req-dashboard-threats")


@router.get("/posture")
def posture() -> dict:
    return ok(dashboard_service.posture(), request_id_prefix="req-dashboard-posture")


@router.get("/calendar")
def calendar() -> dict:
    return ok(dashboard_service.calendar(), request_id_prefix="req-dashboard-calendar")


@router.get("/propagation")
def propagation(unit_id: str | None = None) -> dict:
    return ok(dashboard_service.propagation({"unit_id": unit_id}), request_id_prefix="req-dashboard-propagation")
