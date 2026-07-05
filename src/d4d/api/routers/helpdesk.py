"""Helpdesk inquiry router (B-12)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from d4d.api.envelope import ok
from d4d.services.helpdesk_service import helpdesk_service

router = APIRouter(prefix="/api/helpdesk", tags=["helpdesk"])


@router.post("/inquiries")
def create_inquiry(body: dict[str, Any]) -> dict:
    return ok(helpdesk_service.create_inquiry(body), request_id_prefix="req-helpdesk-inquiry")


@router.get("/inquiries")
def list_inquiries(unit_id: str | None = None, status: str | None = None) -> dict:
    return ok(
        helpdesk_service.list_inquiries({"unit_id": unit_id, "status": status}),
        request_id_prefix="req-helpdesk-list",
    )


@router.post("/inquiries/{inquiry_id}/resolve")
def resolve_inquiry(inquiry_id: str) -> dict:
    return ok(helpdesk_service.resolve_inquiry(inquiry_id), request_id_prefix="req-helpdesk-resolve")


@router.post("/conversations")
def create_conversation(body: dict[str, Any]) -> dict:
    return ok(helpdesk_service.create_conversation(body), request_id_prefix="req-helpdesk-conv-create")


@router.get("/conversations")
def list_conversations(unit_id: str | None = None, status: str | None = None) -> dict:
    return ok(
        helpdesk_service.list_conversations({"unit_id": unit_id, "status": status}),
        request_id_prefix="req-helpdesk-conv-list",
    )


@router.post("/conversations/{conversation_id}/classify")
def classify_conversation(conversation_id: str) -> dict:
    return ok(helpdesk_service.classify_conversation(conversation_id), request_id_prefix="req-helpdesk-conv-classify")


@router.get("/conversations/{conversation_id}/workbench")
def conversation_workbench(conversation_id: str) -> dict:
    return ok(helpdesk_service.workbench(conversation_id), request_id_prefix="req-helpdesk-conv-workbench")


@router.post("/conversations/{conversation_id}/draft-answer")
def draft_answer(conversation_id: str) -> dict:
    return ok(helpdesk_service.draft_answer(conversation_id), request_id_prefix="req-helpdesk-conv-draft")


@router.post("/conversations/{conversation_id}/resolve")
def resolve_conversation(conversation_id: str) -> dict:
    return ok(helpdesk_service.resolve_conversation(conversation_id), request_id_prefix="req-helpdesk-conv-resolve")
