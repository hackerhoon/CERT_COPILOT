"""Cyber defense dashboard read model service."""

from __future__ import annotations

from typing import Any

from d4d.fixtures.operations import clone
from d4d.services.knowledge_service import KnowledgeService
from d4d.services.operations_runtime import OperationsRuntimeService, operations_service


class DashboardService:
    """Compose dashboard data from existing operations, knowledge, and adapter state."""

    def __init__(self, operations: OperationsRuntimeService, knowledge: KnowledgeService) -> None:
        self.operations = operations
        self.knowledge = knowledge

    def overview(self, params: dict[str, Any]) -> dict[str, Any]:
        unit_id = params.get("unit_id")
        incidents = self.operations.list_incidents({"unit_id": unit_id}).get("items", [])
        notifications = self.operations.list_notifications({"unit_id": unit_id}).get("items", [])
        knowledge = self.knowledge.search({"unit_id": unit_id}).get("items", [])
        equipment = self.equipment().get("items", [])
        threats = self.threats().get("items", [])

        open_incidents = [
            item for item in incidents if item.get("status") not in {"closed", "resolved"}
        ]
        equipment_warnings = sum(int(item.get("warning_count", 0)) for item in equipment)
        unacked = len([item for item in notifications if not item.get("read")])
        posture_score = max(0, 100 - (len(open_incidents) * 6) - (equipment_warnings * 4) - (unacked * 2))

        tiles = []
        for incident in open_incidents[:3]:
            tiles.append(
                {
                    "title": incident.get("title", "미확인 상황"),
                    "severity": incident.get("severity", "medium"),
                    "source_type": "incident",
                    "metric": len(incident.get("timeline", [])),
                    "citations": clone(incident.get("evidence_ids", [])),
                    "route": f"#/dashboard/propagation/{incident.get('incident_id')}",
                }
            )
        for item in threats[:2]:
            tiles.append(
                {
                    "title": item["title"],
                    "severity": item["severity"],
                    "source_type": "threat",
                    "metric": item["score"],
                    "citations": item["evidence_ids"],
                    "route": "#/dashboard/threats",
                }
            )

        return {
            "summary": {
                "posture_score": posture_score,
                "unacked_propagations": unacked,
                "open_incidents": len(open_incidents),
                "equipment_warnings": equipment_warnings,
                "knowledge_items": len(knowledge),
            },
            "tiles": tiles,
            "equipment": equipment,
            "threats": threats,
            "calendar": self.calendar().get("items", []),
        }

    def equipment(self) -> dict[str, Any]:
        adapters = self.operations.adapter_status().get("items", [])
        items = []
        for index, adapter in enumerate(adapters):
            warning_count = 0 if adapter.get("status") == "available" else 1
            items.append(
                {
                    "equipment_id": adapter.get("port"),
                    "label": adapter.get("label"),
                    "status": "normal" if warning_count == 0 else "warning",
                    "source_mode": adapter.get("mode"),
                    "warning_count": warning_count,
                    "last_seen_at": "2026-07-05T09:00:00Z",
                    "evidence_ids": ["directive-2026-071"] if index == 0 else [],
                }
            )
        items.extend(
            [
                {
                    "equipment_id": "utm-fw",
                    "label": "UTM/FW 로그 수집",
                    "status": "warning",
                    "source_mode": "synthetic_adapter",
                    "warning_count": 1,
                    "last_seen_at": "2026-07-05T09:12:00Z",
                    "evidence_ids": ["fw-log-0182"],
                },
                {
                    "equipment_id": "nac",
                    "label": "NAC 단말 통제",
                    "status": "normal",
                    "source_mode": "synthetic_adapter",
                    "warning_count": 0,
                    "last_seen_at": "2026-07-05T09:15:00Z",
                    "evidence_ids": ["nac-node-10243"],
                },
            ]
        )
        return {"items": items}

    def threats(self) -> dict[str, Any]:
        return {
            "items": [
                {
                    "threat_id": "thr-stealthmole-001",
                    "title": "StealthMole 유출 크리덴셜 관련 지표 증가",
                    "summary": "masked credential exposure 지표가 계정조치 FAQ와 연결됩니다.",
                    "severity": "high",
                    "score": 82,
                    "tags": ["StealthMole", "credential", "account"],
                    "evidence_ids": ["threat-intel-203-0-113-45"],
                },
                {
                    "threat_id": "thr-fw-outbound-002",
                    "title": "의심 outbound와 유해 IP 지시 미반영 교차",
                    "summary": "방화벽 로그와 상위 조직 지시 반영 상태를 함께 확인해야 합니다.",
                    "severity": "medium",
                    "score": 67,
                    "tags": ["outbound", "firewall", "directive-gap"],
                    "evidence_ids": ["fw-log-0182", "directive-2026-071"],
                },
            ]
        }

    def posture(self) -> dict[str, Any]:
        return {"score": self.overview({}).get("summary", {}).get("posture_score", 0), "status": "watch"}

    def calendar(self) -> dict[str, Any]:
        return {
            "items": [
                {"task_id": "cal-001", "title": "상위 조직 지시 반영 현황 재확인", "due_at": "오늘 10:00", "status": "진행"},
                {"task_id": "cal-002", "title": "야간 위협 동향 브리핑 초안", "due_at": "오늘 15:30", "status": "대기"},
                {"task_id": "cal-003", "title": "헬프데스크 상담 지식DB 후보 검토", "due_at": "오늘 17:00", "status": "대기"},
            ]
        }

    def propagation(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.operations.list_notifications({"unit_id": params.get("unit_id")})


from d4d.services.knowledge_service import knowledge_service  # noqa: E402

dashboard_service = DashboardService(operations_service, knowledge_service)
