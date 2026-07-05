# 기능별 API 스펙

> 상태: BLUEPRINT 5 완료 기준
> 최종 업데이트: 2026-07-04 KST
> 범위: UI/UX 화면 흐름 기반 언어 독립 API 계약

> 2026-07-05 추가 결정: 기존 Operations API는 호환 유지한다. 신규 `사이버 방호 대시보드` read model,
> ChromaDB 기반 통합 검색, conversation 중심 헬프데스크 API 초안은
> `MODE_REDESIGN_CYBER_DEFENSE_DASHBOARD_HELPDESK.md`를 기준으로 구현 티켓(§9)에 반영한다.

## 1. 설계 원칙

이 문서는 구현 언어나 프레임워크를 전제하지 않는다. API 계약은 HTTP method, path, JSON request/response, 공통 오류 형식, mock 데이터 예시만 정의한다.

핵심 원칙:

- 화면은 원천 보안 제품 API를 직접 호출하지 않는다.
- UI는 `Training Session`, `Equipment Query`, `Evidence`, `Action`, `Dynamic Evaluation`, `AAR` 계약만 안다.
- Genian NAC형 NAC, TrusGuard형 UTM/FW, 지시사항함, ThreatIntel은 모두 adapter port 뒤에 있다.
- 모든 데모 데이터는 synthetic 또는 masked 값이다.
- 정책 변경, 단말 격리, 계정 조치 같은 write-like action은 실행이 아니라 `approval_required` proposal로 반환한다.
- 동적 평가는 rule-base 체크리스트만으로 끝나지 않고 scenario rubric, 현재 session state, action/evidence timeline을 기반으로 한다.

## 2. 화면별 API 호출 지도

| 화면 | 사용자 행동/상태 | 호출 API |
|---|---|---|
| 01 훈련 홈 | 홈 진입, 추천 훈련/최근 AAR 조회 | `GET /api/training/home` |
| 01 훈련 홈 | `훈련 시작` 클릭 | 클라이언트 라우팅으로 02 이동. 서버 호출 없음 |
| 02 시나리오 선택 | 카탈로그 로드, 필터 변경 | `GET /api/scenarios` |
| 02 시나리오 선택 | 특정 시나리오 선택 | `GET /api/scenarios/{scenario_id}` |
| 03 임무 브리핑 | 브리핑 화면 로드 | `GET /api/scenarios/{scenario_id}` |
| 03 임무 브리핑 | `임무 시작` 클릭 | `POST /api/training/sessions` |
| 04 미션 데스크 - TrusGuard | 세션 상태/이벤트 피드 로드 | `GET /api/training/sessions/{session_id}`, `GET /api/training/sessions/{session_id}/events` |
| 04 미션 데스크 - TrusGuard | 로그 검색 | `POST /api/training/sessions/{session_id}/equipment/query` with `port=utm_firewall` |
| 04 미션 데스크 - TrusGuard | 근거 pin | `POST /api/training/sessions/{session_id}/evidence/pins` |
| 04 미션 데스크 - TrusGuard | 우선순위/심각도/대응 노력 저장 | `PUT /api/training/sessions/{session_id}/assessment` |
| 04/05 미션 데스크 | 동적 평가 미리보기 | `POST /api/training/sessions/{session_id}/evaluation/preview` |
| 05 미션 데스크 - Genian NAC | IP 귀속/NAC 조회 | `POST /api/training/sessions/{session_id}/equipment/query` with `port=nac` |
| 05 미션 데스크 - Genian NAC | 지시사항/ThreatIntel 조회 | 같은 endpoint, `port=directive`, `threat_intel` |
| 04/05 미션 데스크 | 대응 제출 | `POST /api/training/sessions/{session_id}/actions` |
| 06 AAR 리플레이 | AAR 생성 | `POST /api/training/sessions/{session_id}/aar` |
| 06 AAR 리플레이 | AAR 조회/리플레이 | `GET /api/training/sessions/{session_id}/aar` |
| 06 AAR 리플레이 | 운영 보조 케이스 재사용 | `POST /api/ops/cases/from-training-session` |

## 3. 공통 형식

### 3.1 Response Envelope

모든 성공 응답은 같은 envelope을 사용한다.

```json
{
  "request_id": "req-20260704-0001",
  "data": {},
  "warnings": [],
  "meta": {
    "generated_at": "2026-07-04T05:32:10Z",
    "mode": "fixture"
  }
}
```

### 3.2 Error Envelope

```json
{
  "request_id": "req-20260704-0002",
  "error": {
    "code": "EVIDENCE_NOT_FOUND",
    "message": "요청한 evidence_id를 현재 세션에서 찾을 수 없습니다.",
    "retryable": false,
    "details": {
      "evidence_id": "fw-log-missing"
    }
  }
}
```

권장 오류 코드:

| 코드 | 의미 |
|---|---|
| `BAD_REQUEST` | 필수 필드 누락 또는 잘못된 enum |
| `SESSION_NOT_FOUND` | 세션 없음 |
| `SCENARIO_NOT_FOUND` | 시나리오 없음 |
| `EVIDENCE_NOT_FOUND` | evidence ID 없음 |
| `ADAPTER_UNAVAILABLE` | 특정 mock/live adapter 사용 불가 |
| `ACTION_REQUIRES_APPROVAL` | 실행형 조치가 승인 없이 요청됨 |
| `EVALUATION_PENDING` | 동적 평가 생성 중 |
| `REDACTION_REQUIRED` | raw 민감 데이터가 포함되어 반환 차단 |

### 3.3 공통 Enum

