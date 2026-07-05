"""Operations Mode foundation router."""

from __future__ import annotations

from fastapi import APIRouter
from typing import Any

from d4d.api.envelope import ok
from d4d.services.operations_runtime import operations_service

router = APIRouter(prefix="/api/ops", tags=["operations"])


@router.get("/units")
def list_units() -> dict:
    return ok(operations_service.list_units(), request_id_prefix="req-ops-units")


@router.get("/adapters/status")
def adapter_status() -> dict:
    return ok(operations_service.adapter_status(), request_id_prefix="req-ops-adapters")


@router.post("/incidents")
def create_incident(body: dict[str, Any]) -> dict:
    return ok(operations_service.create_incident(body), request_id_prefix="req-ops-incident-create")


@router.get("/incidents")
def list_incidents(unit_id: str | None = None, status: str | None = None) -> dict:
    return ok(
        operations_service.list_incidents({"unit_id": unit_id, "status": status}),
        request_id_prefix="req-ops-incidents",
    )


@router.get("/status-board")
def status_board(unit_id: str | None = None) -> dict:
    return ok(operations_service.status_board({"unit_id": unit_id}), request_id_prefix="req-ops-status-board")


@router.get("/incidents/{incident_id}/timeline")
def get_timeline(incident_id: str) -> dict:
    return ok(operations_service.get_timeline(incident_id), request_id_prefix="req-ops-timeline")


@router.post("/incidents/{incident_id}/status")
def transition_incident_status(incident_id: str, body: dict[str, Any]) -> dict:
    return ok(
        operations_service.transition_incident_status(incident_id, body),
        request_id_prefix="req-ops-status",
    )


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str) -> dict:
    return ok(operations_service.get_incident(incident_id), request_id_prefix="req-ops-incident")


@router.get("/notifications")
def list_notifications(unit_id: str | None = None) -> dict:
    return ok(
        operations_service.list_notifications({"unit_id": unit_id}),
        request_id_prefix="req-ops-notifications",
    )


@router.post("/notifications/{notification_id}/ack")
def ack_notification(notification_id: str) -> dict:
    return ok(operations_service.ack_notification(notification_id), request_id_prefix="req-ops-ntf-ack")
