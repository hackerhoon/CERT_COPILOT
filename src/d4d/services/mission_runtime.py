"""Fixture runtime for mission sessions and AAR.

This module is deliberately small and deterministic, but not tied to in-memory
state. Session state is persisted through a repository port so local development
can use SQLite and deployment-like environments can attach PostgreSQL.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from d4d.api.envelope import ApiError
from d4d.fixtures.readiness import (
    AAR_PROFILES,
    ANALYSIS_RESULTS,
    EQUIPMENT_RESULTS,
    EVENTS,
    EVENTS_BY_SCENARIO,
    SCENARIOS,
    clone,
)
from d4d.stealthmole.dataset_loader import load_threat_landscape
from d4d.repositories import MissionSessionRepository, create_mission_repository_from_env


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


WRITE_LIKE_ACTIONS = {"policy_update_request", "endpoint_isolation_review", "report", "escalate"}


class MissionRuntimeService:
    """Fixture application service backed by a repository port."""

    def __init__(self, repository: MissionSessionRepository) -> None:
        self.repository = repository
        # B-11: AAR 생성 시 훈련 교훈을 지식DB로 축적하는 콜백.
        # knowledge_service 모듈 임포트 시 배선된다(없으면 축적 없이 동작).
        self.aar_knowledge_accumulator = None

    def start_session(self, body: dict[str, Any]) -> dict[str, Any]:
        scenario_id = body.get("scenario_id")
        if scenario_id not in SCENARIOS:
            raise ApiError(
                "SCENARIO_NOT_FOUND",
                "요청한 시나리오를 찾을 수 없습니다.",
                status_code=404,
                details={"scenario_id": scenario_id},
            )

        sequence = self.repository.next_sequence("training_session")
        session_id = f"sct-20260704-{sequence:02d}"
        session = {
            "session_id": session_id,
            "scenario_id": scenario_id,
            "status": "running",
            "started_at": now(),
            "elapsed_seconds": 0,
            "mode": body.get("mode", "fixture"),
            "visible_event_seq": 0,
            "pinned_evidence_ids": [],
            "discovered_evidence_ids": [],
            "evidence": {},
            "current_assessment": None,
            "submitted_actions": [],
            "aar": None,
        }
        self.repository.save_session(session)
        return self._public_session(session)

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self._public_session(self._session(session_id))

    def get_events(self, session_id: str, since_seq: int | None = None) -> dict[str, Any]:
        session = self._session(session_id)
        events = EVENTS_BY_SCENARIO.get(session.get("scenario_id"), EVENTS)
        items = [clone(event) for event in events if since_seq is None or event["seq"] > since_seq]
        if items:
            session["visible_event_seq"] = max(session["visible_event_seq"], max(item["seq"] for item in items))
            session["elapsed_seconds"] = max(session["elapsed_seconds"], 132)
            self.repository.save_session(session)
        return {"items": items}

    def equipment_query(self, session_id: str, body: dict[str, Any]) -> dict[str, Any]:
        session = self._session(session_id)
        port = body.get("port")
        query_type = body.get("query_type")
        result = EQUIPMENT_RESULTS.get((port, query_type))
        if result is None:
            raise ApiError(
                "ADAPTER_UNAVAILABLE",
                "요청한 fixture adapter 또는 query_type을 사용할 수 없습니다.",
                details={"port": port, "query_type": query_type},
            )

        data = clone(result)
        # ThreatIntel: enrich with the locally-built StealthMole dataset landscape
        # (masked aggregates). Falls back to the synthetic fixture when no dataset
        # has been collected on this machine.
        if port == "threat_intel":
            landscape = load_threat_landscape()
            if landscape:
                data["view_model"]["landscape"] = landscape
                data["view_model"]["sources"] = ["stealthmole:masked"]
                data["view_model"]["fallback_reason"] = None
        for evidence in data["evidence"]:
            evidence_id = evidence["evidence_id"]
            session["evidence"][evidence_id] = evidence
            if evidence_id not in session["discovered_evidence_ids"]:
                session["discovered_evidence_ids"].append(evidence_id)
        self.repository.save_session(session)
        return data

    def analyze_equipment(self, session_id: str, body: dict[str, Any]) -> dict[str, Any]:
        # 세션 유효성만 확인하고 port별 상세 분석 fixture를 반환한다.
        self._session(session_id)
        port = body.get("port")
        analysis = ANALYSIS_RESULTS.get(port)
        if analysis is None:
            raise ApiError(
                "ADAPTER_UNAVAILABLE",
                "분석할 수 없는 port입니다.",
                details={"port": port},
            )
        return clone(analysis)

    def pin_evidence(self, session_id: str, body: dict[str, Any]) -> dict[str, Any]:
        session = self._session(session_id)
        evidence_ids = list(dict.fromkeys(body.get("evidence_ids") or []))
        self._validate_evidence(session, evidence_ids)

        for evidence_id in evidence_ids:
            if evidence_id not in session["pinned_evidence_ids"]:
                session["pinned_evidence_ids"].append(evidence_id)
        self.repository.save_session(session)
        return {
            "session_id": session_id,
            "pinned_evidence_ids": clone(session["pinned_evidence_ids"]),
            "pinned_at": now(),
        }

    def save_assessment(self, session_id: str, body: dict[str, Any]) -> dict[str, Any]:
        session = self._session(session_id)
        evidence_ids = body.get("evidence_ids") or []
        self._validate_evidence(session, evidence_ids)

        if body.get("severity") == "suspected_compromise":
            evidence_set = set(evidence_ids)
            has_security = "fw-log-0182" in evidence_set and (
                "nac-node-10243" in evidence_set or "directive-2026-071" in evidence_set
            )
            if not has_security:
                raise ApiError(
                    "BAD_REQUEST",
                    "suspected_compromise 판단에는 FW 로그와 NAC/지시사항 근거가 함께 필요합니다.",
                    details={"evidence_ids": evidence_ids},
                )

        assessment = {
            "priority": body.get("priority"),
            "severity": body.get("severity"),
            "response_efforts": body.get("response_efforts") or [],
            "approval_required": bool(body.get("approval_required")),
            "confidence": body.get("confidence"),
            "rationale": body.get("rationale", ""),
            "evidence_ids": clone(evidence_ids),
        }
        session["current_assessment"] = assessment
        self.repository.save_session(session)
        return {"session_id": session_id, "assessment": clone(assessment), "saved_at": now()}

    def evaluation_preview(self, session_id: str, _body: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
        session = self._session(session_id)
        citations = self._preferred_citations(session)
        if not citations:
            status = "needs_more_evidence"
            summary = {
                "priority": "근거 부족",
                "severity": "판단 대기",
                "response_effort": "대응 미분리",
                "rubric": "장비 조회 필요",
            }
        else:
            status = "draft"
            summary = {
                "priority": "적절",
                "severity": "근거 수준 일치",
                "response_effort": "분리됨",
                "rubric": "단말 posture 보고 보강",
            }
        return (
            {
                "evaluation_id": f"eval-preview-{session_id}",
                "status": status,
                "summary_strip": summary,
                "evidence_citations": citations,
                "confidence": "medium",
            },
            [
                {
                    "code": "PARTIAL_EVALUATION",
                    "message": "훈련 중 미리보기이므로 최종 AAR 평가와 다를 수 있습니다.",
                }
            ],
        )

    def submit_actions(self, session_id: str, body: dict[str, Any]) -> dict[str, Any]:
        session = self._session(session_id)
        actions = body.get("actions") or []
        if not actions:
            raise ApiError("BAD_REQUEST", "actions가 비어 있습니다.", details={"field": "actions"})

        submitted = []
        for index, action in enumerate(actions, start=1):
            action_type = action.get("action_type")
            evidence_ids = action.get("evidence_ids") or []
            self._validate_evidence(session, evidence_ids)
            if action_type in WRITE_LIKE_ACTIONS and not action.get("approval_required"):
                raise ApiError(
                    "ACTION_REQUIRES_APPROVAL",
                    "정책 반영, 격리, 보고/상위 조직전파성 조치는 approval_required=true여야 합니다.",
                    details={"action_type": action_type},
                )
            submitted.append(
                {
                    "action_id": f"act-{session_id}-{index:03d}",
                    "action_type": action_type,
                    "title": action.get("title", ""),
                    "approval_required": bool(action.get("approval_required")),
                    "evidence_ids": clone(evidence_ids),
                }
            )

        session["submitted_actions"] = submitted
        session["status"] = "submitted"
        self.repository.save_session(session)
        return {
            "session_id": session_id,
            "status": "submitted",
            "submitted_actions": clone(submitted),
            "next_available": ["generate_aar"],
        }

    def create_aar(self, session_id: str, _body: dict[str, Any]) -> dict[str, Any]:
        session = self._session(session_id)
        scenario_id = session.get("scenario_id")
        profile = clone(AAR_PROFILES.get(scenario_id, AAR_PROFILES[list(AAR_PROFILES)[0]]))
        citations = self._preferred_citations(session)
        checked = clone(session["discovered_evidence_ids"])
        aar = {
            "aar_id": f"aar-{session_id}",
            "session_id": session_id,
            "status": "ready",
            "grade": profile["grade"],
            "score": profile["score"],
            "summary": profile["summary"],
            "timeline": profile["timeline"],
            "checked_evidence": checked,
            "missed_or_late_evidence": profile["missed_or_late_evidence"],
            "dynamic_evaluation": {
                "evaluation_id": f"eval-final-{session_id}",
                "rubric_version": f"{scenario_id}:v1",
                "overall_note": profile["summary"],
                "rubric_hits": profile["rubric_hits"],
                "rubric_misses": profile["rubric_misses"],
                "priority_feedback": profile["priority_feedback"],
                "severity_feedback": profile["severity_feedback"],
                "effort_feedback": profile["effort_feedback"],
                "evidence_citations": citations,
                "confidence": "high",
                "status": "ready",
            },
            "next_drills": profile["next_drills"],
            "operations_reuse_available": True,
        }
        session["aar"] = aar
        session["status"] = "aar_ready"
        self.repository.save_session(session)
        if self.aar_knowledge_accumulator is not None:
            self.aar_knowledge_accumulator(aar)
        return clone(aar)

    def get_aar(self, session_id: str) -> dict[str, Any]:
        session = self._session(session_id)
        if session.get("aar") is None:
            raise ApiError(
                "AAR_NOT_FOUND",
                "아직 생성된 AAR이 없습니다.",
                status_code=404,
                details={"session_id": session_id},
            )
        return clone(session["aar"])

    def create_ops_case(self, body: dict[str, Any]) -> dict[str, Any]:
        session_id = body.get("session_id")
        session = self._session(session_id)
        evidence_ids = body.get("reuse_evidence_ids") or []
        self._validate_evidence(session, evidence_ids)
        case = {
            "case_id": f"ops-case-{session_id}",
            "source_session_id": session_id,
            "status": "draft",
            "operator_note": "사용자 접속 장애, NAC posture, FW outbound, directive gap을 같은 사건으로 검토",
            "recommended_outputs": ["사용자 안내 초안", "정책 반영 요청 draft", "일일 보고 문단"],
            "evidence_ids": clone(evidence_ids),
        }
        self.repository.save_ops_case(case)
        return case

    def _session(self, session_id: str | None) -> dict[str, Any]:
        session = self.repository.get_session(session_id) if session_id else None
        if session is None:
            raise ApiError(
                "SESSION_NOT_FOUND",
                "요청한 훈련 세션을 찾을 수 없습니다.",
                status_code=404,
                details={"session_id": session_id},
            )
        return session

    def _public_session(self, session: dict[str, Any]) -> dict[str, Any]:
        return {
            "session_id": session["session_id"],
            "scenario_id": session["scenario_id"],
            "status": session["status"],
            "started_at": session["started_at"],
            "elapsed_seconds": session["elapsed_seconds"],
            "mode": session["mode"],
            "visible_event_seq": session["visible_event_seq"],
            "pinned_evidence_ids": clone(session["pinned_evidence_ids"]),
            "discovered_evidence_ids": clone(session["discovered_evidence_ids"]),
            "current_assessment": clone(session["current_assessment"]),
        }

    def _validate_evidence(self, session: dict[str, Any], evidence_ids: list[str]) -> None:
        missing = [evidence_id for evidence_id in evidence_ids if evidence_id not in session["evidence"]]
        if missing:
            raise ApiError(
                "EVIDENCE_NOT_FOUND",
                "요청한 evidence_id를 현재 세션에서 찾을 수 없습니다.",
                status_code=404,
                details={"evidence_ids": missing},
            )

    def _preferred_citations(self, session: dict[str, Any]) -> list[str]:
        preferred = ["fw-log-0182", "nac-node-10243", "directive-2026-071"]
        citations = [evidence_id for evidence_id in preferred if evidence_id in session["evidence"]]
        if citations:
            return citations
        return clone(session["discovered_evidence_ids"][:3])


runtime_service = MissionRuntimeService(create_mission_repository_from_env())