| 이름 | 값 |
|---|---|
| `mode` | `fixture`, `mock`, `live_readonly`, `live_approval_gated` |
| `source_port` | `ticket`, `identity`, `nac`, `utm_firewall`, `firewall_policy`, `directive`, `topology`, `threat_intel`, `sop`, `derived` |
| `severity` | `temporary_failure`, `policy_restriction`, `suspected_compromise`, `critical_compromise_possible` |
| `response_effort` | `quick_guidance`, `approval_required_action`, `longer_investigation`, `higher_report` |
| `priority` | `service_impact_first`, `security_incident_first`, `directive_gap_first`, `parallel_triage` |
| `confidence` | `low`, `medium`, `high` |
| `action_type` | `inspect`, `pin_evidence`, `user_guidance`, `policy_update_request`, `endpoint_isolation_review`, `escalate`, `report` |

## 4. 공통 데이터 모델

### ScenarioSummary

| 필드 | 설명 |
|---|---|
| `scenario_id` | 시나리오 ID |
| `title` | 표시 이름 |
| `difficulty` | `basic`, `intermediate`, `advanced` |
| `estimated_minutes` | 예상 소요 시간 |
| `training_goals` | 훈련 목표 목록 |
| `available_equipment` | 사용 가능한 mock/live 장비 port |
| `tags` | 검색/필터 태그 |

### TrainingSession

| 필드 | 설명 |
|---|---|
| `session_id` | 세션 ID |
| `scenario_id` | 연결 시나리오 |
| `status` | `briefing`, `running`, `submitted`, `aar_ready`, `closed` |
| `started_at` | 시작 시각 |
| `elapsed_seconds` | 훈련 경과 시간 |
| `mode` | fixture/mock/live-readonly 등 |
| `visible_event_seq` | 마지막으로 노출된 event sequence |
| `pinned_evidence_ids` | 훈련생이 pin한 근거 |
| `current_assessment` | 우선순위/심각도/대응 노력 판단 |

### Evidence

| 필드 | 설명 |
|---|---|
| `evidence_id` | 근거 ID |
| `source_port` | 출처 port |
| `source_id` | 원천 fixture/mock/live 식별자 |
| `source_mode` | adapter mode |
| `claim` | UI/AAR에 표시할 정규화 주장 |
| `confidence` | 신뢰도 |
| `observed_at` | 관측 시각 |
| `related_entity_ids` | 연결된 사용자/노드/정책/지표 |
| `caveat` | 해석 주의사항 |
| `redaction` | `sanitized`, `masked`, `synthetic` |
| `raw_available` | 항상 `false`가 기본 |

### Assessment

| 필드 | 설명 |
|---|---|
| `priority` | 우선순위 판단 |
| `severity` | 심각도 판단 |
| `response_efforts` | 대응 노력 구분 목록 |
| `approval_required` | 승인 필요 여부 |
| `confidence` | 판단 자신감 |
| `rationale` | 훈련생이 작성한 판단 근거 |
| `evidence_ids` | 판단에 사용한 근거 ID |

### DynamicEvaluation

| 필드 | 설명 |
|---|---|
| `evaluation_id` | 평가 ID |
| `scenario_id` | 시나리오 ID |
| `session_id` | 세션 ID |
| `rubric_version` | rubric 버전 |
| `overall_note` | 전체 코칭 문장 |
| `rubric_hits` | 충족한 rubric 항목 |
| `rubric_misses` | 놓친 rubric 항목 |
| `priority_feedback` | 우선순위 피드백 |
| `severity_feedback` | 심각도 피드백 |
| `effort_feedback` | 대응 노력 피드백 |
| `evidence_citations` | 평가에 인용한 evidence IDs |
| `confidence` | 평가 신뢰도 |
| `status` | `draft`, `ready`, `needs_more_evidence` |

## 5. API 상세

### 5.1 GET `/api/training/home`

훈련 홈에 필요한 추천 훈련, 최근 AAR, 숙련 요약을 반환한다.

Mock response:

```json
{
  "request_id": "req-home-001",
  "data": {
    "role_label": "통합보안관제센터 운영 담당자",
    "recommended_scenario": {
      "scenario_id": "scen-main-outbound-001",
      "title": "업무망 접속 장애와 의심 outbound",
      "difficulty": "intermediate",
      "estimated_minutes": 12,
      "training_goals": ["로그 확인", "IP 귀속", "정책 반영 누락 식별", "보고"]
    },
    "skill_summary": [
      { "name": "로그 분석", "score": 78 },
      { "name": "NAC 운용", "score": 72 },
      { "name": "정책 판단", "score": 68 },
      { "name": "보고 작성", "score": 81 }
    ],
    "recent_aars": [
      {
        "session_id": "sct-prev-001",
        "scenario_title": "유해 IP 미반영",
        "grade": "B",
        "key_feedback": "지시사항 확인 지연"
      }
    ]
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T05:32:10Z" }
}
```

### 5.2 GET `/api/scenarios`

시나리오 카탈로그를 반환한다.

Query parameters:

| 이름 | 설명 |
|---|---|
| `difficulty` | 선택. 난이도 필터 |
| `goal` | 선택. 훈련 목표 필터 |
| `max_minutes` | 선택. 예상 시간 상한 |

Mock response:

```json
{
  "request_id": "req-scenarios-001",
  "data": {
    "items": [
      {
        "scenario_id": "scen-main-outbound-001",
        "title": "업무망 접속 장애와 의심 outbound",
        "difficulty": "intermediate",
        "estimated_minutes": 12,
        "training_goals": ["로그 확인", "IP 귀속", "정책 반영 누락 식별", "보고"],
        "available_equipment": ["ticket", "utm_firewall", "nac", "directive", "threat_intel"],
        "tags": ["T5", "cyber-defense-room", "priority-triage"]
      }
    ]
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T05:32:20Z" }
}
```

### 5.3 GET `/api/scenarios/{scenario_id}`

임무 브리핑과 평가 rubric 요약을 반환한다. hidden ground truth는 반환하지 않는다.

Mock response:

