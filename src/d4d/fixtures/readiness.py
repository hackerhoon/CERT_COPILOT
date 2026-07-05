"""Main T5 cyber-defense readiness fixture catalog.

The fixture is intentionally synthetic. It mirrors the team's cyber-defense-room
workflow context without exposing real unit data, real service members, raw
credentials, or real internal system outputs.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


MAIN_SCENARIO_ID = "scen-main-outbound-001"
BASIC_SCENARIO_ID = "scen-harmful-ip-002"
ADVANCED_SCENARIO_ID = "scen-cred-ransom-003"

AVAILABLE_EQUIPMENT = [
    {"port": "ticket", "label": "민원/전화 기록"},
    {"port": "utm_firewall", "label": "TrusGuard형 UTM/FW"},
    {"port": "nac", "label": "Genian NAC형 NAC"},
    {"port": "directive", "label": "지시사항함"},
    {"port": "threat_intel", "label": "ThreatIntel"},
]

SCENARIOS: dict[str, dict[str, Any]] = {
    MAIN_SCENARIO_ID: {
        "scenario_id": MAIN_SCENARIO_ID,
        "title": "업무망 접속 장애와 의심 outbound",
        "difficulty": "intermediate",
        "estimated_minutes": 12,
        "training_goals": ["로그 확인", "IP 귀속", "정책 반영 누락 식별", "보고"],
        "available_equipment": [item["port"] for item in AVAILABLE_EQUIPMENT],
        "tags": ["T5", "cyber-defense-room", "priority-triage"],
        "briefing": {
            "role": "통합보안관제센터 운영 담당자",
            "situation": "업무용 홈페이지 접속 장애 민원이 접수되었고, 같은 시간대 의심 outbound 로그가 관측되었습니다.",
            "objective": "원인과 위험도를 판단하고 필요한 조치와 보고 초안을 제출하십시오.",
            "constraints": ["synthetic data only", "defensive workflow only", "write-like action은 승인 요청까지만"],
        },
        "rubric_summary": [
            "동시다발 이벤트 우선순위",
            "일시 장애와 의심 침해 구분",
            "빠른 조치와 승인 필요 조치 분리",
            "근거 ID 기반 보고",
        ],
        "hidden_ground_truth": {
            "do_not_expose": True,
            "notes": [
                "Directive-2026-071 일부 대상이 mock blacklist에 미반영되어 있다.",
                "nac-node-10243은 정책 미준수로 access limited 상태다.",
                "외부 indicator는 StealthMole/OSINT enrichment용 synthetic pivot이다.",
            ],
        },
    },
    BASIC_SCENARIO_ID: {
        "scenario_id": BASIC_SCENARIO_ID,
        "title": "유해 IP 차단 지시 반영 점검",
        "difficulty": "basic",
        "estimated_minutes": 8,
        "training_goals": ["지시사항 확인", "blacklist 반영 대조", "미반영 식별", "보고"],
        "available_equipment": ["ticket", "directive", "utm_firewall", "threat_intel"],
        "tags": ["T5", "directive-gap", "onboarding"],
        "briefing": {
            "role": "통합보안관제센터 운영 담당자",
            "situation": "상위 조직제대에서 유해 IP 차단 지시(Directive-2026-071)가 하달되었습니다. 방화벽 blacklist 반영 상태를 점검하십시오.",
            "objective": "지시 대상과 방화벽 반영 상태를 대조해 미반영 항목을 찾고, 반영 요청과 보고 초안을 제출하십시오.",
            "constraints": ["synthetic data only", "defensive workflow only", "정책 반영은 승인 요청까지만"],
        },
        "rubric_summary": [
            "지시사항 대상 전수 확인",
            "방화벽 blacklist와 지시 대조",
            "미반영 항목 정확 식별",
            "반영 요청·보고 분리",
        ],
        "hidden_ground_truth": {
            "do_not_expose": True,
            "notes": ["Directive-2026-071 대상 28건 중 4건이 mock blacklist에 미반영되어 있다."],
        },
    },
    ADVANCED_SCENARIO_ID: {
        "scenario_id": ADVANCED_SCENARIO_ID,
        "title": "유출 크리덴셜·활성 랜섬웨어 기반 복합 침해 대응",
        "difficulty": "advanced",
        "estimated_minutes": 16,
        "training_goals": ["크리덴셜 노출 평가", "침해 정황 상관분석", "계정 조치 승인 분리", "위협 헌팅", "상위 조직 보고"],
        "available_equipment": [item["port"] for item in AVAILABLE_EQUIPMENT],
        "tags": ["T5", "threat-hunting", "credential-exposure", "ransomware"],
        "briefing": {
            "role": "통합보안관제센터 통합관제 담당",
            "situation": (
                "StealthMole 외부 인텔에서 우리 관리 도메인 관련 유출 크리덴셜 다수와, 활성 랜섬웨어 그룹의 "
                "동종 섹터 노출이 확인되었습니다. 같은 시간대 내부 단말에서 의심 outbound가 관측됩니다."
            ),
            "objective": (
                "유출 크리덴셜 노출 범위를 산정하고, 내부 관측(단말·outbound)과 외부 인텔을 상관분석해 "
                "침해 정황 여부를 판단하십시오. 계정·격리성 조치는 승인 요청으로 분리하고 상위 조직 보고 초안을 제출하십시오."
            ),
            "constraints": [
                "synthetic/masked data only",
                "raw credential 노출 금지 (마스킹 값만)",
                "계정/격리 조치는 승인 요청까지만",
            ],
        },
        "rubric_summary": [
            "유출 크리덴셜 노출 범위·심각도 산정",
            "내부 관측과 외부 인텔 상관분석",
            "활성 랜섬웨어 노출면 점검(위협 헌팅)",
            "계정·격리 조치를 승인 요청으로 분리",
            "다중 근거 인용 상위 조직 보고",
        ],
        "hidden_ground_truth": {
            "do_not_expose": True,
            "notes": [
                "유출 크리덴셜은 외부 인텔 기반 노출 정황이며 내부 계정 침해가 확정된 것은 아니다.",
                "outbound·NAC posture·크리덴셜 노출을 함께 봐야 우선순위가 선다.",
                "랜섬웨어 노출은 섹터 기반 헌팅 근거이지 직접 피해 확정이 아니다.",
            ],
        },
    },
}

HOME_FIXTURE: dict[str, Any] = {
    "role_label": "통합보안관제센터 운영 담당자",
    "recommended_scenario": {
        "scenario_id": MAIN_SCENARIO_ID,
        "title": "업무망 접속 장애와 의심 outbound",
        "difficulty": "intermediate",
        "estimated_minutes": 12,
        "training_goals": ["로그 확인", "IP 귀속", "정책 반영 누락 식별", "보고"],
    },
    "skill_summary": [
        {"name": "로그 분석", "score": 78},
        {"name": "NAC 운용", "score": 72},
        {"name": "정책 판단", "score": 68},
        {"name": "보고 작성", "score": 81},
    ],
    "recent_aars": [
        {
            "session_id": "sct-prev-001",
            "scenario_title": "유해 IP 미반영",
            "grade": "B",
            "key_feedback": "지시사항 확인 지연",
        },
        {
            "session_id": "sct-prev-002",
            "scenario_title": "피싱 신고 대응",
            "grade": "A",
            "key_feedback": "보고 품질 우수",
        },
    ],
}

ADAPTER_STATUS: list[dict[str, Any]] = [
    {"port": "ticket", "mode": "fixture", "status": "available", "fallback_reason": None},
    {"port": "utm_firewall", "mode": "fixture", "status": "available", "fallback_reason": None},
    {"port": "nac", "mode": "fixture", "status": "available", "fallback_reason": None},
    {"port": "directive", "mode": "fixture", "status": "available", "fallback_reason": None},
    {"port": "threat_intel", "mode": "fixture", "status": "available", "fallback_reason": "live adapter not configured"},
]

EVENTS: list[dict[str, Any]] = [
    {
        "seq": 1,
        "event_id": "evt-ticket-001",
        "timestamp": "2026-07-04T05:34:20Z",
        "event_type": "service_failure",
        "source_port": "ticket",
        "title": "서비스 장애",
        "visible_text": "업무용 홈페이지 접속 장애 민원",
        "severity_hint": "temporary_failure",
    },
    {
        "seq": 2,
        "event_id": "evt-fw-0182",
        "timestamp": "2026-07-04T05:35:00Z",
        "event_type": "suspicious_outbound",
        "source_port": "utm_firewall",
        "title": "의심 outbound",
        "visible_text": "Log ID: FW-20260704-0182",
        "severity_hint": "suspected_compromise",
    },
    {
        "seq": 3,
        "event_id": "evt-directive-071",
        "timestamp": "2026-07-04T05:35:20Z",
        "event_type": "directive_gap",
        "source_port": "directive",
        "title": "지시사항 gap",
        "visible_text": "Directive-2026-071 반영 마감 임박",
        "severity_hint": "policy_restriction",
    },
    {
        "seq": 4,
        "event_id": "evt-nac-10243",
        "timestamp": "2026-07-04T05:35:40Z",
        "event_type": "endpoint_posture",
        "source_port": "nac",
        "title": "단말 posture",
        "visible_text": "nac-node-10243 상태 확인 필요",
        "severity_hint": "policy_restriction",
    },
]

# 초급: 지시사항 반영 점검 — 이벤트가 적고 흐름이 단순하다.
BASIC_EVENTS: list[dict[str, Any]] = [
    {
        "seq": 1,
        "event_id": "evt-directive-071-basic",
        "timestamp": "2026-07-04T05:34:00Z",
        "event_type": "directive_gap",
        "source_port": "directive",
        "title": "유해 IP 차단 지시 하달",
        "visible_text": "Directive-2026-071 · 대상 28건 · 반영 마감 임박",
        "severity_hint": "policy_restriction",
    },
    {
        "seq": 2,
        "event_id": "evt-fw-blacklist-basic",
        "timestamp": "2026-07-04T05:34:40Z",
        "event_type": "policy_gap",
        "source_port": "utm_firewall",
        "title": "방화벽 반영 확인 필요",
        "visible_text": "일부 network scope blacklist 반영 상태 미확인",
        "severity_hint": "policy_restriction",
    },
]

# 숙련: 유출 크리덴셜·랜섬웨어·내부 관측이 동시에 들어오는 복합 상황 — 이벤트가 많다.
ADVANCED_EVENTS: list[dict[str, Any]] = [
    {
        "seq": 1,
        "event_id": "evt-ticket-acct",
        "timestamp": "2026-07-04T05:33:40Z",
        "event_type": "service_failure",
        "source_port": "ticket",
        "title": "계정 이상 민원",
        "visible_text": "다수 사용자 계정 잠금·재인증 요구 민원 접수",
        "severity_hint": "policy_restriction",
    },
    {
        "seq": 2,
        "event_id": "evt-ti-cred",
        "timestamp": "2026-07-04T05:34:10Z",
        "event_type": "threat_intel",
        "source_port": "threat_intel",
        "title": "유출 크리덴셜 노출",
        "visible_text": "외부 인텔에서 관리 도메인 관련 유출 크리덴셜 다수 관측",
        "severity_hint": "suspected_compromise",
    },
    {
        "seq": 3,
        "event_id": "evt-fw-0182-adv",
        "timestamp": "2026-07-04T05:34:50Z",
        "event_type": "suspicious_outbound",
        "source_port": "utm_firewall",
        "title": "의심 outbound",
        "visible_text": "Log ID: FW-20260704-0182 · 반복 outbound",
        "severity_hint": "suspected_compromise",
    },
    {
        "seq": 4,
        "event_id": "evt-ti-ransom",
        "timestamp": "2026-07-04T05:35:20Z",
        "event_type": "threat_intel",
        "source_port": "threat_intel",
        "title": "활성 랜섬웨어 노출",
        "visible_text": "동종 섹터 대상 활성 랜섬웨어 그룹 노출 관측(헌팅 근거)",
        "severity_hint": "policy_restriction",
    },
    {
        "seq": 5,
        "event_id": "evt-nac-10243-adv",
        "timestamp": "2026-07-04T05:35:50Z",
        "event_type": "endpoint_posture",
        "source_port": "nac",
        "title": "단말 posture",
        "visible_text": "nac-node-10243 access limited · 상태 확인 필요",
        "severity_hint": "policy_restriction",
    },
    {
        "seq": 6,
        "event_id": "evt-directive-071-adv",
        "timestamp": "2026-07-04T05:36:20Z",
        "event_type": "directive_gap",
        "source_port": "directive",
        "title": "지시사항 gap",
        "visible_text": "Directive-2026-071 일부 미반영 · 대조 필요",
        "severity_hint": "policy_restriction",
    },
]

# 세션 런타임이 시나리오별로 이벤트 피드를 고른다. 없으면 main으로 폴백.
EVENTS_BY_SCENARIO: dict[str, list[dict[str, Any]]] = {
    MAIN_SCENARIO_ID: EVENTS,
    BASIC_SCENARIO_ID: BASIC_EVENTS,
    ADVANCED_SCENARIO_ID: ADVANCED_EVENTS,
}

EQUIPMENT_RESULTS: dict[tuple[str, str], dict[str, Any]] = {
    (
        "utm_firewall",
        "firewall_log_search",
    ): {
        "port": "utm_firewall",
        "query_type": "firewall_log_search",
        "evidence": [
            {
                "evidence_id": "fw-log-0182",
                "source_port": "utm_firewall",
                "source_id": "FW-20260704-0182",
                "source_mode": "fixture",
                "claim": "10.23.14.52에서 203.0.113.45:443으로 허용된 outbound 로그가 관측됨",
                "confidence": "high",
                "observed_at": "2026-07-04T05:27:31Z",
                "related_entity_ids": ["ip-10-23-14-52", "indicator-203-0-113-45"],
                "caveat": "내부 단말 귀속은 NAC 조회로 확인 필요",
                "redaction": "synthetic",
                "raw_available": False,
            }
        ],
        "view_model": {
            "columns": ["시간", "Log ID", "Source IP", "Destination", "Service", "Action", "정책"],
            "rows": [
                ["14:27:31", "FW-20260704-0182", "10.23.14.52", "203.0.113.45", "443", "allow", "WEB-OUT"],
                ["14:27:30", "FW-20260704-0181", "10.23.14.52", "198.51.100.23", "443", "block", "WEB-OUT"],
                ["14:26:01", "FW-20260704-0179", "10.23.14.52", "198.51.100.77", "80", "block", "WEB-OUT"],
            ],
            "summary": {
                "directive_targets": 28,
                "reflected": 24,
                "missing": 4,
                "selected_log_id": "FW-0182",
            },
        },
    },
    (
        "nac",
        "ip_attribution",
    ): {
        "port": "nac",
        "query_type": "ip_attribution",
        "evidence": [
            {
                "evidence_id": "nac-node-10243",
                "source_port": "nac",
                "source_id": "nac-node-10243",
                "source_mode": "fixture",
                "claim": "관측 시각 기준 10.23.14.52는 조직 본부 업무부서 단말 nac-node-10243에 귀속됨",
                "confidence": "high",
                "observed_at": "2026-07-04T05:27:31Z",
                "related_entity_ids": ["ip-10-23-14-52", "asset-nac-node-10243"],
                "caveat": "사용자 식별자는 masked 값만 표시",
                "redaction": "masked",
                "raw_available": False,
            },
            {
                "evidence_id": "endpoint-posture-10243",
                "source_port": "nac",
                "source_id": "endpoint-posture-10243",
                "source_mode": "fixture",
                "claim": "Agent check-in은 정상이지만 Access가 limited(정책 제한) 상태",
                "confidence": "high",
                "observed_at": "2026-07-04T05:27:31Z",
                "related_entity_ids": ["asset-nac-node-10243"],
                "caveat": "접속 장애 원인 후보이며 외부 outbound 판단과 분리 필요",
                "redaction": "synthetic",
                "raw_available": False,
            },
        ],
        "view_model": {
            "node": {
                "node_id": "nac-node-10243",
                "ip": "10.23.14.52",
                "unit": "조직 본부 업무부서",
                "user_label": "18-1xxx-7xxx",
                "agent_status": "healthy",
                "access_state": "limited",
            },
            "static_ip_ledger": {
                "assigned_ip": "10.23.14.52",
                "observed_ip": "10.23.14.52",
                "mac_match": True,
                "approval_ref": "APR-2026-0512",
            },
        },
    },
    (
        "directive",
        "directive_compliance",
    ): {
        "port": "directive",
        "query_type": "directive_compliance",
        "evidence": [
            {
                "evidence_id": "directive-2026-071",
                "source_port": "directive",
                "source_id": "Directive-2026-071",
                "source_mode": "fixture",
                "claim": "Directive-2026-071 대상 28건 중 4건이 일부 scope의 blacklist에 미반영됨",
                "confidence": "high",
                "observed_at": "2026-07-04T05:26:00Z",
                "related_entity_ids": ["indicator-203-0-113-45", "policy-blacklist-main"],
                "caveat": "정책 반영은 승인 요청까지만 가능",
                "redaction": "synthetic",
                "raw_available": False,
            }
        ],
        "view_model": {
            "directive_id": "Directive-2026-071",
            "targets": 28,
            "reflected": 24,
            "missing": ["203.0.113.45", "198.51.100.77", "198.51.100.120", "203.0.113.12"],
            "approval_required": True,
        },
    },
    (
        "threat_intel",
        "indicator_enrichment",
    ): {
        "port": "threat_intel",
        "query_type": "indicator_enrichment",
        "evidence": [
            {
                "evidence_id": "threat-intel-203-0-113-45",
                "source_port": "threat_intel",
                "source_id": "fixture-ti-203-0-113-45",
                "source_mode": "fixture",
                "claim": "203.0.113.45는 모의 위협 인텔 fixture에서 suspicious outbound indicator로 분류됨",
                "confidence": "medium",
                "observed_at": "2026-07-04T05:31:00Z",
                "related_entity_ids": ["indicator-203-0-113-45"],
                "caveat": "외부 인텔은 내부 로그 판단을 보강하는 참고 근거",
                "redaction": "synthetic",
                "raw_available": False,
            }
        ],
        "view_model": {
            "indicator": "203.0.113.45",
            "risk": "medium",
            "sources": ["fixture-threat-intel"],
            "fallback_reason": "live adapter not configured",
        },
    },
}


# 장비별 상세 로그 분석(drill-down) fixture. equipment/analyze가 반환한다.
# 모든 값은 synthetic/masked이며 목적지 IP/ASN은 문서용(RFC5737) 대역이다.
ANALYSIS_RESULTS: dict[str, dict[str, Any]] = {
    "utm_firewall": {
        "port": "utm_firewall",
        "evidence_id": "fw-log-0182",
        "headline": "203.0.113.45로의 반복 outbound — 지시사항 미반영 대상과 일치",
        "risk_level": "elevated",
        "signals": [
            "동일 목적지로 12분간 9회 연결 (비정상 주기성)",
            "업무 시간대이나 목적지가 지시사항 차단 대상 IP",
            "허용 정책 WEB-OUT로 통과 — blacklist 미반영 구간",
        ],
        "correlated_evidence_ids": ["nac-node-10243", "directive-2026-071", "threat-intel-203-0-113-45"],
        "detail": {
            "fields": {
                "Log ID": "FW-20260704-0182",
                "5-tuple": "10.23.14.52:51142 → 203.0.113.45:443 / TCP",
                "세션 시간": "00:00:47",
                "Bytes out/in": "48.2KB / 3.1KB",
                "반복 연결": "9회 / 12분",
                "매칭 정책": "WEB-OUT (allow)",
                "목적지 ASN": "AS64500 (synthetic)",
                "목적지 분류": "TEST-NET-3 문서용 대역",
            },
            "related_rows": {
                "columns": ["시간", "Log ID", "Source IP", "Destination", "Service", "Action"],
                "rows": [
                    ["14:15:02", "FW-...0177", "10.23.14.52", "203.0.113.45", "443", "allow"],
                    ["14:19:44", "FW-...0179", "10.23.14.52", "203.0.113.45", "443", "allow"],
                    ["14:27:31", "FW-...0182", "10.23.14.52", "203.0.113.45", "443", "allow"],
                ],
            },
        },
    },
    "nac": {
        "port": "nac",
        "evidence_id": "nac-node-10243",
        "headline": "nac-node-10243 — Access limited(정책 제한) · 관측 IP=대장 IP 일치",
        "risk_level": "attention",
        "signals": [
            "Agent 정상 check-in (스푸핑 근거 없음)",
            "Access limited — 정책 제한 상태",
            "고정 IP 대장과 일치 — 귀속 확실",
        ],
        "correlated_evidence_ids": ["fw-log-0182", "endpoint-posture-10243"],
        "detail": {
            "fields": {
                "Node": "nac-node-10243",
                "소속": "조직 본부 업무부서",
                "Access": "limited",
                "MAC 일치": "예",
                "승인 근거": "APR-2026-0512",
            },
            "checks": [
                {"name": "Agent check-in", "pass": True},
                {"name": "고정 IP 대장 일치", "pass": True},
                {"name": "Access 정상", "pass": False},
            ],
        },
    },
    "directive": {
        "port": "directive",
        "evidence_id": "directive-2026-071",
        "headline": "Directive-2026-071 — 28건 중 4건 방화벽 미반영",
        "risk_level": "elevated",
        "signals": ["미반영 유해 IP 4건", "203.0.113.45 포함 — 현재 활성 outbound 대상"],
        "correlated_evidence_ids": ["fw-log-0182", "threat-intel-203-0-113-45"],
        "detail": {
            "fields": {
                "지시사항": "Directive-2026-071",
                "제목": "유해 IP 차단",
                "대상": "28건",
                "반영": "24건",
                "미반영": "4건",
            },
            "missing": ["203.0.113.45", "198.51.100.77", "198.51.100.120", "203.0.113.12"],
        },
    },
    "threat_intel": {
        "port": "threat_intel",
        "evidence_id": "threat-intel-203-0-113-45",
        "headline": "203.0.113.45 — C2 의심 지표 (공개 인텔 sanitized 요약)",
        "risk_level": "elevated",
        "signals": ["공개 출처에서 관측", "분류 C2 의심", "위험도 medium"],
        "correlated_evidence_ids": ["fw-log-0182", "directive-2026-071"],
        "detail": {
            "fields": {
                "지표": "203.0.113.45",
                "위험": "medium",
                "출처": "fixture-threat-intel",
                "원문 저장": "안 함",
            }
        },
    },
}


# 시나리오별 AAR 프로파일. create_aar가 여기에 동적 checked_evidence를 합친다.
AAR_PROFILES: dict[str, dict[str, Any]] = {
    MAIN_SCENARIO_ID: {
        "grade": "B",
        "score": 76,
        "summary": "핵심 근거는 대부분 확인했으나 지시사항 반영 누락 확인이 늦었습니다.",
        "timeline": [
            {"at_seconds": 25, "label": "민원 확인", "status": "ok"},
            {"at_seconds": 72, "label": "TrusGuard 조회", "status": "ok"},
            {"at_seconds": 140, "label": "Genian NAC 조회", "status": "ok"},
            {"at_seconds": 250, "label": "지시사항 늦음", "status": "late"},
        ],
        "missed_or_late_evidence": ["directive-2026-071"],
        "rubric_hits": ["source IP attribution", "approval-required action 분리"],
        "rubric_misses": ["단말 posture 보고 누락", "directive gap 확인 지연"],
        "priority_feedback": "서비스 장애와 의심 outbound를 병행 처리한 점은 적절합니다.",
        "severity_feedback": "정책 제한 + 의심 침해로 표현한 것은 evidence 수준에 맞습니다.",
        "effort_feedback": "즉시 안내와 승인 필요 정책 반영 요청을 분리했습니다.",
        "next_drills": [
            {"scenario_id": ADVANCED_SCENARIO_ID, "title": "유출 크리덴셜·랜섬웨어 복합 침해 대응", "reason": "복합 상관분석 난이도 상향"},
        ],
    },
    BASIC_SCENARIO_ID: {
        "grade": "A",
        "score": 88,
        "summary": "지시 대상과 방화벽 반영을 정확히 대조하고 미반영을 식별했습니다.",
        "timeline": [
            {"at_seconds": 20, "label": "지시사항 확인", "status": "ok"},
            {"at_seconds": 70, "label": "방화벽 blacklist 대조", "status": "ok"},
            {"at_seconds": 120, "label": "미반영 4건 식별", "status": "ok"},
            {"at_seconds": 180, "label": "반영 요청·보고", "status": "ok"},
        ],
        "missed_or_late_evidence": [],
        "rubric_hits": ["지시 대상 전수 확인", "미반영 항목 정확 식별"],
        "rubric_misses": ["보고 근거 인용 보강"],
        "priority_feedback": "단일 과제이므로 순서대로 정확히 처리한 점이 좋습니다.",
        "severity_feedback": "정책 제한으로 표현한 것은 적절합니다.",
        "effort_feedback": "반영 요청을 승인 절차로 분리했습니다.",
        "next_drills": [
            {"scenario_id": MAIN_SCENARIO_ID, "title": "업무망 접속 장애와 의심 outbound", "reason": "동시다발 이벤트 우선순위로 상향"},
        ],
    },
    ADVANCED_SCENARIO_ID: {
        "grade": "C+",
        "score": 71,
        "summary": "복합 상관분석은 시도했으나 유출 크리덴셜 노출 범위 산정과 랜섬웨어 헌팅이 약했습니다.",
        "timeline": [
            {"at_seconds": 30, "label": "계정 민원 확인", "status": "ok"},
            {"at_seconds": 80, "label": "크리덴셜 인텔 확인", "status": "ok"},
            {"at_seconds": 150, "label": "outbound 상관", "status": "ok"},
            {"at_seconds": 240, "label": "랜섬웨어 노출면 미점검", "status": "late"},
            {"at_seconds": 320, "label": "노출 범위 산정 지연", "status": "late"},
        ],
        "missed_or_late_evidence": ["threat-intel-203-0-113-45"],
        "rubric_hits": ["내부 관측·외부 인텔 상관", "계정 조치 승인 분리"],
        "rubric_misses": ["유출 크리덴셜 노출 범위 산정 미흡", "활성 랜섬웨어 노출면 헌팅 누락"],
        "priority_feedback": "계정 이상과 outbound를 함께 본 점은 좋으나 크리덴셜 노출 범위를 먼저 산정했어야 합니다.",
        "severity_feedback": "침해 의심으로 본 판단은 근거에 부합하나 확정 표현은 피해야 합니다.",
        "effort_feedback": "계정·격리 조치를 승인 요청으로 분리한 점은 적절합니다.",
        "next_drills": [
            {"scenario_id": MAIN_SCENARIO_ID, "title": "업무망 접속 장애와 의심 outbound", "reason": "기본 상관분석 흐름 복습"},
        ],
    },
}


def clone(value: Any) -> Any:
    return deepcopy(value)
