"""Knowledge accumulation service (B-11).

업무 지식(KnowledgeItem)을 담당자와 무관하게 SQLite에 비휘발로 축적한다.
사건 종결·훈련 AAR 생성·문의 해결이 자동 축적 트리거이며, 모든 축적은
redaction 게이트를 통과한다 — raw 자격증명·이메일·문서용 대역 밖 IP를
지식DB에 넣지 않는다(WORK_SUPPORT_KNOWLEDGE_DESIGN §2).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from d4d.api.envelope import ApiError
from d4d.fixtures.operations import KNOWLEDGE_SEED, clone
from d4d.repositories import OperationsRepository
from d4d.services.operations_runtime import known_evidence_ids, operations_service


VALID_SOURCE_TYPES = {"incident", "action", "aar", "inquiry", "manual"}

# redaction 규칙 — app/tools/safety-scan.js와 동종. 비밀 literal은 축적 자체를
# 차단하고, 이메일/허용 대역 밖 IP는 마스킹해서 저장한다.
RE_SECRET = re.compile(
    r"(password|passwd|secret|api[_-]?key|client[_-]?secret|access[_-]?token)\s*[:=]\s*\S{6,}",
    re.IGNORECASE,
)
RE_JWT = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}")
RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RE_IP = re.compile(r"\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b")
RE_SERVICE_NUMBER = re.compile(r"\b\d{2}-\d{5,7}\b")


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ip_allowed(first: int, second: int) -> bool:
    if first == 127 or first == 10:
        return True
    if first == 192 and second == 168:
        return True
    if first == 172 and 16 <= second <= 31:
        return True
    # RFC5737 문서용 대역
    if (first, second) in {(192, 0), (198, 51), (203, 0)}:
        return True
    return False


def redact_text(value: str, *, field: str) -> str:
    """Mask leak-prone patterns; raise on outright secrets."""
    if RE_SECRET.search(value) or RE_JWT.search(value):
        raise ApiError(
            "REDACTION_BLOCKED",
            "자격증명/비밀로 보이는 값은 지식DB에 축적할 수 없습니다.",
            details={"field": field},
        )
    value = RE_EMAIL.sub("***@***", value)
    value = RE_SERVICE_NUMBER.sub("**-*****", value)

    def _mask_ip(match: re.Match[str]) -> str:
        first, second = int(match.group(1)), int(match.group(2))
        if any(int(match.group(i)) > 255 for i in range(1, 5)):
            return match.group(0)
        if _ip_allowed(first, second):
            return match.group(0)
        return f"{first}.{second}.***.***"

    return RE_IP.sub(_mask_ip, value)


class KnowledgeService:
    """Accumulate, search, and serve non-volatile work knowledge."""

    def __init__(self, repository: OperationsRepository) -> None:
        self.repository = repository
        self._seed()

    def _seed(self) -> None:
        for entry in KNOWLEDGE_SEED:
            self.accumulate(clone(entry))

    # ---- 축적 (2-2) ----

    def accumulate(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Normalize one origin record into a KnowledgeItem (dedup by source)."""
        source_type = fields.get("source_type")
        source_id = str(fields.get("source_id") or "").strip()
        if source_type not in VALID_SOURCE_TYPES:
            raise ApiError("BAD_REQUEST", "source_type이 올바르지 않습니다.", details={"source_type": source_type})
        if not source_id:
            raise ApiError("BAD_REQUEST", "source_id가 필요합니다.", details={"field": "source_id"})

        existing = self.repository.find_knowledge_by_source(source_type, source_id)
        if existing is not None:
            return existing

        title = redact_text(str(fields.get("title") or "").strip(), field="title")
        summary = redact_text(str(fields.get("summary") or "").strip(), field="summary")
        resolution = redact_text(str(fields.get("resolution") or "").strip(), field="resolution")
        if not title or not summary:
            raise ApiError("BAD_REQUEST", "title과 summary가 필요합니다.")
        tags = [redact_text(str(tag).strip(), field="tags") for tag in fields.get("tags") or [] if str(tag).strip()]
        evidence_ids = list(dict.fromkeys(fields.get("evidence_ids") or []))
        self._validate_evidence(evidence_ids)

        sequence = self.repository.next_sequence("ops_knowledge")
        item = {
            "knowledge_id": f"kb-{sequence:03d}",
            "source_type": source_type,
            "source_id": source_id,
            "title": title,
            "summary": summary,
            "tags": tags,
            "evidence_ids": evidence_ids,
            "resolution": resolution,
            "unit_id": fields.get("unit_id"),
            "created_at": fields.get("created_at") or now(),
        }
        self.repository.save_knowledge(item)
        return clone(item)

    def accumulate_from_incident(self, incident: dict[str, Any]) -> dict[str, Any]:
        """사건 종결 시 자동 훅 — timeline 경위를 지식으로 정규화."""
        notes = " / ".join(
            entry.get("note", "") for entry in incident.get("timeline", []) if entry.get("note")
        )
        return self.accumulate(
            {
                "source_type": "incident",
                "source_id": incident["incident_id"],
                "title": f"사건 대응: {incident['title']}",
                "summary": f"종결까지의 조치 경위 — {notes or 'timeline 참조'}",
                "tags": ["사건대응", incident.get("severity", "medium")],
                "evidence_ids": clone(incident.get("evidence_ids", [])),
                "resolution": f"상태 전이 {len(incident.get('timeline', []))}건, 최종 {incident.get('status')}",
                "unit_id": incident.get("unit_id"),
            }
        )

    def accumulate_from_aar(self, aar: dict[str, Any]) -> dict[str, Any]:
        """훈련 AAR 생성 시 자동 훅 — 재사용 가능한 교훈으로 축적."""
        evaluation = aar.get("dynamic_evaluation") or {}
        hits = " / ".join(evaluation.get("rubric_hits", [])[:2])
        misses = " / ".join(evaluation.get("rubric_misses", [])[:2])
        return self.accumulate(
            {
                "source_type": "aar",
                "source_id": aar["aar_id"],
                "title": f"훈련 교훈: {aar.get('summary', '')[:48]}",
                "summary": f"잘한 점: {hits or '기록 없음'} · 보완: {misses or '기록 없음'}",
                "tags": ["훈련AAR", str(aar.get("grade", ""))],
                "evidence_ids": clone(evaluation.get("evidence_citations", [])),
                "resolution": f"점수 {aar.get('score')} / 등급 {aar.get('grade')}",
                "unit_id": None,
            }
        )

    def accumulate_from_inquiry(self, inquiry: dict[str, Any]) -> dict[str, Any]:
        """문의 해결 시 자동 훅 — 질문·답변 쌍을 FAQ 지식으로."""
        citations = inquiry.get("citations") or {}
        return self.accumulate(
            {
                "source_type": "inquiry",
                "source_id": inquiry["inquiry_id"],
                "title": f"FAQ: {inquiry.get('question', '')[:60]}",
                "summary": inquiry.get("answer", ""),
                "tags": ["FAQ", "헬프데스크"],
                "evidence_ids": clone(citations.get("evidence_ids", [])),
                "resolution": "담당자 검토 후 해결 처리",
                "unit_id": inquiry.get("unit_id"),
            }
        )

    # ---- 검색/조회 (A-10 화면 계약) ----

    def search(self, params: dict[str, Any]) -> dict[str, Any]:
        all_items = self.repository.list_knowledge()
        items = list(all_items)

        query = str(params.get("query") or "").strip().lower()
        if query:
            items = [item for item in items if query in self._haystack(item)]
        tags_raw = str(params.get("tags") or "").strip()
        if tags_raw:
            wanted = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]
            items = [item for item in items if any(tag in item.get("tags", []) for tag in wanted)]
        unit_id = params.get("unit_id")
        if unit_id:
            items = [item for item in items if item.get("unit_id") == unit_id]

        # 대시보드 집계는 필터와 무관하게 전체 기준 (프론트 mock과 동일)
        tag_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        unit_counts: dict[str, int] = {}
        for item in all_items:
            for tag in item.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            source_counts[item["source_type"]] = source_counts.get(item["source_type"], 0) + 1
            if item.get("unit_id"):
                unit_counts[item["unit_id"]] = unit_counts.get(item["unit_id"], 0) + 1
        top_tags = sorted(
            ({"tag": tag, "count": count} for tag, count in tag_counts.items()),
            key=lambda entry: (-entry["count"], entry["tag"]),
        )[:8]

        return {
            "items": items,
            "total": len(all_items),
            "top_tags": top_tags,
            "by_source": source_counts,
            "by_unit": unit_counts,
        }

    def get(self, knowledge_id: str) -> dict[str, Any]:
        item = self.repository.get_knowledge(knowledge_id)
        if item is None:
            raise ApiError(
                "NOT_FOUND",
                "지식을 찾을 수 없습니다.",
                status_code=404,
                details={"knowledge_id": knowledge_id},
            )
        return item

    def create_manual(self, body: dict[str, Any]) -> dict[str, Any]:
        if not body.get("title") or not body.get("summary"):
            raise ApiError("BAD_REQUEST", "title과 summary가 필요합니다.")
        sequence = self.repository.next_sequence("ops_knowledge_manual")
        return self.accumulate(
            {
                "source_type": "manual",
                "source_id": f"manual-{sequence:03d}",
                "title": body.get("title"),
                "summary": body.get("summary"),
                "tags": body.get("tags") or [],
                "evidence_ids": body.get("evidence_ids") or [],
                "resolution": body.get("resolution") or "",
                "unit_id": body.get("unit_id"),
            }
        )

    def _haystack(self, item: dict[str, Any]) -> str:
        return " ".join(
            [
                item.get("title", ""),
                item.get("summary", ""),
                item.get("resolution", ""),
                " ".join(item.get("tags", [])),
            ]
        ).lower()

    def _validate_evidence(self, evidence_ids: list[str]) -> None:
        known = known_evidence_ids()
        unknown = [evidence_id for evidence_id in evidence_ids if evidence_id not in known]
        if unknown:
            raise ApiError(
                "UNKNOWN_EVIDENCE",
                "존재하지 않는 근거 ID는 인용할 수 없습니다.",
                details={"unknown": unknown},
            )


# 자동 축적 훅 배선 — operations_service와 같은 저장소를 공유하므로
# 사건 종결/AAR 생성 즉시 같은 SQLite에 지식이 축적된다(재시작에도 유지).
knowledge_service = KnowledgeService(operations_service.repository)
operations_service.knowledge_accumulator = knowledge_service.accumulate_from_incident

from d4d.services.mission_runtime import runtime_service as _mission_runtime_service  # noqa: E402

_mission_runtime_service.aar_knowledge_accumulator = knowledge_service.accumulate_from_aar