```json
{
  "request_id": "req-scenario-001",
  "data": {
    "scenario_id": "scen-main-outbound-001",
    "title": "업무망 접속 장애와 의심 outbound",
    "briefing": {
      "role": "통합보안관제센터 운영 담당자",
      "situation": "업무용 홈페이지 접속 장애 민원이 접수되었고, 같은 시간대 의심 outbound 로그가 관측되었습니다.",
      "objective": "원인과 위험도를 판단하고 필요한 조치와 보고 초안을 제출하십시오.",
      "constraints": ["synthetic data only", "defensive workflow only", "write-like action은 승인 요청까지만"]
    },
    "available_equipment": [
      { "port": "ticket", "label": "민원/전화 기록" },
      { "port": "utm_firewall", "label": "TrusGuard형 UTM/FW" },
      { "port": "nac", "label": "Genian NAC형 NAC" },
      { "port": "directive", "label": "지시사항함" },
      { "port": "threat_intel", "label": "ThreatIntel" }
    ],
    "rubric_summary": [
      "동시다발 이벤트 우선순위",
      "일시 장애와 의심 침해 구분",
      "빠른 조치와 승인 필요 조치 분리",
      "근거 ID 기반 보고"
    ]
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T05:33:00Z" }
}
```

### 5.4 POST `/api/training/sessions`

시나리오 세션을 시작한다.

Mock request:

```json
{
  "scenario_id": "scen-main-outbound-001",
  "mode": "fixture",
  "difficulty": "intermediate",
  "hint_policy": "on_request"
}
```

Mock response:

```json
{
  "request_id": "req-session-start-001",
  "data": {
    "session_id": "sct-20260704-01",
    "scenario_id": "scen-main-outbound-001",
    "status": "running",
    "started_at": "2026-07-04T05:34:00Z",
    "elapsed_seconds": 0,
    "mode": "fixture",
    "visible_event_seq": 0,
    "pinned_evidence_ids": [],
    "current_assessment": null
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T05:34:00Z" }
}
```

### 5.5 GET `/api/training/sessions/{session_id}`

현재 세션 상태를 반환한다.

Mock response:

```json
{
  "request_id": "req-session-001",
  "data": {
    "session_id": "sct-20260704-01",
    "scenario_id": "scen-main-outbound-001",
    "status": "running",
    "elapsed_seconds": 132,
    "mode": "fixture",
    "visible_event_seq": 5,
    "pinned_evidence_ids": ["fw-log-0182", "directive-2026-071"],
    "current_assessment": {
      "priority": "parallel_triage",
      "severity": "suspected_compromise",
      "response_efforts": ["quick_guidance", "approval_required_action"],
      "approval_required": true,
      "confidence": "medium",
      "rationale": "FW/Directive 확인, NAC 추가 조회 필요",
      "evidence_ids": ["fw-log-0182", "directive-2026-071"]
    }
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T05:36:12Z" }
}
```

### 5.6 GET `/api/training/sessions/{session_id}/events`

세션의 visible event feed를 반환한다. MVP는 polling으로 충분하며, streaming은 후순위다.

Query parameters:

| 이름 | 설명 |
|---|---|
| `since_seq` | 선택. 이 sequence 이후 이벤트만 조회 |

Mock response:

```json
{
  "request_id": "req-events-001",
  "data": {
    "items": [
      {
        "seq": 1,
        "event_id": "evt-ticket-001",
        "timestamp": "2026-07-04T05:34:20Z",
        "event_type": "service_failure",
        "source_port": "ticket",
        "title": "서비스 장애",
        "visible_text": "업무용 홈페이지 접속 장애 민원",
        "severity_hint": "temporary_failure"
      },
      {
        "seq": 2,
        "event_id": "evt-fw-0182",
        "timestamp": "2026-07-04T05:35:00Z",
        "event_type": "suspicious_outbound",
        "source_port": "utm_firewall",
        "title": "의심 outbound",
        "visible_text": "Log ID: FW-20260704-0182",
        "severity_hint": "suspected_compromise"
      }
    ]
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T05:36:00Z" }
}
```

### 5.7 POST `/api/training/sessions/{session_id}/equipment/query`

미션 데스크의 목업 장비 조회를 단일 계약으로 처리한다. `port`와 `query`가 adapter port를 결정한다.

Mock request: TrusGuard형 UTM/FW 로그 검색

```json
{
  "port": "utm_firewall",
  "query_type": "firewall_log_search",
  "query": {
    "time_range": {
      "from": "2026-07-04T05:00:00Z",
      "to": "2026-07-04T06:00:00Z"
    },
    "source_ip": "10.23.14.52",
    "destination": "203.0.113.45"
  }
}
```

Mock response:

```json
{
  "request_id": "req-equipment-fw-001",
  "data": {
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
        "raw_available": false
      }
    ],
    "view_model": {
      "columns": ["시간", "Log ID", "Source IP", "Destination", "Service", "Action", "정책"],
      "rows": [
        ["14:27:31", "FW-20260704-0182", "10.23.14.52", "203.0.113.45", "443", "allow", "WEB-OUT"]
      ],
      "summary": {
        "directive_targets": 28,
        "reflected": 24,
        "missing": 4,
        "selected_log_id": "FW-0182"
      }
    }
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T05:36:30Z" }
}
```

Mock request: Genian NAC형 IP 귀속

```json
{
  "port": "nac",
  "query_type": "ip_attribution",
  "query": {
    "ip": "10.23.14.52",
    "observed_at": "2026-07-04T05:27:31Z"
  }
}
```

Mock response:

