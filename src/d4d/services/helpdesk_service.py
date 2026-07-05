"""Helpdesk inquiry answering service (B-12).

검색이 1차다: 지식DB에서 근거를 찾고, OpenAI-compatible LLM API가 있으면 검색 컨텍스트만으로
답변을 다듬는다(RAG). 없으면 규칙/템플릿으로 항상 응답한다. 관련 지식이
없으면 답변을 생성하지 않고 "근거 부족"을 반환한다(환각 방지). 모든 답변에
knowledge/evidence citation이 붙는다.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from d4d.api.envelope import ApiError
from d4d.fixtures.operations import clone
from d4d.llm import LlmProviderPort, OpenAICompatibleLlmAdapter
from d4d.repositories import OperationsRepository
from d4d.services.knowledge_service import KnowledgeService


# 단어 하나짜리 우연 일치(=2점)로 grounded 처리하지 않는 임계값 (프론트 mock과 동일)
RETRIEVE_THRESHOLD = 3
RETRIEVE_TOP_K = 2

NO_EVIDENCE_ANSWER = (
    "근거 부족 — 지식DB에서 관련 지식을 찾지 못했습니다. 담당자 확인이 필요합니다. "
    "(환각 방지를 위해 검색 범위 밖 답변은 생성하지 않습니다)"
)
APPROVAL_SUFFIX = " 정책 반영·격리·계정 조치는 자동 실행이 아니라 승인 절차를 따릅니다."

_TOKEN_SPLIT = re.compile(r"[\s,.?!()\[\]{}:;'\"/]+")


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class HelpdeskService:
    """Inquiry intake → retrieval → (LLM API | rule) answer → resolve loop."""

    def __init__(
        self,
        repository: OperationsRepository,
        knowledge: KnowledgeService,
        llm: LlmProviderPort | None = None,
    ) -> None:
        self.repository = repository
        self.knowledge = knowledge
        self.llm = llm if llm is not None else OpenAICompatibleLlmAdapter()

    # ---- 검색 retrieval (규칙/토큰 매칭) ----

    def retrieve(self, question: str) -> list[dict[str, Any]]:
        tokens = [token for token in _TOKEN_SPLIT.split(question.lower()) if len(token) >= 2]
        scored: list[dict[str, Any]] = []
        for item in self.knowledge.repository.list_knowledge():
            haystack = " ".join(
                [item.get("title", ""), item.get("summary", ""), item.get("resolution", ""), " ".join(item.get("tags", []))]
            ).lower()
            score = 0
            for token in tokens:
                if token in haystack:
                    score += 2
                elif len(token) >= 3 and token[:-1] in haystack:  # 조사 등 어미 제거 근사
                    score += 1
            if score >= RETRIEVE_THRESHOLD:
                scored.append({"item": item, "score": score})
        scored.sort(key=lambda entry: -entry["score"])
        return scored[:RETRIEVE_TOP_K]

    # ---- 답변 생성 ----

    def _compose_answer(self, question: str, hits: list[dict[str, Any]]) -> dict[str, Any]:
        if not hits:
            return {
                "answer": NO_EVIDENCE_ANSWER,
                "engine": "rule",
                "confidence": "low",
                "citations": {"knowledge_ids": [], "evidence_ids": []},
                "fallback_used": True,
                "grounded": False,
            }

        knowledge_ids: list[str] = []
        evidence_ids: list[str] = []
        for hit in hits:
            knowledge_ids.append(hit["item"]["knowledge_id"])
            for evidence_id in hit["item"].get("evidence_ids", []):
                if evidence_id not in evidence_ids:
                    evidence_ids.append(evidence_id)

        top = hits[0]["item"]
        rule_answer = (
            f"관련 지식 \"{top['title']}\" 기준: {top['summary']}"
            + (f" 과거 처리: {top['resolution']}." if top.get("resolution") else "")
            + APPROVAL_SUFFIX
        )

        engine = "rule"
        answer = rule_answer
        if self.llm.available():
            try:
                context = "\n".join(
                    f"- [{hit['item']['knowledge_id']}] {hit['item']['title']}: {hit['item']['summary']}"
                    f" (과거 처리: {hit['item'].get('resolution') or '기록 없음'})"
                    for hit in hits
                )
                prompt = (
                    "당신은 보안 관제 조직 업무 지원 도우미입니다. 아래 지식DB 발췌 범위 안에서만 "
                    "한국어로 간결하게 답하세요. 발췌에 없는 사실·정책·수치는 절대 만들지 마세요.\n\n"
                    f"[지식DB 발췌]\n{context}\n\n[문의]\n{question}\n\n[답변]"
                )
                result = self.llm.complete(prompt, max_tokens=300, temperature=0.2)
                if result.text:
                    answer = result.text + APPROVAL_SUFFIX
                    engine = "llm"
            except Exception:  # noqa: BLE001 — LLM API 실패 시 규칙 답변으로 무중단 폴백
                answer = rule_answer
                engine = "rule"

        return {
            "answer": answer,
            "engine": engine,
            "confidence": "high" if hits[0]["score"] >= 6 else "medium",
            "citations": {"knowledge_ids": knowledge_ids, "evidence_ids": evidence_ids},
            "fallback_used": engine == "rule",
            "grounded": True,
        }

    # ---- 문의 lifecycle ----

    def create_inquiry(self, body: dict[str, Any]) -> dict[str, Any]:
        question = str(body.get("question") or body.get("message") or "").strip()
        if not question:
            raise ApiError("BAD_REQUEST", "question이 필요합니다.", details={"field": "question"})
        unit_id = body.get("unit_id")
        if unit_id and self.repository.get_unit(unit_id) is None:
            raise ApiError("BAD_REQUEST", "unit_id가 올바르지 않습니다.", details={"unit_id": unit_id})

        answered = self._compose_answer(question, self.retrieve(question))
        sequence = self.repository.next_sequence("ops_inquiry")
        inquiry = {
            "inquiry_id": f"inq-{sequence:03d}",
            "unit_id": unit_id,
            "question": question,
            "answer": answered["answer"],
            "engine": answered["engine"],
            "confidence": answered["confidence"],
            "citations": answered["citations"],
            "fallback_used": answered["fallback_used"],
            "grounded": answered["grounded"],
            "status": "answered" if answered["grounded"] else "needs_review",
            "created_at": now(),
            "linked_knowledge_ids": list(answered["citations"]["knowledge_ids"]),
        }
        self.repository.save_inquiry(inquiry)
        return clone(inquiry)

    # ---- 채팅형 conversation API ----

    def create_conversation(self, body: dict[str, Any]) -> dict[str, Any]:
        inquiry = self.create_inquiry({**body, "question": body.get("question") or body.get("message")})
        classification = self._classify(inquiry["question"])
        inquiry["conversation_id"] = f"conv-{inquiry['inquiry_id']}"
        inquiry["classification"] = classification
        inquiry["messages"] = [
            {
                "role": "user",
                "text": inquiry["question"],
                "at": inquiry["created_at"],
            },
            {
                "role": "assistant",
                "text": inquiry["answer"],
                "at": inquiry["created_at"],
                "engine": inquiry["engine"],
            },
        ]
        self.repository.save_inquiry(inquiry)
        return {
            "conversation_id": inquiry["conversation_id"],
            "conversation": self._conversation_from_inquiry(inquiry),
            "classification": classification,
        }

    def list_conversations(self, params: dict[str, Any]) -> dict[str, Any]:
        inquiries = self.list_inquiries(params).get("items", [])
        return {"items": [self._conversation_from_inquiry(inquiry) for inquiry in inquiries]}

    def classify_conversation(self, conversation_id: str) -> dict[str, Any]:
        inquiry = self._get_conversation_inquiry(conversation_id)
        classification = self._classify(inquiry["question"])
        inquiry["classification"] = classification
        self.repository.save_inquiry(inquiry)
        return classification

    def workbench(self, conversation_id: str) -> dict[str, Any]:
        inquiry = self._get_conversation_inquiry(conversation_id)
        classification = inquiry.get("classification") or self._classify(inquiry["question"])
        hits = self.retrieve(inquiry["question"])
        return {
            "conversation": self._conversation_from_inquiry(inquiry),
            "classification": classification,
            "related_knowledge": [clone(hit["item"]) for hit in hits],
            "suggested_answer": inquiry.get("answer"),
            "suggested_actions": self._suggested_actions(classification),
        }

    def draft_answer(self, conversation_id: str) -> dict[str, Any]:
        inquiry = self._get_conversation_inquiry(conversation_id)
        return {
            "conversation_id": conversation_id,
            "answer": inquiry.get("answer"),
            "engine": inquiry.get("engine"),
            "citations": inquiry.get("citations") or {},
        }

    def resolve_conversation(self, conversation_id: str) -> dict[str, Any]:
        inquiry = self._get_conversation_inquiry(conversation_id)
        result = self.resolve_inquiry(inquiry["inquiry_id"])
        result["conversation_id"] = conversation_id
        return result

    def list_inquiries(self, params: dict[str, Any]) -> dict[str, Any]:
        inquiries = self.repository.list_inquiries()
        unit_id = params.get("unit_id")
        if unit_id:
            inquiries = [inquiry for inquiry in inquiries if inquiry.get("unit_id") == unit_id]
        status = params.get("status")
        if status:
            inquiries = [inquiry for inquiry in inquiries if inquiry.get("status") == status]
        return {"items": inquiries}

    def resolve_inquiry(self, inquiry_id: str) -> dict[str, Any]:
        inquiry = self.repository.get_inquiry(inquiry_id)
        if inquiry is None:
            raise ApiError(
                "NOT_FOUND",
                "문의를 찾을 수 없습니다.",
                status_code=404,
                details={"inquiry_id": inquiry_id},
            )
        if inquiry.get("status") == "resolved":
            raise ApiError("BAD_REQUEST", "이미 해결 처리된 문의입니다.", details={"inquiry_id": inquiry_id})

        inquiry["status"] = "resolved"
        inquiry["resolved_at"] = now()
        self.repository.save_inquiry(inquiry)
        accumulated = self.knowledge.accumulate_from_inquiry(inquiry)
        return {
            "inquiry_id": inquiry_id,
            "conversation_id": inquiry.get("conversation_id") or f"conv-{inquiry_id}",
            "status": "resolved",
            "accumulated_knowledge_id": accumulated["knowledge_id"],
        }

    def _get_conversation_inquiry(self, conversation_id: str) -> dict[str, Any]:
        inquiry_id = conversation_id.removeprefix("conv-")
        inquiry = self.repository.get_inquiry(inquiry_id)
        if inquiry is None:
            raise ApiError(
                "NOT_FOUND",
                "상담을 찾을 수 없습니다.",
                status_code=404,
                details={"conversation_id": conversation_id},
            )
        if not inquiry.get("conversation_id"):
            inquiry["conversation_id"] = f"conv-{inquiry['inquiry_id']}"
        return inquiry

    def _conversation_from_inquiry(self, inquiry: dict[str, Any]) -> dict[str, Any]:
        classification = inquiry.get("classification") or self._classify(inquiry.get("question", ""))
        return {
            "conversation_id": inquiry.get("conversation_id") or f"conv-{inquiry['inquiry_id']}",
            "inquiry_id": inquiry["inquiry_id"],
            "unit_id": inquiry.get("unit_id"),
            "question": inquiry.get("question"),
            "answer": inquiry.get("answer"),
            "category": classification["category"],
            "priority": classification["priority"],
            "autopilot_level": classification["autopilot_level"],
            "confidence": inquiry.get("confidence"),
            "citations": inquiry.get("citations") or {},
            "status": inquiry.get("status"),
            "created_at": inquiry.get("created_at"),
            "messages": inquiry.get("messages") or [],
        }

    def _classify(self, text: str) -> dict[str, Any]:
        lowered = text.lower()
        if any(word in lowered for word in ["비밀번호", "패스워드", "password", "초기화"]):
            category = "password_reset"
            priority = "medium"
            fields = ["식별번호", "계정 일치 여부"]
            autopilot = "ai_takeover_ready"
        elif any(word in lowered for word in ["방화벽", "정책", "포트", "허용"]):
            category = "firewall_policy_request"
            priority = "high"
            fields = ["출발지", "목적지", "포트", "승인자"]
            autopilot = "operator_review"
        elif any(word in lowered for word in ["장비", "네트워크", "접속", "장애"]):
            category = "network_equipment_issue"
            priority = "high"
            fields = ["장비/서비스", "장애 시간", "영향 범위"]
            autopilot = "operator_review"
        elif any(word in lowered for word in ["침해", "악성", "신고", "감염"]):
            category = "incident_report"
            priority = "critical"
            fields = ["발견 시간", "영향 단말", "증거"]
            autopilot = "operator_review"
        else:
            category = "simple_question"
            priority = "low"
            fields = []
            autopilot = "ai_takeover_ready"
        return {
            "category": category,
            "priority": priority,
            "required_fields": fields,
            "autopilot_level": autopilot,
        }

    def _suggested_actions(self, classification: dict[str, Any]) -> list[dict[str, Any]]:
        category = classification.get("category")
        if category == "password_reset":
            return [
                {
                    "action_type": "identity_check",
                    "summary": "식별번호과 요청 계정 일치 여부를 확인한 뒤 비밀번호 초기화 승인 절차로 넘깁니다.",
                    "required_approval": True,
                    "executed": False,
                }
            ]
        if category == "firewall_policy_request":
            return [
                {
                    "action_type": "firewall_policy_review",
                    "summary": "출발지/목적지/포트와 기존 지시사항을 대조해 정책 반영 요청서를 생성합니다.",
                    "required_approval": True,
                    "executed": False,
                }
            ]
        if category == "incident_report":
            return [
                {
                    "action_type": "incident_intake",
                    "summary": "침해사고 접수 양식으로 전환하고 상위 조직 전파 범위를 제안합니다.",
                    "required_approval": True,
                    "executed": False,
                }
            ]
        return [
            {
                "action_type": "knowledge_grounded_reply",
                "summary": "관련 지식DB 근거가 있으면 AI가 답변 초안을 생성합니다.",
                "required_approval": False,
                "executed": False,
            }
        ]


from d4d.services.knowledge_service import knowledge_service  # noqa: E402
from d4d.services.operations_runtime import operations_service  # noqa: E402

helpdesk_service = HelpdeskService(operations_service.repository, knowledge_service)
