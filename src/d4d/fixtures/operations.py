"""Synthetic Operations Mode fixtures.

The labels are intentionally public-safe and generic. They model the shape of a
corps cyber-defense room managing subordinate units and many endpoint nodes
without using real unit names, real personnel, or internal system identifiers.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


OPERATION_UNITS: list[dict[str, Any]] = [
    {
        "unit_id": "unit-corps-cyber",
        "name": "상위 조직-통합보안관제센터",
        "role": "higher",
        "parent_unit_id": None,
        "level": 0,
        "sort_order": 10,
        "managed_node_count": 10420,
        "description": "현장 조직 상황 공유와 정책 반영 결과를 읽기 관점에서 확인하는 synthetic 상위 조직 제대.",
    },
    {
        "unit_id": "unit-bn-a",
        "name": "현장 보안팀-A",
        "role": "field",
        "parent_unit_id": "unit-corps-cyber",
        "level": 1,
        "sort_order": 20,
        "managed_node_count": 6120,
        "description": "NAC 고정 IP 대장과 UTM/FW 로그를 직접 확인하는 synthetic 발생 조직.",
    },
    {
        "unit_id": "unit-bn-b",
        "name": "현장 보안팀-B",
        "role": "field",
        "parent_unit_id": "unit-corps-cyber",
        "level": 1,
        "sort_order": 30,
        "managed_node_count": 4300,
        "description": "상위 조직 상태판에서 함께 집계되는 두 번째 synthetic 현장 조직.",
    },
]


OPERATION_ADAPTER_STATUS: list[dict[str, Any]] = [
    {
        "port": "notification",
        "label": "인앱 자동 알림",
        "mode": "fixture",
        "status": "available",
        "external_delivery": False,
        "capabilities": ["in_app_record_only", "unit_escalation_preview", "ack_tracking"],
        "safety": "외부 메신저·메일·SMS 발송 없음. 앱 내부 Notification 레코드만 생성.",
    },
    {
        "port": "operations_storage",
        "label": "Operations 영속 저장소",
        "mode": "sqlite",
        "status": "available",
        "external_delivery": False,
        "capabilities": ["unit_seed", "incident_ready", "knowledge_ready"],
        "safety": "synthetic/masked 운영 데이터만 저장.",
    },
]


# B-11 지식DB seed — 사건/조치/AAR/문의에서 축적된 형태의 synthetic 예시.
# 프론트 mock(app/js/api/mock.js)의 seed와 동일한 내용을 유지한다.
KNOWLEDGE_SEED: list[dict[str, Any]] = [
    {
        "source_type": "aar",
        "source_id": "aar-basic-20260703-07",
        "title": "유해 IP 차단 지시 미반영 식별 절차",
        "summary": "상위 조직 지시(directive)와 방화벽 blacklist 반영 상태를 대조해 미반영 IP를 식별하고, 반영은 승인 요청으로 상신한다.",
        "tags": ["유해IP", "directive-gap", "방화벽"],
        "evidence_ids": ["directive-2026-071", "fw-log-0182"],
        "resolution": "미반영 2건 식별 → 정책 반영 승인 요청 상신 → 상위 조직 보고 초안 작성",
        "unit_id": "unit-bn-a",
        "created_at": "2026-07-03T02:10:00Z",
    },
    {
        "source_type": "incident",
        "source_id": "inc-20260702-004",
        "title": "유출 크리덴셜 노출 시 계정 조치 분리 보고",
        "summary": "크리덴셜 노출 지표 확인 시 계정 잠금·초기화는 직접 실행하지 않고 승인 분리 원칙으로 제안만 기록한다.",
        "tags": ["크리덴셜유출", "계정조치", "승인분리"],
        "evidence_ids": ["threat-intel-203-0-113-45"],
        "resolution": "노출 계정 3건 목록화 → 계정 조치 승인 요청 → 상위 조직 보고",
        "unit_id": "unit-bn-b",
        "created_at": "2026-07-02T11:40:00Z",
    },
    {
        "source_type": "action",
        "source_id": "act-endpoint-isolation-002",
        "title": "NAC 미준수 단말 격리 검토 상신 기준",
        "summary": "posture 미준수 단말은 즉시 격리하지 않고 업무 영향 검토 후 endpoint_isolation_review 제안으로 상신한다.",
        "tags": ["NAC격리", "승인절차", "posture"],
        "evidence_ids": ["nac-node-10243", "endpoint-posture-10243"],
        "resolution": "격리 검토 제안 1건 상신 (승인 대기)",
        "unit_id": "unit-bn-b",
        "created_at": "2026-07-02T13:05:00Z",
    },
    {
        "source_type": "aar",
        "source_id": "aar-sct-20260703-02",
        "title": "의심 outbound 우선순위 판단 기준",
        "summary": "접속 장애 민원과 의심 outbound가 겹치면 outbound 근거(FW 로그·위협 IP 매칭)를 우선 확인하고 민원은 안내 초안으로 분리한다.",
        "tags": ["outbound", "우선순위", "방화벽"],
        "evidence_ids": ["fw-log-0182"],
        "resolution": "outbound 우선 분석 → 위협 IP 매칭 확인 → 민원 별도 안내",
        "unit_id": "unit-bn-a",
        "created_at": "2026-07-03T09:20:00Z",
    },
    {
        "source_type": "inquiry",
        "source_id": "inq-20260701-003",
        "title": "지시사항 반영 확인 요청 대응 (FAQ)",
        "summary": "현장 조직에서 지시 반영 여부 문의가 오면 directive 항목별 반영 상태표를 회신하고 미반영 건은 사유·예정일을 함께 안내한다.",
        "tags": ["directive-gap", "FAQ", "보고"],
        "evidence_ids": ["directive-2026-071"],
        "resolution": "반영 상태표 회신 → 미반영 사유 회신 표준화",
        "unit_id": "unit-corps-cyber",
        "created_at": "2026-07-01T15:30:00Z",
    },
]


def clone(value: Any) -> Any:
    return deepcopy(value)