```json
{
  "request_id": "req-equipment-nac-001",
  "data": {
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
        "raw_available": false
      },
      {
        "evidence_id": "endpoint-posture-10243",
        "source_port": "nac",
        "source_id": "endpoint-posture-10243",
        "source_mode": "fixture",
        "claim": "Agent check-in은 정상이지만 Access는 limited이고 AV 기준 미준수 상태",
        "confidence": "high",
        "observed_at": "2026-07-04T05:27:31Z",
        "related_entity_ids": ["asset-nac-node-10243"],
        "caveat": "접속 장애 원인 후보이며 외부 outbound 판단과 분리 필요",
        "redaction": "synthetic",
        "raw_available": false
      }
    ],
    "view_model": {
      "node": {
        "node_id": "nac-node-10243",
        "ip": "10.23.14.52",
        "unit": "조직 본부 업무부서",
        "user_label": "18-1xxx-7xxx",
        "agent_status": "healthy",
        "access_state": "limited"
      },
      "static_ip_ledger": {
        "assigned_ip": "10.23.14.52",
        "observed_ip": "10.23.14.52",
        "mac_match": true,
        "approval_ref": "APR-2026-0512"
      },
      "endpoint_posture": {
        "av_version": "1.0.0.1234",
        "baseline_version": "20260615.01",
        "relay_sync": "delayed",
        "violation": "AV 미준수"
      }
    }
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T05:37:00Z" }
}
```

### 5.8 POST `/api/training/sessions/{session_id}/evidence/pins`

훈련생이 직접 확인한 evidence를 조사 노트에 pin한다.

Mock request:

```json
{
  "evidence_ids": ["fw-log-0182", "directive-2026-071"],
  "note": "FW 로그와 지시사항 gap을 우선 근거로 pin"
}
```

Mock response:

```json
{
  "request_id": "req-pin-001",
  "data": {
    "session_id": "sct-20260704-01",
    "pinned_evidence_ids": ["fw-log-0182", "directive-2026-071"],
    "pinned_at": "2026-07-04T05:37:20Z"
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T05:37:20Z" }
}
```

### 5.9 PUT `/api/training/sessions/{session_id}/assessment`

훈련생의 우선순위, 심각도, 대응 노력 판단을 저장한다.

Mock request:

```json
{
  "priority": "parallel_triage",
  "severity": "suspected_compromise",
  "response_efforts": ["quick_guidance", "approval_required_action", "higher_report"],
  "approval_required": true,
  "confidence": "medium",
  "rationale": "접속 장애는 AV 기준 미준수와 관련 가능성이 높고, 유해 IP 지시사항 반영 누락은 별도 보고가 필요함.",
  "evidence_ids": ["fw-log-0182", "nac-node-10243", "endpoint-posture-10243", "directive-2026-071"]
}
```

Mock response:

```json
{
  "request_id": "req-assessment-001",
  "data": {
    "session_id": "sct-20260704-01",
    "assessment": {
      "priority": "parallel_triage",
      "severity": "suspected_compromise",
      "response_efforts": ["quick_guidance", "approval_required_action", "higher_report"],
      "approval_required": true,
      "confidence": "medium",
      "rationale": "접속 장애는 AV 기준 미준수와 관련 가능성이 높고, 유해 IP 지시사항 반영 누락은 별도 보고가 필요함.",
      "evidence_ids": ["fw-log-0182", "nac-node-10243", "endpoint-posture-10243", "directive-2026-071"]
    },
    "saved_at": "2026-07-04T05:38:00Z"
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T05:38:00Z" }
}
```

### 5.10 POST `/api/training/sessions/{session_id}/evaluation/preview`

현재까지의 행동과 근거를 바탕으로 동적 평가 초안을 생성한다. 훈련 중에는 짧은 상태만 보여 주고, 자세한 평가는 AAR에서 표시한다.

Mock request:

```json
{
  "include_private_rubric_detail": false,
  "reason": "mission_desk_status_strip"
}
```

Mock response:

```json
{
  "request_id": "req-eval-preview-001",
  "data": {
    "evaluation_id": "eval-preview-001",
    "status": "draft",
    "summary_strip": {
      "priority": "적절",
      "severity": "근거 수준 일치",
      "response_effort": "분리됨",
      "rubric": "AV 보고 보강"
    },
    "evidence_citations": ["fw-log-0182", "nac-node-10243", "directive-2026-071"],
    "confidence": "medium"
  },
  "warnings": [
    {
      "code": "PARTIAL_EVALUATION",
      "message": "훈련 중 미리보기이므로 최종 AAR 평가와 다를 수 있습니다."
    }
  ],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T05:38:30Z" }
}
```

### 5.11 POST `/api/training/sessions/{session_id}/actions`

훈련생의 대응 제출을 저장한다. 실제 조치 실행이 아니라 action proposal과 보고 초안이다.

Mock request:

```json
{
  "actions": [
    {
      "action_type": "user_guidance",
      "title": "사용자 AV 업데이트 안내",
      "body": "단말 posture 점검 후 업무용 홈페이지 접속을 재시도하도록 안내",
      "evidence_ids": ["endpoint-posture-10243"],
      "approval_required": false
    },
    {
      "action_type": "policy_update_request",
      "title": "Directive 2026-071 blacklist 반영 요청",
      "body": "203.0.113.45가 일부 scope에서 미반영되어 승인 요청",
      "evidence_ids": ["fw-log-0182", "directive-2026-071"],
      "approval_required": true
    },
    {
      "action_type": "report",
      "title": "상위 조직 보고 초안",
      "body": "민원, FW 로그, NAC 귀속, AV 미준수, 지시사항 gap을 근거로 보고",
      "evidence_ids": ["fw-log-0182", "nac-node-10243", "endpoint-posture-10243", "directive-2026-071"],
      "approval_required": true
    }
  ]
}
```

Mock response:

```json
{
  "request_id": "req-actions-001",
  "data": {
    "session_id": "sct-20260704-01",
    "status": "submitted",
    "submitted_actions": [
      {
        "action_id": "act-user-guidance-001",
        "action_type": "user_guidance",
        "approval_required": false,
        "evidence_ids": ["endpoint-posture-10243"]
      },
      {
        "action_id": "act-policy-request-001",
        "action_type": "policy_update_request",
        "approval_required": true,
        "evidence_ids": ["fw-log-0182", "directive-2026-071"]
      }
    ],
    "next_available": ["generate_aar"]
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T05:39:00Z" }
}
```

### 5.12 POST `/api/training/sessions/{session_id}/aar`

AAR 생성을 요청한다. 내부적으로 동적 평가가 아직 없으면 먼저 생성한다.

