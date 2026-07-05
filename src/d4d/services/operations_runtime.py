"""Operations Mode runtime service.

B-08 only exposes the foundation: synthetic unit hierarchy, storage adapter
status, ancestor calculation, and escalation depth. Later B-09~B-12 services
can build incidents, notifications, knowledge, and inquiries on this base.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from d4d.api.envelope import ApiError
from d4d.fixtures.readiness import EQUIPMENT_RESULTS
from d4d.fixtures.operations import OPERATION_ADAPTER_STATUS, OPERATION_UNITS, clone
from d4d.repositories import OperationsRepository, create_operations_repository_from_env


VALID_SEVERITIES = {"low", "medium", "high", "critical"}
STATUS_TRANSITIONS = {
    "received": ["in_progress", "needs_approval", "escalated"],
    "in_progress": ["contained", "needs_approval", "escalated"],
    "needs_approval": ["in_progress", "escalated"],
    "contained": ["closed", "needs_approval"],
    "escalated": ["in_progress", "contained", "closed"],
    "closed": [],
}
ESCALATION_DEPTH_BY_SEVERITY = {
    "low": 1,
    "medium": 1,
    "high": 2,
    "critical": 99,
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def known_evidence_ids() -> set[str]:
    evidence_ids: set[str] = set()
    for result in EQUIPMENT_RESULTS.values():
        for evidence in result.get("evidence", []):
            evidence_id = evidence.get("evidence_id")
            if evidence_id:
                evidence_ids.add(evidence_id)
    return evidence_ids


class OperationsRuntimeService:
    """Application service for Operations Mode foundation endpoints."""

    def __init__(self, repository: OperationsRepository) -> None:
        self.repository = repository
        self.repository.seed_units(OPERATION_UNITS)
        # B-11: 사건 종결 시 지식 축적 콜백. knowledge_service 모듈이 임포트될 때
        # 배선된다(콜백이 없으면 축적 없이 동작 — 단위 테스트용 독립 인스턴스 포함).
        self.knowledge_accumulator = None

    def list_units(self) -> dict[str, Any]:
        units = self.repository.list_units()
        by_parent: dict[str | None, list[dict[str, Any]]] = {}
        for unit in units:
            by_parent.setdefault(unit.get("parent_unit_id"), []).append(unit)

        items = []
        for unit in units:
            unit_id = unit["unit_id"]
            item = clone(unit)
            item["ancestor_unit_ids"] = self.ancestors(unit_id)
            item["child_unit_ids"] = [child["unit_id"] for child in by_parent.get(unit_id, [])]
            items.append(item)

        root_unit_ids = [unit["unit_id"] for unit in by_parent.get(None, [])]
        field_units = [unit for unit in units if unit.get("role") == "field"]
        higher_units = [unit for unit in units if unit.get("role") == "higher"]
        node_count_basis = field_units or units
        return {
            "items": items,
            "root_unit_ids": root_unit_ids,
            "default_viewer_unit_id": field_units[0]["unit_id"] if field_units else (units[0]["unit_id"] if units else None),
            "higher_unit_id": higher_units[0]["unit_id"] if higher_units else None,
            "managed_node_count_total": sum(int(unit.get("managed_node_count", 0)) for unit in node_count_basis),
            "escalation_policy": {
                "low": "해당 조직 + 직속 상위 조직",
                "medium": "해당 조직 + 직속 상위 조직",
                "high": "해당 조직 + 상위 조직 체인",
                "critical": "해당 조직 + 전 상위 조직 체인",
            },
        }

    def adapter_status(self) -> dict[str, Any]:
        items = clone(OPERATION_ADAPTER_STATUS)
        for item in items:
            if item["port"] == "operations_storage":
                item["mode"] = self.repository.backend_name
        return {
            "storage_backend": self.repository.backend_name,
            "items": items,
            "safety": ["synthetic_units", "in_app_notification_only", "approval_gated_write_like_actions"],
        }

    def create_incident(self, body: dict[str, Any]) -> dict[str, Any]:
        unit_id = body.get("unit_id")
        title = str(body.get("title") or "").strip()
        severity = str(body.get("severity") or "").strip()
        note = str(body.get("note") or "").strip()
        evidence_ids = list(dict.fromkeys(body.get("evidence_ids") or []))

        if not title:
            raise ApiError("BAD_REQUEST", "title이 필요합니다.", details={"field": "title"})
        if severity not in VALID_SEVERITIES:
            raise ApiError(
                "BAD_REQUEST",
                "severity는 low/medium/high/critical 중 하나여야 합니다.",
                details={"field": "severity", "severity": severity or None},
            )
        if not unit_id or self.repository.get_unit(unit_id) is None:
            raise ApiError(
                "BAD_REQUEST",
                "unit_id가 올바르지 않습니다.",
                details={"unit_id": unit_id or None},
            )
        self._validate_public_evidence(evidence_ids)

        sequence = self.repository.next_sequence("ops_incident")
        incident_id = f"inc-20260704-{sequence:03d}"
        created_at = now()
        targets = self.notification_targets(unit_id, severity, include_self=True)
        notifications = [
            self._notification(
                incident_id=incident_id,
                to_unit_id=target_unit_id,
                kind="incident_opened",
                severity=severity,
                title=title,
            )
            for target_unit_id in targets
        ]
        incident = {
            "incident_id": incident_id,
            "unit_id": unit_id,
            "title": title,
            "severity": severity,
            "status": "received",
            "created_at": created_at,
            "evidence_ids": evidence_ids,
            "timeline": [
                {
                    "at": created_at,
                    "from": None,
                    "to": "received",
                    "actor_unit": unit_id,
                    "note": note or "상황 접수",
                    "evidence_ids": clone(evidence_ids),
                }
            ],
            "notified_unit_ids": [notification["to_unit_id"] for notification in notifications],
        }
        self.repository.save_incident(incident)
        self.repository.save_notifications(notifications)
        return self._incident_dto(incident, notifications=notifications)

    def list_incidents(self, params: dict[str, Any]) -> dict[str, Any]:
        incidents = self.repository.list_incidents()
        unit_id = params.get("unit_id")
        if unit_id:
            visible_unit_ids = {unit_id, *self.descendants(unit_id)}
            incidents = [incident for incident in incidents if incident.get("unit_id") in visible_unit_ids]
        status = params.get("status")
        if status:
            incidents = [incident for incident in incidents if incident.get("status") == status]
        return {"items": [clone(incident) for incident in incidents]}

    def get_incident(self, incident_id: str) -> dict[str, Any]:
        incident = self.repository.get_incident(incident_id)
        if incident is None:
            raise ApiError(
                "NOT_FOUND",
                "사건을 찾을 수 없습니다.",
                status_code=404,
                details={"incident_id": incident_id},
            )
        return self._incident_dto(incident)

    def get_timeline(self, incident_id: str) -> dict[str, Any]:
        incident = self._require_incident(incident_id)
        return {"incident_id": incident_id, "items": clone(incident.get("timeline", []))}

    def transition_incident_status(self, incident_id: str, body: dict[str, Any]) -> dict[str, Any]:
        incident = self._require_incident(incident_id)
        actor_unit_id = body.get("actor_unit_id")
        to_status = str(body.get("to_status") or "").strip()
        note = str(body.get("note") or "").strip()
        evidence_ids = list(dict.fromkeys(body.get("evidence_ids") or []))

        if actor_unit_id != incident["unit_id"]:
            raise ApiError(
                "FORBIDDEN",
                "상태 전이는 해당(발생) 조직만 수행할 수 있습니다. 상위 조직 조직는 읽기 전용입니다.",
                status_code=403,
                details={"incident_unit_id": incident["unit_id"], "actor_unit_id": actor_unit_id or None},
            )
        allowed = STATUS_TRANSITIONS.get(incident["status"], [])
        if to_status not in allowed:
            raise ApiError(
                "INVALID_TRANSITION",
                "허용되지 않는 상태 전이입니다.",
                details={"from": incident["status"], "to": to_status or None, "allowed": clone(allowed)},
            )
        self._validate_public_evidence(evidence_ids)

        timeline_entry = {
            "at": now(),
            "from": incident["status"],
            "to": to_status,
            "actor_unit": incident["unit_id"],
            "note": note,
            "evidence_ids": clone(evidence_ids),
        }
        incident["status"] = to_status
        incident.setdefault("timeline", []).append(timeline_entry)
        self.repository.save_incident(incident)

        notifications = [
            self._notification(
                incident_id=incident_id,
                to_unit_id=target_unit_id,
                kind="status_changed",
                severity=incident["severity"],
                title=incident["title"],
            )
            for target_unit_id in self.notification_targets(incident["unit_id"], incident["severity"], include_self=False)
        ]
        self.repository.save_notifications(notifications)

        # B-11: 종결 시 자동 지식 축적 — 담당자와 무관하게 비휘발(설계 §2.2)
        accumulated = None
        if to_status == "closed" and self.knowledge_accumulator is not None:
            accumulated = self.knowledge_accumulator(incident)

        return {
            "incident_id": incident_id,
            "status": incident["status"],
            "approval_required": to_status == "needs_approval",
            "executed": False,
            "timeline_entry": timeline_entry,
            "notifications": clone(notifications),
            "allowed_transitions": clone(STATUS_TRANSITIONS.get(incident["status"], [])),
            "accumulated_knowledge_id": accumulated["knowledge_id"] if accumulated else None,
        }

    def status_board(self, params: dict[str, Any]) -> dict[str, Any]:
        unit_id = params.get("unit_id")
        if not unit_id:
            raise ApiError("BAD_REQUEST", "unit_id가 필요합니다.", details={"field": "unit_id"})
        self._require_unit(unit_id)
        subordinate_units = self.descendants(unit_id)
        visible_unit_ids = {unit_id, *subordinate_units}
        incidents = [
            incident
            for incident in self.repository.list_incidents()
            if incident.get("unit_id") in visible_unit_ids
        ]
        return {
            "viewer_unit_id": unit_id,
            "subordinate_units": subordinate_units,
            "incidents": [
                {
                    "incident_id": incident["incident_id"],
                    "unit_id": incident["unit_id"],
                    "title": incident["title"],
                    "status": incident["status"],
                    "severity": incident["severity"],
                    "elapsed_seconds": 600 * (index + 1),
                    "last_transition": self._last_transition_label(incident),
                }
                for index, incident in enumerate(incidents)
            ],
        }

    def list_notifications(self, params: dict[str, Any]) -> dict[str, Any]:
        notifications = self.repository.list_notifications()
        unit_id = params.get("unit_id")
        if unit_id:
            notifications = [item for item in notifications if item.get("to_unit_id") == unit_id]
        notifications = sorted(notifications, key=lambda item: str(item.get("created_at", "")), reverse=True)
        notifications = sorted(notifications, key=lambda item: bool(item.get("read")))
        unread_count = len([item for item in notifications if not item.get("read")])
        return {"items": [clone(item) for item in notifications], "unread_count": unread_count}

    def ack_notification(self, notification_id: str) -> dict[str, Any]:
        notification = self.repository.get_notification(notification_id)
        if notification is None:
            raise ApiError(
                "NOT_FOUND",
                "알림을 찾을 수 없습니다.",
                status_code=404,
                details={"notification_id": notification_id},
            )
        notification["read"] = True
        notification["read_at"] = now()
        self.repository.save_notification(notification)
        return {"notification_id": notification_id, "read": True}

    def notification_targets(self, unit_id: str, severity: str, *, include_self: bool) -> list[str]:
        depth = self.escalation_depth(severity)
        targets = [unit_id] if include_self else []
        targets.extend(self.ancestors(unit_id)[:depth])
        return list(dict.fromkeys(targets))

    def descendants(self, unit_id: str) -> list[str]:
        self._require_unit(unit_id)
        units = self.repository.list_units()
        children_by_parent: dict[str, list[str]] = {}
        for unit in units:
            parent_unit_id = unit.get("parent_unit_id")
            if parent_unit_id:
                children_by_parent.setdefault(parent_unit_id, []).append(unit["unit_id"])

        found: list[str] = []
        stack = list(children_by_parent.get(unit_id, []))
        while stack:
            child_id = stack.pop(0)
            found.append(child_id)
            stack.extend(children_by_parent.get(child_id, []))
        return found

    def ancestors(self, unit_id: str) -> list[str]:
        unit = self._require_unit(unit_id)

        ancestors: list[str] = []
        seen = {unit_id}
        parent_unit_id = unit.get("parent_unit_id")
        while parent_unit_id:
            if parent_unit_id in seen:
                raise ApiError(
                    "UNIT_HIERARCHY_CYCLE",
                    "조직 계층에 순환 참조가 있습니다.",
                    details={"unit_id": unit_id, "parent_unit_id": parent_unit_id},
                )
            parent = self.repository.get_unit(parent_unit_id)
            if parent is None:
                raise ApiError(
                    "UNIT_PARENT_NOT_FOUND",
                    "조직 계층의 상위 조직 조직를 찾을 수 없습니다.",
                    details={"unit_id": unit_id, "parent_unit_id": parent_unit_id},
                )
            ancestors.append(parent_unit_id)
            seen.add(parent_unit_id)
            parent_unit_id = parent.get("parent_unit_id")
        return ancestors

    def escalation_depth(self, severity: str) -> int:
        return ESCALATION_DEPTH_BY_SEVERITY.get(severity, 1)

    def _require_unit(self, unit_id: str) -> dict[str, Any]:
        unit = self.repository.get_unit(unit_id)
        if unit is None:
            raise ApiError(
                "UNIT_NOT_FOUND",
                "요청한 synthetic 조직를 찾을 수 없습니다.",
                status_code=404,
                details={"unit_id": unit_id},
            )
        return unit

    def _require_incident(self, incident_id: str) -> dict[str, Any]:
        incident = self.repository.get_incident(incident_id)
        if incident is None:
            raise ApiError(
                "NOT_FOUND",
                "사건을 찾을 수 없습니다.",
                status_code=404,
                details={"incident_id": incident_id},
            )
        return incident

    def _validate_public_evidence(self, evidence_ids: list[str]) -> None:
        known = known_evidence_ids()
        unknown = [evidence_id for evidence_id in evidence_ids if evidence_id not in known]
        if unknown:
            raise ApiError(
                "UNKNOWN_EVIDENCE",
                "존재하지 않는 근거 ID는 인용할 수 없습니다.",
                details={"unknown": unknown},
            )

    def _notification(
        self,
        *,
        incident_id: str,
        to_unit_id: str,
        kind: str,
        severity: str,
        title: str,
    ) -> dict[str, Any]:
        sequence = self.repository.next_sequence("ops_notification")
        return {
            "notification_id": f"ntf-{sequence:03d}",
            "incident_id": incident_id,
            "to_unit_id": to_unit_id,
            "kind": kind,
            "severity": severity,
            "title": title,
            "created_at": now(),
            "read": False,
        }

    def _incident_dto(self, incident: dict[str, Any], *, notifications: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        dto = clone(incident)
        dto["allowed_transitions"] = clone(STATUS_TRANSITIONS.get(incident.get("status"), []))
        if notifications is None:
            notifications = [
                notification
                for notification in self.repository.list_notifications()
                if notification.get("incident_id") == incident["incident_id"]
            ]
        dto["notifications"] = clone(notifications)
        return dto

    def _last_transition_label(self, incident: dict[str, Any]) -> str:
        timeline = incident.get("timeline", [])
        if not timeline:
            return "접수"
        last = timeline[-1]
        if last.get("from"):
            return f"{last['from']}→{last['to']}"
        return "접수"


operations_service = OperationsRuntimeService(create_operations_repository_from_env())
