"""Mission session, equipment, evidence, assessment, action, and AAR routers."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from d4d.api.envelope import ok
from d4d.services.mission_runtime import runtime_service

router = APIRouter(prefix="/api/training/sessions", tags=["training-sessions"])


@router.post("")
def start_session(body: dict[str, Any]) -> dict:
    return ok(runtime_service.start_session(body), request_id_prefix="req-session-start")


@router.get("/{session_id}")
def get_session(session_id: str) -> dict:
    return ok(runtime_service.get_session(session_id), request_id_prefix="req-session")


@router.get("/{session_id}/events")
def get_events(session_id: str, since_seq: int | None = Query(default=None, ge=0)) -> dict:
    return ok(runtime_service.get_events(session_id, since_seq), request_id_prefix="req-events")


@router.post("/{session_id}/equipment/query")
def equipment_query(session_id: str, body: dict[str, Any]) -> dict:
    return ok(runtime_service.equipment_query(session_id, body), request_id_prefix="req-equipment")


@router.post("/{session_id}/equipment/analyze")
def equipment_analyze(session_id: str, body: dict[str, Any]) -> dict:
    return ok(runtime_service.analyze_equipment(session_id, body), request_id_prefix="req-analyze")


@router.post("/{session_id}/evidence/pins")
def pin_evidence(session_id: str, body: dict[str, Any]) -> dict:
    return ok(runtime_service.pin_evidence(session_id, body), request_id_prefix="req-pin")


@router.put("/{session_id}/assessment")
def save_assessment(session_id: str, body: dict[str, Any]) -> dict:
    return ok(runtime_service.save_assessment(session_id, body), request_id_prefix="req-assessment")


@router.post("/{session_id}/evaluation/preview")
def evaluation_preview(session_id: str, body: dict[str, Any]) -> dict:
    data, warnings = runtime_service.evaluation_preview(session_id, body)
    return ok(data, request_id_prefix="req-eval-preview", warnings=warnings)


@router.post("/{session_id}/actions")
def submit_actions(session_id: str, body: dict[str, Any]) -> dict:
    return ok(runtime_service.submit_actions(session_id, body), request_id_prefix="req-actions")


@router.post("/{session_id}/aar")
def create_aar(session_id: str, body: dict[str, Any]) -> dict:
    return ok(runtime_service.create_aar(session_id, body), request_id_prefix="req-aar-create")


@router.get("/{session_id}/aar")
def get_aar(session_id: str) -> dict:
    return ok(runtime_service.get_aar(session_id), request_id_prefix="req-aar-get")