Mock request:

```json
{
  "include_dynamic_evaluation": true,
  "include_operations_reuse_hint": true
}
```

Mock response:

```json
{
  "request_id": "req-aar-create-001",
  "data": {
    "aar_id": "aar-sct-20260704-01",
    "session_id": "sct-20260704-01",
    "status": "ready",
    "grade": "B",
    "score": 76,
    "summary": "핵심 근거는 대부분 확인했으나 지시사항 반영 누락 확인이 늦었습니다.",
    "dynamic_evaluation": {
      "evaluation_id": "eval-final-001",
      "rubric_version": "scen-main-outbound-001:v1",
      "overall_note": "서비스 장애 안내와 의심 outbound 조사를 병행한 점은 적절하지만 지시사항 gap 확인이 늦었습니다.",
      "rubric_hits": ["source IP attribution", "approval-required action 분리"],
      "rubric_misses": ["단말 posture 보고 누락", "directive gap 확인 지연"],
      "priority_feedback": "서비스 장애와 의심 outbound를 병행 처리한 점은 적절합니다.",
      "severity_feedback": "정책 제한 + 의심 침해로 표현한 것은 evidence 수준에 맞습니다.",
      "effort_feedback": "즉시 안내와 승인 필요 정책 반영 요청을 분리했습니다.",
      "evidence_citations": ["fw-log-0182", "nac-node-10243", "directive-2026-071"],
      "confidence": "high",
      "status": "ready"
    }
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T05:40:00Z" }
}
```

### 5.13 GET `/api/training/sessions/{session_id}/aar`

AAR 리플레이 화면 데이터를 반환한다.

Mock response:

```json
{
  "request_id": "req-aar-get-001",
  "data": {
    "aar_id": "aar-sct-20260704-01",
    "session_id": "sct-20260704-01",
    "score": 76,
    "grade": "B",
    "timeline": [
      { "at_seconds": 25, "label": "민원 확인", "status": "ok" },
      { "at_seconds": 72, "label": "TrusGuard 조회", "status": "ok" },
      { "at_seconds": 140, "label": "Genian NAC 조회", "status": "ok" },
      { "at_seconds": 250, "label": "지시사항 늦음", "status": "late" }
    ],
    "checked_evidence": ["fw-log-0182", "nac-node-10243", "endpoint-posture-10243"],
    "missed_or_late_evidence": ["directive-2026-071"],
    "dynamic_evaluation": {
      "priority_feedback": "서비스 장애 안내와 의심 outbound 조사를 병행한 점은 적절하나 지시사항 gap 확인이 늦었습니다.",
      "severity_feedback": "정책 제한 + 의심 침해 표현은 근거 수준에 맞습니다.",
      "effort_feedback": "즉시 안내와 승인 필요 조치를 분리했습니다."
    },
    "next_drills": [
      {
        "scenario_id": "scen-directive-gap-001",
        "title": "유해 IP 지시사항 미반영 대응",
        "reason": "정책 반영 누락 확인 속도 보강"
      }
    ],
    "operations_reuse_available": true
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T05:40:10Z" }
}
```

### 5.14 POST `/api/ops/cases/from-training-session`

훈련 사건을 운영 보조 케이스로 변환한다. Training Mode와 Operations Mode가 같은 evidence model을 공유함을 보여 주는 데모용 API다.

Mock request:

```json
{
  "session_id": "sct-20260704-01",
  "reuse_evidence_ids": ["fw-log-0182", "nac-node-10243", "endpoint-posture-10243", "directive-2026-071"]
}
```

Mock response:

```json
{
  "request_id": "req-ops-from-training-001",
  "data": {
    "case_id": "ops-case-20260704-001",
    "source_session_id": "sct-20260704-01",
    "status": "draft",
    "operator_note": "사용자 접속 장애, NAC/AV posture, FW outbound, directive gap을 같은 사건으로 검토",
    "recommended_outputs": [
      "사용자 안내 초안",
      "정책 반영 요청 draft",
      "일일 보고 문단"
    ]
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T05:41:00Z" }
}
```

### 5.15 GET `/api/adapters/status`

현재 adapter mode와 사용 가능 상태를 반환한다. 화면의 `mock/live 보강 데이터 사용 불가` 상태에 사용한다.

Mock response:

```json
{
  "request_id": "req-adapters-001",
  "data": {
    "items": [
      { "port": "utm_firewall", "mode": "fixture", "status": "available" },
      { "port": "nac", "mode": "fixture", "status": "available" },
      { "port": "directive", "mode": "fixture", "status": "available" },
      { "port": "threat_intel", "mode": "fixture", "status": "available", "fallback_reason": null }
    ]
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T05:41:20Z" }
}
```

### 5.16 GET `/api/ops/units`

Operations Mode의 synthetic 조직 계층을 반환한다. 실제 조직명·인원·식별번호은 포함하지 않는다.

Mock response:

```json
{
  "request_id": "req-ops-units-001",
  "data": {
    "items": [
      {
        "unit_id": "unit-corps-cyber",
        "name": "상위 조직-통합보안관제센터",
        "role": "higher",
        "parent_unit_id": null,
        "ancestor_unit_ids": [],
        "child_unit_ids": ["unit-bn-a", "unit-bn-b"],
        "managed_node_count": 10420
      },
      {
        "unit_id": "unit-bn-a",
        "name": "현장 보안팀-A",
        "role": "field",
        "parent_unit_id": "unit-corps-cyber",
        "ancestor_unit_ids": ["unit-corps-cyber"],
        "child_unit_ids": [],
        "managed_node_count": 6120
      }
    ],
    "root_unit_ids": ["unit-corps-cyber"],
    "default_viewer_unit_id": "unit-bn-a",
    "higher_unit_id": "unit-corps-cyber",
    "managed_node_count_total": 10420
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T06:20:00Z" }
}
```

### 5.17 GET `/api/ops/adapters/status`

