"""Knowledge DB router (B-11)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from d4d.api.envelope import ok
from d4d.services.knowledge_service import knowledge_service

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("")
def search_knowledge(query: str | None = None, tags: str | None = None, unit_id: str | None = None) -> dict:
    return ok(
        knowledge_service.search({"query": query, "tags": tags, "unit_id": unit_id}),
        request_id_prefix="req-knowledge",
    )


@router.get("/search")
def unified_search(
    q: str | None = None,
    query: str | None = None,
    source_type: str | None = None,
    tags: str | None = None,
    unit_id: str | None = None,
) -> dict:
    result = knowledge_service.search({"query": query or q, "tags": tags, "unit_id": unit_id})
    if source_type:
        result["items"] = [item for item in result.get("items", []) if item.get("source_type") == source_type]
    result["query"] = query or q
    result["source_type"] = source_type
    return ok(result, request_id_prefix="req-knowledge-search")


@router.post("")
def create_manual_knowledge(body: dict[str, Any]) -> dict:
    return ok(knowledge_service.create_manual(body), request_id_prefix="req-knowledge-manual")


@router.get("/{knowledge_id}")
def get_knowledge(knowledge_id: str) -> dict:
    return ok(knowledge_service.get(knowledge_id), request_id_prefix="req-knowledge-item")