Operations Mode 전용 adapter 상태를 반환한다. B-08에서는 외부 발송 없는 인앱 `NotificationPort` fixture와
Operations 저장소 backend 상태만 제공한다.

Mock response:

```json
{
  "request_id": "req-ops-adapters-001",
  "data": {
    "storage_backend": "sqlite",
    "items": [
      {
        "port": "notification",
        "mode": "fixture",
        "status": "available",
        "external_delivery": false,
        "capabilities": ["in_app_record_only", "unit_escalation_preview", "ack_tracking"]
      },
      {
        "port": "operations_storage",
        "mode": "sqlite",
        "status": "available",
        "external_delivery": false,
        "capabilities": ["unit_seed", "incident_ready", "knowledge_ready"]
      }
    ]
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T06:20:20Z" }
}
```

### 5.18 POST `/api/ops/incidents`

Operations Mode 사건을 접수하고, 해당 조직와 심각도별 상위 조직 체인에 인앱 알림을 생성한다. 외부 발송은 없다.

Mock request:

```json
{
  "unit_id": "unit-bn-a",
  "title": "방화벽 지시 반영 누락 의심",
  "severity": "high",
  "note": "Directive-2026-071 대조 필요",
  "evidence_ids": ["directive-2026-071", "fw-log-0182"]
}
```

Mock response:

```json
{
  "request_id": "req-ops-incident-create-001",
  "data": {
    "incident_id": "inc-20260704-001",
    "unit_id": "unit-bn-a",
    "title": "방화벽 지시 반영 누락 의심",
    "severity": "high",
    "status": "received",
    "created_at": "2026-07-04T06:30:00Z",
    "evidence_ids": ["directive-2026-071", "fw-log-0182"],
    "timeline": [
      {
        "at": "2026-07-04T06:30:00Z",
        "from": null,
        "to": "received",
        "actor_unit": "unit-bn-a",
        "note": "Directive-2026-071 대조 필요",
        "evidence_ids": ["directive-2026-071", "fw-log-0182"]
      }
    ],
    "notified_unit_ids": ["unit-bn-a", "unit-corps-cyber"],
    "notifications": [
      {
        "notification_id": "ntf-001",
        "incident_id": "inc-20260704-001",
        "to_unit_id": "unit-bn-a",
        "kind": "incident_opened",
        "severity": "high",
        "title": "방화벽 지시 반영 누락 의심",
        "read": false
      }
    ]
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T06:30:00Z" }
}
```

### 5.19 GET `/api/ops/incidents?unit_id=&status=`

조직 관점 사건 목록을 반환한다. `unit_id`가 상위 조직 조직이면 하위 조직 사건도 포함한다.

Mock response:

```json
{
  "request_id": "req-ops-incidents-001",
  "data": {
    "items": [
      {
        "incident_id": "inc-20260704-001",
        "unit_id": "unit-bn-a",
        "title": "방화벽 지시 반영 누락 의심",
        "severity": "high",
        "status": "received",
        "notified_unit_ids": ["unit-bn-a", "unit-corps-cyber"]
      }
    ]
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T06:31:00Z" }
}
```

### 5.20 GET `/api/ops/notifications?unit_id=`

조직 관점 알림 피드를 반환한다. 미확인 알림을 우선 표시하고 `unread_count`를 함께 반환한다.

Mock response:

```json
{
  "request_id": "req-ops-notifications-001",
  "data": {
    "items": [
      {
        "notification_id": "ntf-002",
        "incident_id": "inc-20260704-001",
        "to_unit_id": "unit-corps-cyber",
        "kind": "incident_opened",
        "severity": "high",
        "title": "방화벽 지시 반영 누락 의심",
        "read": false
      }
    ],
    "unread_count": 1
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T06:31:20Z" }
}
```

### 5.21 POST `/api/ops/notifications/{notification_id}/ack`

인앱 알림을 확인 처리한다. 외부 시스템에는 아무 동작도 하지 않는다.

Mock response:

```json
{
  "request_id": "req-ops-ntf-ack-001",
  "data": {
    "notification_id": "ntf-002",
    "read": true
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T06:31:40Z" }
}
```

### 5.22 POST `/api/ops/incidents/{incident_id}/status`

사건 상태를 전이하고 timeline에 비휘발 기록을 남긴다. 발생 조직만 전이할 수 있고 상위 조직 조직는 읽기 전용이다.
`needs_approval` 전이는 실제 조치 실행이 아니라 승인 필요 제안으로만 기록한다.

Mock request:

```json
{
  "actor_unit_id": "unit-bn-a",
  "to_status": "in_progress",
  "note": "방화벽 로그와 NAC posture 대조 시작",
  "evidence_ids": ["fw-log-0182"]
}
```

Mock response:

```json
{
  "request_id": "req-ops-status-001",
  "data": {
    "incident_id": "inc-20260704-001",
    "status": "in_progress",
    "approval_required": false,
    "executed": false,
    "timeline_entry": {
      "at": "2026-07-04T06:33:00Z",
      "from": "received",
      "to": "in_progress",
      "actor_unit": "unit-bn-a",
      "note": "방화벽 로그와 NAC posture 대조 시작",
      "evidence_ids": ["fw-log-0182"]
    },
    "notifications": [
      {
        "notification_id": "ntf-003",
        "incident_id": "inc-20260704-001",
        "to_unit_id": "unit-corps-cyber",
        "kind": "status_changed",
        "severity": "high",
        "title": "방화벽 지시 반영 누락 의심",
        "read": false
      }
    ],
    "allowed_transitions": ["contained", "needs_approval", "escalated"],
    "accumulated_knowledge_id": null
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T06:33:00Z" }
}
```

### 5.23 GET `/api/ops/incidents/{incident_id}/timeline`

사건 상태 전이와 조치 이력을 반환한다.

Mock response:

```json
{
  "request_id": "req-ops-timeline-001",
  "data": {
    "incident_id": "inc-20260704-001",
    "items": [
      {
        "at": "2026-07-04T06:30:00Z",
        "from": null,
        "to": "received",
        "actor_unit": "unit-bn-a",
        "note": "Directive-2026-071 대조 필요",
        "evidence_ids": ["directive-2026-071", "fw-log-0182"]
      },
      {
        "at": "2026-07-04T06:33:00Z",
        "from": "received",
        "to": "in_progress",
        "actor_unit": "unit-bn-a",
        "note": "방화벽 로그와 NAC posture 대조 시작",
        "evidence_ids": ["fw-log-0182"]
      }
    ]
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T06:33:10Z" }
}
```

### 5.24 GET `/api/ops/status-board?unit_id=`

상위 조직 조직 관점에서 하위 조직 사건 상태판을 읽기 전용으로 반환한다. 하위 조직의 상태 전이는 여기서 실행하지 않는다.

Mock response:

```json
{
  "request_id": "req-ops-status-board-001",
  "data": {
    "viewer_unit_id": "unit-corps-cyber",
    "subordinate_units": ["unit-bn-a", "unit-bn-b"],
    "incidents": [
      {
        "incident_id": "inc-20260704-001",
        "unit_id": "unit-bn-a",
        "title": "방화벽 지시 반영 누락 의심",
        "status": "in_progress",
        "severity": "high",
        "elapsed_seconds": 600,
        "last_transition": "received→in_progress"
      }
    ]
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-04T06:33:20Z" }
}
```

### 5.25 GET `/api/knowledge?query=&tags=&unit_id=` · GET `/api/knowledge/{id}` · POST `/api/knowledge`

비휘발 업무 지식DB(B-11). 사건 종결·훈련 AAR 생성·문의 해결 시 자동 축적되고, 수동 등록은 `POST`로 한다.
모든 축적은 redaction 게이트를 통과한다: 자격증명/JWT 감지 시 `REDACTION_BLOCKED`, 이메일·허용 대역
(RFC1918/RFC5737/loopback) 밖 IP·식별번호 형태는 마스킹 저장. 목록 응답에는 대시보드 집계가 함께 온다.

Mock response (`GET /api/knowledge`):

```json
{
  "request_id": "req-knowledge-001",
  "data": {
    "items": [
      {
        "knowledge_id": "kb-001",
        "source_type": "aar",
        "source_id": "aar-basic-20260703-07",
        "title": "유해 IP 차단 지시 미반영 식별 절차",
        "summary": "상위 조직 지시(directive)와 방화벽 blacklist 반영 상태를 대조해 미반영 IP를 식별하고, 반영은 승인 요청으로 상신한다.",
        "tags": ["유해IP", "directive-gap", "방화벽"],
        "evidence_ids": ["directive-2026-071", "fw-log-0182"],
        "resolution": "미반영 2건 식별 → 정책 반영 승인 요청 상신 → 상위 조직 보고 초안 작성",
        "unit_id": "unit-bn-a",
        "created_at": "2026-07-03T02:10:00Z"
      }
    ],
    "total": 5,
    "top_tags": [{ "tag": "directive-gap", "count": 2 }],
    "by_source": { "aar": 2, "incident": 1, "action": 1, "inquiry": 1 },
    "by_unit": { "unit-bn-a": 2, "unit-bn-b": 2, "unit-corps-cyber": 1 }
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-05T02:10:00Z" }
}
```

- 자동 축적 dedup 키는 `source_type + source_id`다. 같은 원본을 다시 축적해도 기존 지식이 반환된다.
- 사건 종결(`POST /status` → `closed`) 응답의 `accumulated_knowledge_id`가 생성된 지식을 가리킨다.

### 5.26 POST `/api/helpdesk/inquiries` · GET `/api/helpdesk/inquiries?unit_id=&status=` · POST `/api/helpdesk/inquiries/{id}/resolve`

업무 문의 답변(B-12). 검색이 1차: 지식DB retrieval(토큰 매칭, 임계값으로 단어 1개 우연 일치 차단) 후
OpenAI 호환 LLM API(`LlmProviderPort`, `D4D_LLM_BASE_URL` + `/v1/chat/completions`)가 있으면 검색 컨텍스트 범위 안에서 답변을
생성하고(`engine:"llm"`), 없으면 규칙/템플릿으로 항상 응답한다(`engine:"rule"`). 관련 지식이 없으면
답변을 생성하지 않고 근거 부족을 반환한다(환각 방지, `grounded:false`, `status:"needs_review"`).

Mock response (`POST /api/helpdesk/inquiries`):

```json
{
  "request_id": "req-helpdesk-inquiry-001",
  "data": {
    "inquiry_id": "inq-001",
    "unit_id": "unit-bn-a",
    "question": "유해 IP 지시 반영이 일부 누락됐을 때 절차는?",
    "answer": "관련 지식 \"유해 IP 차단 지시 미반영 식별 절차\" 기준: … 정책 반영·격리·계정 조치는 자동 실행이 아니라 승인 절차를 따릅니다.",
    "engine": "rule",
    "confidence": "high",
    "citations": {
      "knowledge_ids": ["kb-001", "kb-005"],
      "evidence_ids": ["directive-2026-071", "fw-log-0182"]
    },
    "fallback_used": true,
    "grounded": true,
    "status": "answered",
    "created_at": "2026-07-05T02:12:00Z",
    "linked_knowledge_ids": ["kb-001", "kb-005"]
  },
  "warnings": [],
  "meta": { "mode": "fixture", "generated_at": "2026-07-05T02:12:00Z" }
}
```

- 모든 grounded 답변에 `citations`(knowledge/evidence)가 강제된다. 인용이 없으면 반드시 근거 부족 응답이다.
- `POST .../resolve`는 문의를 `resolved`로 바꾸고 질문–답변 쌍을 FAQ 지식으로 축적한다
  (응답 `accumulated_knowledge_id`). 이미 해결된 문의는 `BAD_REQUEST`.
- 모든 LLM endpoint는 OpenAI 호환 chat completions 계약을 사용한다. `D4D_LLM_API_KEY` 같은 비밀은 환경변수로만 주입하고 코드/fixture에 저장하지 않는다.

## 6. Mock E2E 사고 실험

목표: 위 API만으로 `훈련 시작 -> 시나리오 선택 -> 임무 브리핑 -> 미션 데스크 -> 대응 제출 -> AAR -> 운영 보조 재사용`이 가능한지 검증한다.

### 6.1 정상 흐름

1. 홈이 `GET /api/training/home`을 호출한다.
   - 추천 시나리오와 최근 AAR이 한 번에 온다.
   - 과설계 방지: 홈 카드마다 별도 API를 만들지 않는다.

2. 시나리오 선택 화면이 `GET /api/scenarios`를 호출한다.
   - 필터는 query parameter로 충분하다.
   - 누락 없음: 난이도, 목표, 예상 시간, 사용 장비가 모두 포함된다.

3. 브리핑 화면이 `GET /api/scenarios/{scenario_id}`를 호출한다.
   - hidden ground truth는 반환하지 않는다.
   - rubric은 summary만 보여 준다.

4. 훈련생이 `임무 시작`을 누르면 `POST /api/training/sessions`를 호출한다.
   - session ID가 생기고 이벤트 피드가 시작된다.
   - 화면은 이후 모든 조회에 `session_id`를 사용한다.

5. 미션 데스크가 `GET /api/training/sessions/{session_id}`와 `/events`를 polling한다.
   - MVP는 polling으로 충분하다.
   - 실시간 streaming은 6번 아키텍처에서 확장 옵션으로 둔다.

6. TrusGuard 로그 검색은 `equipment/query` with `port=utm_firewall`로 처리한다.
   - 장비별 엔드포인트를 만들지 않아 UI가 vendor API에 묶이지 않는다.
   - view model과 evidence가 함께 와서 화면 표시와 AAR 인용이 동시에 가능하다.

7. 훈련생이 `fw-log-0182`를 pin하면 `evidence/pins`를 호출한다.
   - AAR은 pin 여부를 기준으로 "직접 확인한 근거"와 "시스템이 나중에 안 근거"를 구분할 수 있다.

8. NAC 조회도 `equipment/query` with `port=nac`로 처리한다.
   - `nac-node-10243`과 `endpoint-posture-10243` 두 evidence가 생성된다.
   - IP attribution과 endpoint compliance가 분리되어 평가가 쉬워진다.

9. 우선순위/심각도/대응 노력은 `PUT /assessment`로 저장한다.
   - 훈련생이 실제 판단을 남기므로 AAR이 결과만이 아니라 판단 과정을 평가할 수 있다.

10. 동적 평가 미리보기는 `evaluation/preview`를 호출한다.
    - 훈련 중에는 정답을 과하게 노출하지 않고 짧은 상태만 반환한다.
    - 자세한 rubric detail은 AAR에서만 공개한다.

11. 대응 제출은 `POST /actions`로 저장한다.
    - `approval_required`가 조치별로 분리되어 자동 실행 오해를 막는다.

12. AAR 생성은 `POST /aar`, 조회는 `GET /aar`로 분리한다.
    - 생성 비용이 크거나 LLM 평가가 지연될 수 있으므로 생성/조회 분리가 필요하다.

13. 운영 보조 재사용은 `POST /api/ops/cases/from-training-session`으로 처리한다.
    - 훈련과 운영이 같은 evidence IDs를 공유한다는 피치 근거가 된다.

### 6.2 과설계 제거

초기에는 장비별 API를 다음처럼 나눌 수 있었다.

```text
POST /api/utm/logs/search
POST /api/nac/nodes/attribution
POST /api/directives/diff
POST /api/av/status
POST /api/intel/enrich
```

하지만 이 방식은 UI가 장비별 API를 직접 알아야 하고, 실제 제품/목업 교체에도 취약하다. 최종 스펙은 `equipment/query` 하나로 묶고 `port`, `query_type`, `query`로 분기한다. 장비별 세부 계약은 adapter spec에 둔다.

### 6.3 빠트린 부분 보완

사고 실험 중 다음 누락을 발견해 보완했다.

| 발견 | 보완 |
|---|---|
| 홈 화면의 추천 훈련과 최근 AAR을 어디서 받는지 불명확 | `GET /api/training/home` 추가 |
| 평가가 AAR 생성 시점에만 가능하면 미션 데스크 하단 평가 스트립을 구현하기 어려움 | `POST /evaluation/preview` 추가 |
| 우선순위/심각도/대응 노력 판단 저장 API가 없으면 고급 역량 평가가 불가능 | `PUT /assessment` 추가 |
| 운영 보조 재사용을 화면에서 보여 줄 API가 없음 | `POST /api/ops/cases/from-training-session` 추가 |
| mock/live adapter 장애 상태를 UI에 표시할 수 없음 | `GET /api/adapters/status` 추가 |

### 6.4 남겨 둔 확장

이번 API 스펙에는 넣지 않는 것:

- 클래스/수강생 관리 API.
- 복잡한 시나리오 편집기 API.
- 실시간 streaming 전용 프로토콜.
- 실제 조치 실행 API.
- 세부 권한/조직 관리 API.

해커톤 MVP는 한 시나리오의 세션 실행, 근거 조회, 판단 저장, 대응 제출, AAR 생성이 끊기지 않는 것이 더 중요하다.

## 7. BLUEPRINT 5 완료 기준 체크

| 기준 | 상태 |
|---|---|
| UI 화면별 호출 위치 정의 | 완료 |
| request/response 공통 형식 정의 | 완료 |
| 기능별 API 유형과 인터페이스 정의 | 완료 |
| mock request/output 예시 작성 | 완료 |
| mock API 기반 e2e 사고 실험 | 완료 |
| 과설계/누락 분석과 보완 | 완료 |
| 프로그래밍 언어 의존성 제거 | 완료 |
