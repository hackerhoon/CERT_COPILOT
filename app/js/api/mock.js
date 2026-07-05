/**
 * In-browser mock API — fixture responses matching architecture/API_SPEC.md.
 *
 * Every response uses the same envelope as the real API:
 *   { request_id, data, warnings, meta: { mode, generated_at } }
 *
 * Endpoints for A-01/A-02/A-03 are fully populated: home/scenarios/briefing,
 * session/events (with since_seq for feed polling), and equipment/query for the
 * the mock devices. Endpoints owned by later tickets return a NOT_IMPLEMENTED
 * error envelope rather than throwing, so the UI can show a graceful state.
 *
 * NOTE: fixtures are synthetic/masked only. No hidden ground truth is exposed
 * on briefing/scenario responses (per API_SPEC 5.3).
 */
window.D4D = window.D4D || {};
(function (D4D) {
  "use strict";

  var SCENARIOS = [
    {
      scenario_id: "scen-main-outbound-001",
      title: "업무망 접속 장애와 의심 outbound",
      difficulty: "intermediate",
      estimated_minutes: 12,
      training_goals: ["로그 확인", "IP 귀속", "정책 반영 누락 식별", "보고"],
      available_equipment: ["ticket", "utm_firewall", "nac", "directive", "threat_intel"],
      tags: ["T5", "cyber-defense-room", "priority-triage"],
      summary: "접속 장애 민원, 의심 outbound, 지시사항 미반영, 단말 미준수를 함께 판단하는 훈련",
    },
    {
      scenario_id: "scen-harmful-ip-002",
      title: "유해 IP 차단 지시 반영 점검",
      difficulty: "basic",
      estimated_minutes: 8,
      training_goals: ["지시사항 확인", "blacklist 반영 대조", "미반영 식별", "보고"],
      available_equipment: ["ticket", "directive", "utm_firewall", "threat_intel"],
      tags: ["T5", "directive-gap", "onboarding"],
      summary: "상급제대 유해 IP 차단 지시와 방화벽 blacklist 반영 상태를 대조해 미반영을 찾는다.",
    },
    {
      scenario_id: "scen-cred-ransom-003",
      title: "유출 크리덴셜·활성 랜섬웨어 기반 복합 침해 대응",
      difficulty: "advanced",
      estimated_minutes: 16,
      training_goals: ["크리덴셜 노출 평가", "침해 정황 상관분석", "계정 조치 승인 분리", "위협 헌팅", "상급 보고"],
      available_equipment: ["ticket", "utm_firewall", "nac", "directive", "threat_intel"],
      tags: ["T5", "threat-hunting", "credential-exposure", "ransomware"],
      summary: "StealthMole 인텔의 유출 크리덴셜·활성 랜섬웨어 노출과 내부 관측을 상관분석하는 복합 시나리오.",
    },
  ];

  var EQUIPMENT_LABELS = {
    ticket: "민원/전화 기록",
    utm_firewall: "TrusGuard형 UTM/FW",
    nac: "Genian NAC형 NAC",
    directive: "지시사항함",
    threat_intel: "ThreatIntel",
    identity: "계정/IAM",
  };

  var HOME = {
    role_label: "통합보안관제센터 운영 담당자",
    headline: "훈련을 통해 사이버방호 임무 역량을 강화하십시오.",
    recommended_scenario: {
      scenario_id: "scen-main-outbound-001",
      title: "업무망 접속 장애와 의심 outbound",
      difficulty: "intermediate",
      estimated_minutes: 12,
      training_goals: ["로그 확인", "IP 귀속", "정책 반영 누락 식별", "보고"],
      reason: "사이버방호 업무 종합 · 동시다발 이벤트 우선순위 훈련",
    },
    weekly_progress: { label: "이번 주 진행", percent: 42, caption: "훈련" },
    skill_summary: [
      { name: "로그 분석", score: 78 },
      { name: "NAC 운용", score: 72 },
      { name: "정책 판단", score: 68 },
      { name: "보고 작성", score: 81 },
    ],
    recent_aars: [
      { session_id: "sct-prev-001", scenario_title: "유해 IP 미반영", grade: "B", key_feedback: "지시사항 확인 지연" },
      { session_id: "sct-prev-002", scenario_title: "피싱 신고", grade: "A", key_feedback: "보고 품질 우수" },
      { session_id: "sct-prev-003", scenario_title: "단말 posture 점검", grade: "C", key_feedback: "posture 근거 누락" },
    ],
    common_weaknesses: ["지시사항 반영 누락 확인 지연", "보고 근거 인용 부족"],
  };

  var SESSION_EVENTS = [
    { seq: 1, event_id: "evt-ticket-001", timestamp: "2026-07-04T05:34:20Z", event_type: "service_failure", source_port: "ticket", title: "서비스 장애", visible_text: "업무용 홈페이지 접속 장애 민원", severity_hint: "temporary_failure" },
    { seq: 2, event_id: "evt-fw-0182", timestamp: "2026-07-04T05:35:00Z", event_type: "suspicious_outbound", source_port: "utm_firewall", title: "의심 outbound", visible_text: "Log ID: FW-20260704-0182", severity_hint: "suspected_compromise" },
    { seq: 3, event_id: "evt-directive-071", timestamp: "2026-07-04T05:35:30Z", event_type: "directive", source_port: "directive", title: "지시사항", visible_text: "유해 IP 차단 지시사항 · Directive-2026-071", severity_hint: "policy_restriction" },
    { seq: 4, event_id: "evt-nac-10243", timestamp: "2026-07-04T05:36:00Z", event_type: "endpoint_posture", source_port: "nac", title: "NAC 알림", visible_text: "Agent 미준수 노드 발생 · nac-node-10243", severity_hint: "policy_restriction" },
  ];

  var BASIC_EVENTS = [
    { seq: 1, event_id: "evt-directive-071-basic", timestamp: "2026-07-04T05:34:00Z", event_type: "directive_gap", source_port: "directive", title: "유해 IP 차단 지시 하달", visible_text: "Directive-2026-071 · 대상 28건 · 반영 마감 임박", severity_hint: "policy_restriction" },
    { seq: 2, event_id: "evt-fw-blacklist-basic", timestamp: "2026-07-04T05:34:40Z", event_type: "policy_gap", source_port: "utm_firewall", title: "방화벽 반영 확인 필요", visible_text: "일부 network scope blacklist 반영 상태 미확인", severity_hint: "policy_restriction" },
  ];

  var ADVANCED_EVENTS = [
    { seq: 1, event_id: "evt-ticket-acct", timestamp: "2026-07-04T05:33:40Z", event_type: "service_failure", source_port: "ticket", title: "계정 이상 민원", visible_text: "다수 사용자 계정 잠금·재인증 요구 민원 접수", severity_hint: "policy_restriction" },
    { seq: 2, event_id: "evt-ti-cred", timestamp: "2026-07-04T05:34:10Z", event_type: "threat_intel", source_port: "threat_intel", title: "유출 크리덴셜 노출", visible_text: "외부 인텔에서 관리 도메인 관련 유출 크리덴셜 다수 관측", severity_hint: "suspected_compromise" },
    { seq: 3, event_id: "evt-fw-0182-adv", timestamp: "2026-07-04T05:34:50Z", event_type: "suspicious_outbound", source_port: "utm_firewall", title: "의심 outbound", visible_text: "Log ID: FW-20260704-0182 · 반복 outbound", severity_hint: "suspected_compromise" },
    { seq: 4, event_id: "evt-ti-ransom", timestamp: "2026-07-04T05:35:20Z", event_type: "threat_intel", source_port: "threat_intel", title: "활성 랜섬웨어 노출", visible_text: "동종 섹터 대상 활성 랜섬웨어 그룹 노출 관측(헌팅 근거)", severity_hint: "policy_restriction" },
    { seq: 5, event_id: "evt-nac-10243-adv", timestamp: "2026-07-04T05:35:50Z", event_type: "endpoint_posture", source_port: "nac", title: "단말 posture", visible_text: "nac-node-10243 access limited · 상태 확인 필요", severity_hint: "policy_restriction" },
    { seq: 6, event_id: "evt-directive-071-adv", timestamp: "2026-07-04T05:36:20Z", event_type: "directive_gap", source_port: "directive", title: "지시사항 gap", visible_text: "Directive-2026-071 일부 미반영 · 대조 필요", severity_hint: "policy_restriction" },
  ];

  var EVENTS_BY_SCENARIO = {
    "scen-main-outbound-001": SESSION_EVENTS,
    "scen-harmful-ip-002": BASIC_EVENTS,
    "scen-cred-ransom-003": ADVANCED_EVENTS,
  };

  // Mock는 세션→시나리오 매핑을 기억해 시나리오별 이벤트/AAR을 서빙한다.
  var sessionScenarios = {};
  function eventsFor(sid) { return EVENTS_BY_SCENARIO[sessionScenarios[sid]] || SESSION_EVENTS; }

  // Per-port equipment query fixtures (API_SPEC 5.7). Each returns an evidence[]
  // list (shared evidence contract, no raw data) plus a UI view_model. utm_firewall
  // and nac match the spec examples; directive/threat_intel are modeled the
  // same way. The renderer dispatches on `port`.
  var OBS = "2026-07-04T05:27:31Z";
  var EQUIPMENT_QUERY = {
    utm_firewall: {
      port: "utm_firewall",
      query_type: "firewall_log_search",
      evidence: [
        {
          evidence_id: "fw-log-0182", source_port: "utm_firewall", source_id: "FW-20260704-0182",
          source_mode: "fixture",
          claim: "10.23.14.52에서 203.0.113.45:443으로 허용된 outbound 로그가 관측됨",
          confidence: "high", observed_at: OBS,
          related_entity_ids: ["ip-10-23-14-52", "indicator-203-0-113-45"],
          caveat: "내부 단말 귀속은 NAC 조회로 확인 필요", redaction: "synthetic", raw_available: false,
        },
      ],
      view_model: {
        columns: ["시간", "Log ID", "Source IP", "Destination", "Service", "Action", "정책"],
        rows: [["14:27:31", "FW-20260704-0182", "10.23.14.52", "203.0.113.45", "443", "allow", "WEB-OUT"]],
        summary: { directive_targets: 28, reflected: 24, missing: 4, selected_log_id: "FW-0182" },
      },
    },
    nac: {
      port: "nac",
      query_type: "ip_attribution",
      evidence: [
        {
          evidence_id: "nac-node-10243", source_port: "nac", source_id: "nac-node-10243", source_mode: "fixture",
          claim: "관측 시각 기준 10.23.14.52는 조직 본부 업무부서 단말 nac-node-10243에 귀속됨",
          confidence: "high", observed_at: OBS,
          related_entity_ids: ["ip-10-23-14-52", "asset-nac-node-10243"],
          caveat: "사용자 식별자는 masked 값만 표시", redaction: "masked", raw_available: false,
        },
        {
          evidence_id: "endpoint-posture-10243", source_port: "nac", source_id: "endpoint-posture-10243", source_mode: "fixture",
          claim: "Agent check-in은 정상이지만 Access가 limited(정책 제한) 상태",
          confidence: "high", observed_at: OBS,
          related_entity_ids: ["asset-nac-node-10243"],
          caveat: "접속 장애 원인 후보이며 외부 outbound 판단과 분리 필요", redaction: "synthetic", raw_available: false,
        },
      ],
      view_model: {
        node: { node_id: "nac-node-10243", ip: "10.23.14.52", unit: "조직 본부 업무부서", user_label: "18-1xxx-7xxx", agent_status: "healthy", access_state: "limited" },
        static_ip_ledger: { assigned_ip: "10.23.14.52", observed_ip: "10.23.14.52", mac_match: true, approval_ref: "APR-2026-0512" },
      },
    },
    directive: {
      port: "directive",
      query_type: "directive_compliance",
      evidence: [
        {
          evidence_id: "directive-2026-071", source_port: "directive", source_id: "Directive-2026-071", source_mode: "fixture",
          claim: "유해 IP 차단 지시사항 28건 중 4건이 방화벽 정책에 미반영",
          confidence: "high", observed_at: OBS,
          related_entity_ids: ["indicator-203-0-113-45"],
          caveat: "정책 반영은 승인 절차 필요 (approval_required)", redaction: "synthetic", raw_available: false,
        },
      ],
      view_model: {
        directive_id: "Directive-2026-071", targets: 28, reflected: 24,
        missing: ["203.0.113.45", "198.51.100.77", "198.51.100.120", "203.0.113.12"], approval_required: true,
      },
    },
    threat_intel: {
      port: "threat_intel",
      query_type: "indicator_enrichment",
      evidence: [
        {
          evidence_id: "threat-intel-203-0-113-45", source_port: "threat_intel", source_id: "indicator-203-0-113-45", source_mode: "fixture",
          claim: "203.0.113.45는 공개 위협 인텔에서 C2 의심 지표로 관측됨",
          confidence: "medium", observed_at: OBS,
          related_entity_ids: ["indicator-203-0-113-45"],
          caveat: "sanitized 요약만 표시하며 원문 응답은 저장하지 않음", redaction: "sanitized", raw_available: false,
        },
      ],
      view_model: {
        indicator: "203.0.113.45", risk: "medium", sources: ["fixture-threat-intel"], fallback_reason: null,
        // 합성 landscape (백엔드는 로컬 StealthMole 데이터셋에서 마스킹 집계로 대체).
        landscape: {
          source: "fixture:synthetic",
          dataset_run: "synthetic",
          ransomware: {
            sampled: 3, feed_total: 30020,
            top_groups: { Qilin: 2, Akira: 1 },
            recent: [
              { attack_group: "Qilin", victim: "Md L***", sector: "Accounting (AI)" },
              { attack_group: "Akira", victim: "Good***", sector: "Social Services (AI)" },
            ],
          },
          credentials: {
            sampled: 3, feed_total: 1079829, with_password: 3,
            top_domains: { "gma***": 2, "exa***": 1 },
            recent_samples: [
              { email: "t***@g***.com", domain: "gma***", password: "***(len=60)", leaked_date: "2026-04" },
            ],
          },
          monitoring: {
            government_sampled: 2, leaked_sampled: 2,
            recent_titles: [{ title: "www.gis.gov.**", author: "HX***" }],
          },
        },
      },
    },
  };

  // 장비별 상세 분석(drill-down) fixture. equipment/analyze가 반환한다.
  // 모든 값은 synthetic/masked이며 목적지 IP/ASN/대역은 문서용(TEST-NET) 대역이다.
  var ANALYSIS = {
    utm_firewall: {
      port: "utm_firewall", evidence_id: "fw-log-0182",
      headline: "203.0.113.45로의 반복 outbound — 지시사항 미반영 대상과 일치",
      risk_level: "elevated",
      signals: [
        "동일 목적지로 12분간 9회 연결 (비정상 주기성)",
        "업무 시간대이나 목적지가 지시사항 차단 대상 IP",
        "허용 정책 WEB-OUT로 통과 — blacklist 미반영 구간",
      ],
      correlated_evidence_ids: ["nac-node-10243", "directive-2026-071", "threat-intel-203-0-113-45"],
      detail: {
        fields: {
          "Log ID": "FW-20260704-0182",
          "5-tuple": "10.23.14.52:51142 → 203.0.113.45:443 / TCP",
          "세션 시간": "00:00:47",
          "Bytes out/in": "48.2KB / 3.1KB",
          "반복 연결": "9회 / 12분",
          "매칭 정책": "WEB-OUT (allow)",
          "목적지 ASN": "AS64500 (synthetic)",
          "목적지 분류": "TEST-NET-3 문서용 대역",
        },
        related_rows: {
          columns: ["시간", "Log ID", "Source IP", "Destination", "Service", "Action"],
          rows: [
            ["14:15:02", "FW-...0177", "10.23.14.52", "203.0.113.45", "443", "allow"],
            ["14:19:44", "FW-...0179", "10.23.14.52", "203.0.113.45", "443", "allow"],
            ["14:27:31", "FW-...0182", "10.23.14.52", "203.0.113.45", "443", "allow"],
          ],
        },
      },
    },
    nac: {
      port: "nac", evidence_id: "nac-node-10243",
      headline: "nac-node-10243 — Access limited(정책 제한) · 관측 IP=대장 IP 일치",
      risk_level: "attention",
      signals: [
        "Agent 정상 check-in (스푸핑 근거 없음)",
        "Access limited — 정책 제한 상태",
        "고정 IP 대장과 일치 — 귀속 확실",
      ],
      correlated_evidence_ids: ["fw-log-0182", "endpoint-posture-10243"],
      detail: {
        fields: { "Node": "nac-node-10243", "소속": "조직 본부 업무부서", "Access": "limited", "MAC 일치": "예", "승인 근거": "APR-2026-0512" },
        checks: [
          { name: "Agent check-in", pass: true },
          { name: "고정 IP 대장 일치", pass: true },
          { name: "Access 정상", pass: false },
        ],
      },
    },
    directive: {
      port: "directive", evidence_id: "directive-2026-071",
      headline: "Directive-2026-071 — 28건 중 4건 방화벽 미반영",
      risk_level: "elevated",
      signals: ["미반영 유해 IP 4건", "203.0.113.45 포함 — 현재 활성 outbound 대상"],
      correlated_evidence_ids: ["fw-log-0182", "threat-intel-203-0-113-45"],
      detail: {
        fields: { "지시사항": "Directive-2026-071", "제목": "유해 IP 차단", "대상": "28건", "반영": "24건", "미반영": "4건" },
        missing: ["203.0.113.45", "198.51.100.23", "203.0.113.77", "198.51.100.9"],
      },
    },
    threat_intel: {
      port: "threat_intel", evidence_id: "threat-intel-203-0-113-45",
      headline: "203.0.113.45 — C2 의심 지표 (공개 인텔 sanitized 요약)",
      risk_level: "elevated",
      signals: ["2개 공개 출처에서 관측", "최초 관측 2026-06-20", "분류 c2_suspected"],
      correlated_evidence_ids: ["fw-log-0182", "directive-2026-071"],
      detail: {
        fields: { "지표": "203.0.113.45", "유형": "ipv4", "분류": "c2_suspected", "신뢰도": "보통", "출처 수": "2", "원문 저장": "안 함" },
      },
    },
  };

  // 정책 반영/격리/보고/상급전파성 조치는 클라이언트 입력과 무관하게 항상 승인 필요로
  // 강제한다. 백엔드 WRITE_LIKE_ACTIONS 집합과 동일하게 유지한다.
  var FORCE_APPROVAL = {
    policy_update_request: true,
    endpoint_isolation_review: true,
    report: true,
    escalate: true,
  };

  // 세션에서 조회 가능한 evidence id 집합 — pin/assessment 인용 검증에 쓴다.
  var KNOWN_EVIDENCE = {
    "fw-log-0182": 1, "nac-node-10243": 1, "endpoint-posture-10243": 1,
    "directive-2026-071": 1, "threat-intel-203-0-113-45": 1,
  };
  var HIGH_SEVERITY = { suspected_compromise: 1, critical_compromise_possible: 1 };

  // 시나리오별 AAR fixture (API_SPEC 5.12/5.13). synthetic 평가 결과.
  var AAR_BY_SCENARIO = {
    "scen-main-outbound-001": {
      aar_id: "aar-sct-20260704-01", session_id: "sct-20260704-01", status: "ready",
      grade: "B", score: 76,
      summary: "핵심 근거는 대부분 확인했으나 지시사항 반영 누락 확인이 늦었습니다.",
      timeline: [
        { at_seconds: 25, label: "민원 확인", status: "ok" },
        { at_seconds: 72, label: "TrusGuard 조회", status: "ok" },
        { at_seconds: 140, label: "Genian NAC 조회", status: "ok" },
        { at_seconds: 250, label: "지시사항 늦음", status: "late" },
      ],
      checked_evidence: ["fw-log-0182", "nac-node-10243", "endpoint-posture-10243"],
      missed_or_late_evidence: ["directive-2026-071"],
      dynamic_evaluation: {
        evaluation_id: "eval-final-001", rubric_version: "scen-main-outbound-001:v1",
        overall_note: "서비스 장애 안내와 의심 outbound 조사를 병행한 점은 적절하지만 지시사항 gap 확인이 늦었습니다.",
        rubric_hits: ["source IP attribution", "approval-required action 분리"],
        rubric_misses: ["단말 posture 보고 누락", "directive gap 확인 지연"],
        priority_feedback: "서비스 장애와 의심 outbound를 병행 처리한 점은 적절합니다.",
        severity_feedback: "정책 제한 + 의심 침해로 표현한 것은 evidence 수준에 맞습니다.",
        effort_feedback: "즉시 안내와 승인 필요 정책 반영 요청을 분리했습니다.",
        evidence_citations: ["fw-log-0182", "nac-node-10243", "directive-2026-071"], confidence: "high",
      },
      next_drills: [{ scenario_id: "scen-cred-ransom-003", title: "유출 크리덴셜·랜섬웨어 복합 침해 대응", reason: "복합 상관분석 난이도 상향" }],
      operations_reuse_available: true,
    },
    "scen-harmful-ip-002": {
      aar_id: "aar-basic", session_id: "sct-20260704-01", status: "ready",
      grade: "A", score: 88,
      summary: "지시 대상과 방화벽 반영을 정확히 대조하고 미반영을 식별했습니다.",
      timeline: [
        { at_seconds: 20, label: "지시사항 확인", status: "ok" },
        { at_seconds: 70, label: "방화벽 blacklist 대조", status: "ok" },
        { at_seconds: 120, label: "미반영 4건 식별", status: "ok" },
        { at_seconds: 180, label: "반영 요청·보고", status: "ok" },
      ],
      checked_evidence: ["directive-2026-071", "fw-log-0182"],
      missed_or_late_evidence: [],
      dynamic_evaluation: {
        evaluation_id: "eval-basic", rubric_version: "scen-harmful-ip-002:v1",
        overall_note: "지시 대상과 방화벽 반영을 정확히 대조하고 미반영을 식별했습니다.",
        rubric_hits: ["지시 대상 전수 확인", "미반영 항목 정확 식별"],
        rubric_misses: ["보고 근거 인용 보강"],
        priority_feedback: "단일 과제이므로 순서대로 정확히 처리한 점이 좋습니다.",
        severity_feedback: "정책 제한으로 표현한 것은 적절합니다.",
        effort_feedback: "반영 요청을 승인 절차로 분리했습니다.",
        evidence_citations: ["directive-2026-071", "fw-log-0182"], confidence: "high",
      },
      next_drills: [{ scenario_id: "scen-main-outbound-001", title: "업무망 접속 장애와 의심 outbound", reason: "동시다발 이벤트 우선순위로 상향" }],
      operations_reuse_available: true,
    },
    "scen-cred-ransom-003": {
      aar_id: "aar-adv", session_id: "sct-20260704-01", status: "ready",
      grade: "C+", score: 71,
      summary: "복합 상관분석은 시도했으나 유출 크리덴셜 노출 범위 산정과 랜섬웨어 헌팅이 약했습니다.",
      timeline: [
        { at_seconds: 30, label: "계정 민원 확인", status: "ok" },
        { at_seconds: 80, label: "크리덴셜 인텔 확인", status: "ok" },
        { at_seconds: 150, label: "outbound 상관", status: "ok" },
        { at_seconds: 240, label: "랜섬웨어 노출면 미점검", status: "late" },
        { at_seconds: 320, label: "노출 범위 산정 지연", status: "late" },
      ],
      checked_evidence: ["fw-log-0182", "nac-node-10243", "threat-intel-203-0-113-45"],
      missed_or_late_evidence: ["threat-intel-203-0-113-45"],
      dynamic_evaluation: {
        evaluation_id: "eval-adv", rubric_version: "scen-cred-ransom-003:v1",
        overall_note: "복합 상관분석은 시도했으나 유출 크리덴셜 노출 범위 산정과 랜섬웨어 헌팅이 약했습니다.",
        rubric_hits: ["내부 관측·외부 인텔 상관", "계정 조치 승인 분리"],
        rubric_misses: ["유출 크리덴셜 노출 범위 산정 미흡", "활성 랜섬웨어 노출면 헌팅 누락"],
        priority_feedback: "계정 이상과 outbound를 함께 본 점은 좋으나 크리덴셜 노출 범위를 먼저 산정했어야 합니다.",
        severity_feedback: "침해 의심으로 본 판단은 근거에 부합하나 확정 표현은 피해야 합니다.",
        effort_feedback: "계정·격리 조치를 승인 요청으로 분리한 점은 적절합니다.",
        evidence_citations: ["fw-log-0182", "nac-node-10243", "threat-intel-203-0-113-45"], confidence: "high",
      },
      next_drills: [{ scenario_id: "scen-main-outbound-001", title: "업무망 접속 장애와 의심 outbound", reason: "기본 상관분석 흐름 복습" }],
      operations_reuse_available: true,
    },
  };
  function aarFor(sid) { return AAR_BY_SCENARIO[sessionScenarios[sid]] || AAR_BY_SCENARIO["scen-main-outbound-001"]; }

  var SCENARIO_BRIEF = {
    "scen-main-outbound-001": {
      role: "통합보안관제센터 운영 담당자",
      situation: "업무용 홈페이지 접속 장애 민원이 접수되었고, 같은 시간대 의심 outbound 로그가 관측되었습니다.",
      objective: "원인과 위험도를 판단하고 필요한 조치와 보고 초안을 제출하십시오.",
      constraints: ["synthetic data only", "defensive workflow only", "write-like action은 승인 요청까지만"],
      rubric_summary: ["동시다발 이벤트 우선순위", "일시 장애와 의심 침해 구분", "빠른 조치와 승인 필요 조치 분리", "근거 ID 기반 보고"],
    },
    "scen-harmful-ip-002": {
      role: "통합보안관제센터 운영 담당자",
      situation: "상급제대에서 유해 IP 차단 지시(Directive-2026-071)가 하달되었습니다. 방화벽 blacklist 반영 상태를 점검하십시오.",
      objective: "지시 대상과 방화벽 반영 상태를 대조해 미반영 항목을 찾고, 반영 요청과 보고 초안을 제출하십시오.",
      constraints: ["synthetic data only", "defensive workflow only", "정책 반영은 승인 요청까지만"],
      rubric_summary: ["지시사항 대상 전수 확인", "방화벽 blacklist와 지시 대조", "미반영 항목 정확 식별", "반영 요청·보고 분리"],
    },
    "scen-cred-ransom-003": {
      role: "통합보안관제센터 통합관제 담당",
      situation: "StealthMole 외부 인텔에서 관리 도메인 관련 유출 크리덴셜 다수와 활성 랜섬웨어 그룹의 동종 섹터 노출이 확인되었고, 같은 시간대 내부 단말에서 의심 outbound가 관측됩니다.",
      objective: "유출 크리덴셜 노출 범위를 산정하고 내부 관측과 외부 인텔을 상관분석해 침해 정황을 판단하십시오. 계정·격리성 조치는 승인 요청으로 분리하고 상급 보고 초안을 제출하십시오.",
      constraints: ["synthetic/masked data only", "raw credential 노출 금지 (마스킹 값만)", "계정/격리 조치는 승인 요청까지만"],
      rubric_summary: ["유출 크리덴셜 노출 범위·심각도 산정", "내부 관측과 외부 인텔 상관분석", "활성 랜섬웨어 노출면 점검(위협 헌팅)", "계정·격리 조치를 승인 요청으로 분리", "다중 근거 인용 상급 보고"],
    },
  };

  function scenarioBriefing(id) {
    var s = SCENARIOS.filter(function (x) { return x.scenario_id === id; })[0];
    if (!s) return null;
    var b = SCENARIO_BRIEF[id] || SCENARIO_BRIEF["scen-main-outbound-001"];
    return {
      scenario_id: s.scenario_id,
      title: s.title,
      difficulty: s.difficulty,
      estimated_minutes: s.estimated_minutes,
      briefing: {
        role: b.role,
        situation: b.situation,
        objective: b.objective,
        constraints: b.constraints,
      },
      available_equipment: s.available_equipment.map(function (p) {
        return { port: p, label: EQUIPMENT_LABELS[p] || p };
      }),
      rubric_summary: b.rubric_summary,
    };
  }

  // Operations Mode (A-07) — synthetic 부대 계층. 백엔드 B-08(API_SPEC 5.16)과
  // 동일한 이름·필드를 사용한다. 부대명은 synthetic label만 사용.
  var OPS_UNITS = [
    {
      unit_id: "unit-corps-cyber", name: "상위 관제센터", role: "higher",
      parent_unit_id: null, ancestor_unit_ids: [], child_unit_ids: ["unit-bn-a", "unit-bn-b"],
      managed_node_count: 10420,
    },
    {
      unit_id: "unit-bn-a", name: "예하 보안대대-A", role: "field",
      parent_unit_id: "unit-corps-cyber", ancestor_unit_ids: ["unit-corps-cyber"], child_unit_ids: [],
      managed_node_count: 6120,
    },
    {
      unit_id: "unit-bn-b", name: "예하 보안대대-B", role: "field",
      parent_unit_id: "unit-corps-cyber", ancestor_unit_ids: ["unit-corps-cyber"], child_unit_ids: [],
      managed_node_count: 4300,
    },
  ];

  // Operations 사건/알림 (A-08) — B-09 계약 선반영. mock은 새로고침 전까지
  // in-memory로 유지되며, 알림은 인앱 레코드만 생성한다(외부 발송 없음).
  var OPS_SEVERITY_DEPTH = { low: 1, medium: 1, high: 2, critical: 99 };
  var OPS_SEVERITIES = { low: true, medium: true, high: true, critical: true };
  var opsIncidentSeq = 0;
  var opsNotifSeq = 0;
  var OPS_INCIDENTS = [];
  var OPS_NOTIFICATIONS = [];

  function opsUnit(unitId) {
    for (var i = 0; i < OPS_UNITS.length; i++) {
      if (OPS_UNITS[i].unit_id === unitId) return OPS_UNITS[i];
    }
    return null;
  }

  function opsAncestors(unitId) {
    var chain = [];
    var u = opsUnit(unitId);
    while (u && u.parent_unit_id) {
      chain.push(u.parent_unit_id);
      u = opsUnit(u.parent_unit_id);
    }
    return chain;
  }

  function opsDescendants(unitId) {
    return OPS_UNITS.filter(function (u) {
      return opsAncestors(u.unit_id).indexOf(unitId) !== -1;
    }).map(function (u) { return u.unit_id; });
  }

  function opsStamp() {
    // mock 고정 기준 시각에서 생성 순서만 분 단위로 증가시킨다.
    var n = opsIncidentSeq + opsNotifSeq;
    return "2026-07-04T06:" + ("0" + Math.min(59, 10 + n)).slice(-2) + ":00Z";
  }

  // 상태 머신 — 백엔드 B-10(operations_runtime.STATUS_TRANSITIONS)과 동일하게 유지.
  // needs_approval은 write-like 조치의 "제안" 상태(실행 아님)이며, 승인 후
  // in_progress로 복귀해야 contained로 갈 수 있다.
  var OPS_TRANSITIONS = {
    received: ["in_progress", "needs_approval", "escalated"],
    in_progress: ["contained", "needs_approval", "escalated"],
    needs_approval: ["in_progress", "escalated"],
    contained: ["closed", "needs_approval"],
    escalated: ["in_progress", "contained", "closed"],
    closed: [],
  };

  function opsNotify(incident, kind, includeSelf) {
    var depth = OPS_SEVERITY_DEPTH[incident.severity] || 1;
    var targets = (includeSelf ? [incident.unit_id] : []).concat(opsAncestors(incident.unit_id).slice(0, depth));
    return targets.map(function (unitId) {
      opsNotifSeq += 1;
      var n = {
        notification_id: "ntf-" + ("00" + opsNotifSeq).slice(-3),
        incident_id: incident.incident_id,
        to_unit_id: unitId,
        kind: kind,
        severity: incident.severity,
        title: incident.title,
        created_at: opsStamp(),
        read: false,
      };
      OPS_NOTIFICATIONS.push(n);
      return n;
    });
  }

  function opsCreateIncident(unitId, title, severity, note, evidenceIds) {
    opsIncidentSeq += 1;
    var inc = {
      incident_id: "inc-20260704-" + ("00" + opsIncidentSeq).slice(-3),
      unit_id: unitId,
      title: title,
      severity: severity,
      status: "received",
      created_at: opsStamp(),
      evidence_ids: evidenceIds || [],
      timeline: [
        { at: opsStamp(), from: null, to: "received", actor_unit: unitId, note: note || "상황 접수" },
      ],
      notified_unit_ids: [],
    };
    OPS_INCIDENTS.push(inc);
    var notifications = opsNotify(inc, "incident_opened", true);
    inc.notified_unit_ids = notifications.map(function (n) { return n.to_unit_id; });
    return { incident: inc, notifications: notifications };
  }

  function opsIncidentById(id) {
    for (var i = 0; i < OPS_INCIDENTS.length; i++) {
      if (OPS_INCIDENTS[i].incident_id === id) return OPS_INCIDENTS[i];
    }
    return null;
  }

  function opsLastTransition(inc) {
    var last = inc.timeline[inc.timeline.length - 1];
    if (!last) return "접수";
    return last.from ? last.from + "→" + last.to : "접수";
  }

  function opsIncidentDto(inc) {
    var d = {};
    Object.keys(inc).forEach(function (k) { d[k] = inc[k]; });
    d.allowed_transitions = (OPS_TRANSITIONS[inc.status] || []).slice();
    d.notifications = OPS_NOTIFICATIONS.filter(function (n) { return n.incident_id === inc.incident_id; });
    return d;
  }

  // 데모 seed: 하위 부대(보안대대-B) 사건 1건 → 상급 관점 알림 합류가 처음부터 보인다.
  opsCreateIncident(
    "unit-bn-b",
    "NAC 미준수 단말 급증 (패턴 3일 경과)",
    "medium",
    "야간 점검 중 posture 미준수 단말 증가 관측",
    []
  );

  // 지식DB (A-10) — B-11 계약 선반영. 사건 종결·문의 해결 시 자동 축적되는
  // 비휘발 지식 루프의 mock이다. 모든 값은 synthetic/masked.
  var opsKnowledgeSeq = 0;
  var OPS_KNOWLEDGE = [];

  function opsAddKnowledge(fields) {
    // source_type+source_id 중복 억제 (설계 §2.2)
    var dup = null;
    OPS_KNOWLEDGE.forEach(function (k) {
      if (k.source_type === fields.source_type && k.source_id === fields.source_id) dup = k;
    });
    if (dup) return dup;
    opsKnowledgeSeq += 1;
    var item = {
      knowledge_id: "kb-" + ("00" + opsKnowledgeSeq).slice(-3),
      source_type: fields.source_type,
      source_id: fields.source_id,
      title: fields.title,
      summary: fields.summary,
      tags: fields.tags || [],
      evidence_ids: fields.evidence_ids || [],
      resolution: fields.resolution || "",
      unit_id: fields.unit_id || null,
      created_at: fields.created_at || opsStamp(),
    };
    OPS_KNOWLEDGE.push(item);
    return item;
  }

  // seed 지식 (사건/조치/AAR/문의에서 축적된 형태의 synthetic 예시)
  opsAddKnowledge({
    source_type: "aar", source_id: "aar-basic-20260703-07",
    title: "유해 IP 차단 지시 미반영 식별 절차",
    summary: "상급 지시(directive)와 방화벽 blacklist 반영 상태를 대조해 미반영 IP를 식별하고, 반영은 승인 요청으로 상신한다.",
    tags: ["유해IP", "directive-gap", "방화벽"],
    evidence_ids: ["directive-2026-071", "fw-log-0182"],
    resolution: "미반영 2건 식별 → 정책 반영 승인 요청 상신 → 상급 보고 초안 작성",
    unit_id: "unit-bn-a", created_at: "2026-07-03T02:10:00Z",
  });
  opsAddKnowledge({
    source_type: "incident", source_id: "inc-20260702-004",
    title: "유출 크리덴셜 노출 시 계정 조치 분리 보고",
    summary: "크리덴셜 노출 지표 확인 시 계정 잠금·초기화는 직접 실행하지 않고 승인 분리 원칙으로 제안만 기록한다.",
    tags: ["크리덴셜유출", "계정조치", "승인분리"],
    evidence_ids: ["threat-intel-203-0-113-45"],
    resolution: "노출 계정 3건 목록화 → 계정 조치 승인 요청 → 상급 보고",
    unit_id: "unit-bn-b", created_at: "2026-07-02T11:40:00Z",
  });
  opsAddKnowledge({
    source_type: "action", source_id: "act-endpoint-isolation-002",
    title: "NAC 미준수 단말 격리 검토 상신 기준",
    summary: "posture 미준수 단말은 즉시 격리하지 않고 업무 영향 검토 후 endpoint_isolation_review 제안으로 상신한다.",
    tags: ["NAC격리", "승인절차", "posture"],
    evidence_ids: ["nac-node-10243", "endpoint-posture-10243"],
    resolution: "격리 검토 제안 1건 상신 (승인 대기)",
    unit_id: "unit-bn-b", created_at: "2026-07-02T13:05:00Z",
  });
  opsAddKnowledge({
    source_type: "aar", source_id: "aar-sct-20260703-02",
    title: "의심 outbound 우선순위 판단 기준",
    summary: "접속 장애 민원과 의심 outbound가 겹치면 outbound 근거(FW 로그·위협 IP 매칭)를 우선 확인하고 민원은 안내 초안으로 분리한다.",
    tags: ["outbound", "우선순위", "방화벽"],
    evidence_ids: ["fw-log-0182"],
    resolution: "outbound 우선 분석 → 위협 IP 매칭 확인 → 민원 별도 안내",
    unit_id: "unit-bn-a", created_at: "2026-07-03T09:20:00Z",
  });
  opsAddKnowledge({
    source_type: "inquiry", source_id: "inq-20260701-003",
    title: "지시사항 반영 확인 요청 대응 (FAQ)",
    summary: "예하 부대에서 지시 반영 여부 문의가 오면 directive 항목별 반영 상태표를 회신하고 미반영 건은 사유·예정일을 함께 안내한다.",
    tags: ["directive-gap", "FAQ", "보고"],
    evidence_ids: ["directive-2026-071"],
    resolution: "반영 상태표 회신 → 미반영 사유 회신 표준화",
    unit_id: "unit-corps-cyber", created_at: "2026-07-01T15:30:00Z",
  });

  function opsAccumulateFromIncident(inc) {
    var notes = inc.timeline
      .map(function (t) { return t.note; })
      .filter(Boolean)
      .join(" / ");
    return opsAddKnowledge({
      source_type: "incident",
      source_id: inc.incident_id,
      title: "사건 대응: " + inc.title,
      summary: "종결까지의 조치 경위 — " + (notes || "timeline 참조"),
      tags: ["사건대응", inc.severity],
      evidence_ids: inc.evidence_ids.slice(),
      resolution: "상태 전이 " + inc.timeline.length + "건, 최종 " + inc.status,
      unit_id: inc.unit_id,
    });
  }

  // 헬프데스크 (A-11) — B-12 계약 선반영. 검색(규칙) 1차 + citation 강제.
  // mock에는 LLM API가 없으므로 항상 규칙/검색 엔진으로 답한다(폴백 보장 경로).
  var opsInquirySeq = 0;
  var OPS_INQUIRIES = [];

  function opsRetrieve(question) {
    var tokens = String(question || "")
      .toLowerCase()
      .split(/[\s,.?!()\[\]{}:;'"/]+/)
      .filter(function (t) { return t.length >= 2; });
    var scored = OPS_KNOWLEDGE.map(function (k) {
      var hay = (k.title + " " + k.summary + " " + k.resolution + " " + k.tags.join(" ")).toLowerCase();
      var score = 0;
      tokens.forEach(function (t) {
        if (hay.indexOf(t) !== -1) score += 2;
        else if (t.length >= 3 && hay.indexOf(t.slice(0, -1)) !== -1) score += 1; // 조사 등 어미 제거 근사
      });
      return { item: k, score: score };
    });
    // 단어 하나짜리 우연 일치(=2점)로 grounded 처리하지 않도록 3점 이상만 채택
    return scored
      .filter(function (s) { return s.score >= 3; })
      .sort(function (a, b) { return b.score - a.score; })
      .slice(0, 2);
  }

  function opsAnswerInquiry(question) {
    var hits = opsRetrieve(question);
    if (!hits.length) {
      return {
        answer: "근거 부족 — 지식DB에서 관련 지식을 찾지 못했습니다. 담당자 확인이 필요합니다. (환각 방지를 위해 검색 범위 밖 답변은 생성하지 않습니다)",
        engine: "rule",
        confidence: "low",
        citations: { knowledge_ids: [], evidence_ids: [] },
        fallback_used: true,
        grounded: false,
      };
    }
    var top = hits[0].item;
    var evidence = [];
    var kids = hits.map(function (h) {
      h.item.evidence_ids.forEach(function (id) {
        if (evidence.indexOf(id) === -1) evidence.push(id);
      });
      return h.item.knowledge_id;
    });
    return {
      answer:
        "관련 지식 \"" + top.title + "\" 기준: " + top.summary +
        (top.resolution ? " 과거 처리: " + top.resolution + "." : "") +
        " 정책 반영·격리·계정 조치는 자동 실행이 아니라 승인 절차를 따릅니다.",
      engine: "rule",
      confidence: hits[0].score >= 6 ? "high" : "medium",
      citations: { knowledge_ids: kids, evidence_ids: evidence },
      fallback_used: false,
      grounded: true,
    };
  }

  function opsDashboardEquipment() {
    return [
      { equipment_id: "notification", label: "인앱 자동 알림", status: "normal", source_mode: "fixture", warning_count: 0, last_seen_at: opsStamp(), evidence_ids: ["directive-2026-071"] },
      { equipment_id: "operations_storage", label: "Operations 영속 저장소", status: "normal", source_mode: "memory", warning_count: 0, last_seen_at: opsStamp(), evidence_ids: [] },
      { equipment_id: "utm-fw", label: "UTM/FW 로그 수집", status: "warning", source_mode: "synthetic_adapter", warning_count: 1, last_seen_at: opsStamp(), evidence_ids: ["fw-log-0182"] },
      { equipment_id: "nac", label: "NAC 단말 통제", status: "normal", source_mode: "synthetic_adapter", warning_count: 0, last_seen_at: opsStamp(), evidence_ids: ["nac-node-10243"] },
    ];
  }

  function opsDashboardThreats() {
    return [
      {
        threat_id: "thr-stealthmole-001",
        title: "StealthMole 유출 크리덴셜 관련 지표 증가",
        summary: "masked credential exposure 지표가 계정조치 FAQ와 연결됩니다.",
        severity: "high",
        score: 82,
        tags: ["StealthMole", "credential", "account"],
        evidence_ids: ["threat-intel-203-0-113-45"],
      },
      {
        threat_id: "thr-fw-outbound-002",
        title: "의심 outbound와 유해 IP 지시 미반영 교차",
        summary: "방화벽 로그와 상급 지시 반영 상태를 함께 확인해야 합니다.",
        severity: "medium",
        score: 67,
        tags: ["outbound", "firewall", "directive-gap"],
        evidence_ids: ["fw-log-0182", "directive-2026-071"],
      },
    ];
  }

  function opsDashboardOverview(unitId) {
    var incidents = OPS_INCIDENTS.filter(function (i) { return !unitId || i.unit_id === unitId || opsDescendants(unitId).indexOf(i.unit_id) !== -1; });
    var notifications = OPS_NOTIFICATIONS.filter(function (n) { return !unitId || n.to_unit_id === unitId; });
    var openIncidents = incidents.filter(function (i) { return i.status !== "closed"; });
    var equipment = opsDashboardEquipment();
    var threats = opsDashboardThreats();
    var equipmentWarnings = equipment.reduce(function (sum, e) { return sum + e.warning_count; }, 0);
    var unacked = notifications.filter(function (n) { return !n.read; }).length;
    var posture = Math.max(0, 100 - openIncidents.length * 6 - equipmentWarnings * 4 - unacked * 2);
    var tiles = openIncidents.slice(0, 3).map(function (i) {
      return { title: i.title, severity: i.severity, source_type: "incident", metric: i.timeline.length, citations: i.evidence_ids, route: "#/ops/incidents/" + i.incident_id };
    }).concat(threats.slice(0, 2).map(function (t) {
      return { title: t.title, severity: t.severity, source_type: "threat", metric: t.score, citations: t.evidence_ids, route: "#/dashboard/threats" };
    }));
    return {
      summary: {
        posture_score: posture,
        unacked_propagations: unacked,
        open_incidents: openIncidents.length,
        equipment_warnings: equipmentWarnings,
        knowledge_items: OPS_KNOWLEDGE.length,
      },
      tiles: tiles,
      equipment: equipment,
      threats: threats,
      calendar: [
        { task_id: "cal-001", title: "상급 지시 반영 현황 재확인", due_at: "오늘 10:00", status: "진행" },
        { task_id: "cal-002", title: "야간 위협 동향 브리핑 초안", due_at: "오늘 15:30", status: "대기" },
        { task_id: "cal-003", title: "헬프데스크 상담 지식DB 후보 검토", due_at: "오늘 17:00", status: "대기" },
      ],
    };
  }

  function opsClassify(text) {
    var s = String(text || "").toLowerCase();
    if (s.indexOf("비밀번호") !== -1 || s.indexOf("패스워드") !== -1 || s.indexOf("초기화") !== -1) {
      return { category: "password_reset", priority: "medium", required_fields: ["식별번호", "계정 일치 여부"], autopilot_level: "ai_takeover_ready" };
    }
    if (s.indexOf("방화벽") !== -1 || s.indexOf("정책") !== -1 || s.indexOf("포트") !== -1) {
      return { category: "firewall_policy_request", priority: "high", required_fields: ["출발지", "목적지", "포트", "승인자"], autopilot_level: "operator_review" };
    }
    if (s.indexOf("장비") !== -1 || s.indexOf("네트워크") !== -1 || s.indexOf("접속") !== -1 || s.indexOf("장애") !== -1) {
      return { category: "network_equipment_issue", priority: "high", required_fields: ["장비/서비스", "장애 시간", "영향 범위"], autopilot_level: "operator_review" };
    }
    if (s.indexOf("침해") !== -1 || s.indexOf("악성") !== -1 || s.indexOf("신고") !== -1 || s.indexOf("감염") !== -1) {
      return { category: "incident_report", priority: "critical", required_fields: ["발견 시간", "영향 단말", "증거"], autopilot_level: "operator_review" };
    }
    return { category: "simple_question", priority: "low", required_fields: [], autopilot_level: "ai_takeover_ready" };
  }

  function conversationFromInquiry(i) {
    var cls = i.classification || opsClassify(i.question);
    return {
      conversation_id: i.conversation_id || ("conv-" + i.inquiry_id),
      inquiry_id: i.inquiry_id,
      unit_id: i.unit_id,
      question: i.question,
      answer: i.answer,
      category: cls.category,
      priority: cls.priority,
      autopilot_level: cls.autopilot_level,
      confidence: i.confidence,
      citations: i.citations,
      status: i.status,
      created_at: i.created_at,
      messages: i.messages || [],
    };
  }

  var seq = 0;
  function reqId(tag) {
    seq += 1;
    return "req-" + (tag || "mock") + "-" + ("000" + seq).slice(-4);
  }

  function ok(data, tag, warnings) {
    return {
      request_id: reqId(tag),
      data: data,
      warnings: warnings || [],
      meta: { mode: D4D.config.DEFAULT_MODE, generated_at: "2026-07-04T05:32:10Z" },
    };
  }

  function err(code, message, details) {
    return {
      request_id: reqId("err"),
      error: { code: code, message: message, retryable: false, details: details || {} },
    };
  }

  // Very small path matcher. Returns { data } envelope or { error } envelope.
  function resolve(method, path, params, body) {
    params = params || {};
    body = body || {};

    if (method === "GET" && path === "/api/training/home") {
      return ok(HOME, "home");
    }

    if (method === "GET" && path === "/api/scenarios") {
      var items = SCENARIOS.slice();
      if (params.difficulty) {
        items = items.filter(function (s) { return s.difficulty === params.difficulty; });
      }
      if (params.max_minutes) {
        items = items.filter(function (s) { return s.estimated_minutes <= Number(params.max_minutes); });
      }
      return ok({ items: items }, "scenarios");
    }

    var mScenario = path.match(/^\/api\/scenarios\/([^/]+)$/);
    if (method === "GET" && mScenario) {
      var brief = scenarioBriefing(mScenario[1]);
      if (!brief) return err("SCENARIO_NOT_FOUND", "시나리오를 찾을 수 없습니다.", { scenario_id: mScenario[1] });
      return ok(brief, "scenario");
    }

    if (method === "POST" && path === "/api/training/sessions") {
      if (!body.scenario_id) return err("BAD_REQUEST", "scenario_id가 필요합니다.");
      var newSid = "sct-20260704-01";
      sessionScenarios[newSid] = body.scenario_id;
      return ok(
        {
          session_id: newSid,
          scenario_id: body.scenario_id,
          status: "running",
          started_at: "2026-07-04T05:34:00Z",
          elapsed_seconds: 0,
          mode: body.mode || D4D.config.DEFAULT_MODE,
          visible_event_seq: 0,
          pinned_evidence_ids: [],
          current_assessment: null,
        },
        "session-start"
      );
    }

    var mSession = path.match(/^\/api\/training\/sessions\/([^/]+)$/);
    if (method === "GET" && mSession) {
      return ok(
        {
          session_id: mSession[1],
          scenario_id: sessionScenarios[mSession[1]] || "scen-main-outbound-001",
          status: "running",
          elapsed_seconds: 132,
          mode: D4D.config.DEFAULT_MODE,
          visible_event_seq: eventsFor(mSession[1]).length,
          pinned_evidence_ids: [],
          current_assessment: null,
        },
        "session"
      );
    }

    var mEvents = path.match(/^\/api\/training\/sessions\/([^/]+)\/events$/);
    if (method === "GET" && mEvents) {
      var since = Number(params.since_seq || 0);
      var evs = eventsFor(mEvents[1]).filter(function (e) { return e.seq > since; });
      return ok({ items: evs }, "events");
    }

    var mEquip = path.match(/^\/api\/training\/sessions\/([^/]+)\/equipment\/query$/);
    if (method === "POST" && mEquip) {
      var fixture = EQUIPMENT_QUERY[body.port];
      if (!fixture) return err("BAD_REQUEST", "지원하지 않는 장비 port입니다.", { port: body.port || null });
      return ok(
        {
          port: fixture.port,
          query_type: body.query_type || fixture.query_type,
          evidence: fixture.evidence,
          view_model: fixture.view_model,
        },
        "equipment-" + body.port
      );
    }

    var mAnalyze = path.match(/^\/api\/training\/sessions\/([^/]+)\/equipment\/analyze$/);
    if (method === "POST" && mAnalyze) {
      var analysis = ANALYSIS[body.port];
      if (!analysis) return err("BAD_REQUEST", "분석할 수 없는 port입니다.", { port: body.port || null });
      return ok(analysis, "analyze-" + body.port);
    }

    var mActions = path.match(/^\/api\/training\/sessions\/([^/]+)\/actions$/);
    if (method === "POST" && mActions) {
      var incoming = body.actions || [];
      if (!incoming.length) return err("BAD_REQUEST", "actions가 비어 있습니다.");
      var submitted = incoming.map(function (a, i) {
        var forced = !!FORCE_APPROVAL[a.action_type];
        var approval = forced || !!a.approval_required;
        return {
          action_id: "act-" + (a.action_type || "action") + "-" + ("00" + (i + 1)).slice(-3),
          action_type: a.action_type,
          title: a.title || "",
          target: a.target || null,
          scope: a.scope || null,
          approval_required: approval,
          approval_forced: forced,
          status: approval ? "승인 대기" : "기록됨",
          executed: false,
          evidence_ids: a.evidence_ids || [],
        };
      });
      return ok(
        { session_id: mActions[1], status: "submitted", submitted_actions: submitted, next_available: ["generate_aar"] },
        "actions"
      );
    }

    var mPins = path.match(/^\/api\/training\/sessions\/([^/]+)\/evidence\/pins$/);
    if (method === "POST" && mPins) {
      var ids = body.evidence_ids || [];
      var unknown = ids.filter(function (id) { return !KNOWN_EVIDENCE[id]; });
      if (unknown.length) return err("UNKNOWN_EVIDENCE", "존재하지 않는 근거 ID는 pin할 수 없습니다.", { unknown: unknown });
      return ok({ session_id: mPins[1], pinned_evidence_ids: ids, pinned_at: "2026-07-04T05:37:20Z" }, "pin");
    }

    var mAssess = path.match(/^\/api\/training\/sessions\/([^/]+)\/assessment$/);
    if (method === "PUT" && mAssess) {
      var evIds = body.evidence_ids || [];
      var badRef = evIds.filter(function (id) { return !KNOWN_EVIDENCE[id]; });
      if (badRef.length) return err("UNKNOWN_EVIDENCE", "존재하지 않는 근거 ID를 인용했습니다.", { unknown: badRef });
      var warns = [];
      if (HIGH_SEVERITY[body.severity] && evIds.length === 0) {
        warns.push({ code: "WEAK_SEVERITY_BASIS", message: "침해 의심 이상 심각도는 보안 근거 인용이 필요합니다." });
      }
      return ok(
        {
          session_id: mAssess[1],
          assessment: {
            priority: body.priority || null,
            severity: body.severity || null,
            response_efforts: body.response_efforts || [],
            approval_required: !!body.approval_required,
            confidence: body.confidence || null,
            rationale: body.rationale || "",
            evidence_ids: evIds,
          },
          saved_at: "2026-07-04T05:38:00Z",
        },
        "assessment",
        warns
      );
    }

    var mEvalPrev = path.match(/^\/api\/training\/sessions\/([^/]+)\/evaluation\/preview$/);
    if (method === "POST" && mEvalPrev) {
      return ok(
        {
          evaluation_id: "eval-preview-001",
          status: "draft",
          summary_strip: { priority: "적절", severity: "근거 수준 일치", response_effort: "분리됨", rubric: "단말 posture 보고 보강" },
          evidence_citations: ["fw-log-0182", "nac-node-10243", "directive-2026-071"],
          confidence: "medium",
        },
        "eval-preview",
        [{ code: "PARTIAL_EVALUATION", message: "훈련 중 미리보기이므로 최종 사후 강평 평가와 다를 수 있습니다." }]
      );
    }

    var mAarPost = path.match(/^\/api\/training\/sessions\/([^/]+)\/aar$/);
    if (method === "POST" && mAarPost) {
      var ac = aarFor(mAarPost[1]);
      return ok(
        {
          aar_id: ac.aar_id, session_id: mAarPost[1], status: "ready",
          grade: ac.grade, score: ac.score, summary: ac.summary,
          dynamic_evaluation: ac.dynamic_evaluation,
        },
        "aar-create"
      );
    }
    if (method === "GET" && mAarPost) {
      var ag = aarFor(mAarPost[1]);
      var d = {};
      Object.keys(ag).forEach(function (k) { d[k] = ag[k]; });
      d.session_id = mAarPost[1];
      return ok(d, "aar-get");
    }

    if (method === "POST" && path === "/api/ops/cases/from-training-session") {
      if (!body.session_id) return err("BAD_REQUEST", "session_id가 필요합니다.");
      var reuse = body.reuse_evidence_ids || [];
      var badReuse = reuse.filter(function (id) { return !KNOWN_EVIDENCE[id]; });
      if (badReuse.length) return err("UNKNOWN_EVIDENCE", "존재하지 않는 근거는 재사용할 수 없습니다.", { unknown: badReuse });
      return ok(
        {
          case_id: "ops-case-20260704-001",
          source_session_id: body.session_id,
          status: "draft",
          reuse_evidence_ids: reuse,
          operator_note: "사용자 접속 장애, NAC posture, FW outbound, directive gap을 같은 사건으로 검토",
          recommended_outputs: ["사용자 안내 초안", "정책 반영 요청 draft", "일일 보고 문단"],
        },
        "ops-case"
      );
    }

    if (method === "GET" && path === "/api/ops/units") {
      return ok(
        {
          items: OPS_UNITS.slice(),
          root_unit_ids: ["unit-corps-cyber"],
          default_viewer_unit_id: "unit-bn-a",
          higher_unit_id: "unit-corps-cyber",
          managed_node_count_total: 10420,
        },
        "ops-units"
      );
    }

    if (method === "POST" && path === "/api/ops/incidents") {
      if (!body.title || !String(body.title).trim()) return err("BAD_REQUEST", "title이 필요합니다.");
      if (!OPS_SEVERITIES[body.severity]) return err("BAD_REQUEST", "severity는 low/medium/high/critical 중 하나여야 합니다.");
      if (!opsUnit(body.unit_id)) return err("BAD_REQUEST", "unit_id가 올바르지 않습니다.", { unit_id: body.unit_id || null });
      var evd = body.evidence_ids || [];
      var badEvd = evd.filter(function (id) { return !KNOWN_EVIDENCE[id]; });
      if (badEvd.length) return err("UNKNOWN_EVIDENCE", "존재하지 않는 근거 ID는 인용할 수 없습니다.", { unknown: badEvd });
      var created = opsCreateIncident(body.unit_id, String(body.title).trim(), body.severity, body.note, evd);
      var incDto = {};
      Object.keys(created.incident).forEach(function (k) { incDto[k] = created.incident[k]; });
      incDto.notifications = created.notifications;
      return ok(incDto, "ops-incident-create");
    }

    if (method === "GET" && path === "/api/ops/incidents") {
      var viewer = opsUnit(params.unit_id);
      var list = OPS_INCIDENTS.slice();
      if (viewer) {
        var visible = [viewer.unit_id].concat(opsDescendants(viewer.unit_id));
        list = list.filter(function (i) { return visible.indexOf(i.unit_id) !== -1; });
      }
      if (params.status) {
        list = list.filter(function (i) { return i.status === params.status; });
      }
      return ok({ items: list }, "ops-incidents");
    }

    if (method === "GET" && path === "/api/ops/notifications") {
      var feed = OPS_NOTIFICATIONS.filter(function (n) {
        return !params.unit_id || n.to_unit_id === params.unit_id;
      });
      // 미확인 우선, 그 다음 최신순
      feed = feed.slice().sort(function (a, b) {
        if (a.read !== b.read) return a.read ? 1 : -1;
        return a.created_at < b.created_at ? 1 : -1;
      });
      var unread = feed.filter(function (n) { return !n.read; }).length;
      return ok({ items: feed, unread_count: unread }, "ops-notifications");
    }

    var mIncDetail = path.match(/^\/api\/ops\/incidents\/([^/]+)$/);
    if (method === "GET" && mIncDetail) {
      var incD = opsIncidentById(mIncDetail[1]);
      if (!incD) return err("NOT_FOUND", "사건을 찾을 수 없습니다.", { incident_id: mIncDetail[1] });
      return ok(opsIncidentDto(incD), "ops-incident");
    }

    var mIncTimeline = path.match(/^\/api\/ops\/incidents\/([^/]+)\/timeline$/);
    if (method === "GET" && mIncTimeline) {
      var incT = opsIncidentById(mIncTimeline[1]);
      if (!incT) return err("NOT_FOUND", "사건을 찾을 수 없습니다.", { incident_id: mIncTimeline[1] });
      return ok({ incident_id: incT.incident_id, items: incT.timeline.slice() }, "ops-timeline");
    }

    var mIncStatus = path.match(/^\/api\/ops\/incidents\/([^/]+)\/status$/);
    if (method === "POST" && mIncStatus) {
      var incS = opsIncidentById(mIncStatus[1]);
      if (!incS) return err("NOT_FOUND", "사건을 찾을 수 없습니다.", { incident_id: mIncStatus[1] });
      if (body.actor_unit_id !== incS.unit_id) {
        return err("FORBIDDEN", "상태 전이는 해당(발생) 부대만 수행할 수 있습니다. 상급 부대는 읽기 전용입니다.", {
          incident_unit_id: incS.unit_id, actor_unit_id: body.actor_unit_id || null,
        });
      }
      var allowed = OPS_TRANSITIONS[incS.status] || [];
      if (allowed.indexOf(body.to_status) === -1) {
        return err("INVALID_TRANSITION", "허용되지 않는 상태 전이입니다.", {
          from: incS.status, to: body.to_status || null, allowed: allowed,
        });
      }
      var evdS = body.evidence_ids || [];
      var badEvdS = evdS.filter(function (id) { return !KNOWN_EVIDENCE[id]; });
      if (badEvdS.length) return err("UNKNOWN_EVIDENCE", "존재하지 않는 근거 ID는 인용할 수 없습니다.", { unknown: badEvdS });

      var entry = {
        at: opsStamp(),
        from: incS.status,
        to: body.to_status,
        actor_unit: incS.unit_id,
        note: body.note || "",
        evidence_ids: evdS,
      };
      incS.status = body.to_status;
      incS.timeline.push(entry);
      var statusNtf = opsNotify(incS, "status_changed", false);
      // 종결 시 자동 지식 축적 (설계 §2.2 — 담당자와 무관하게 비휘발)
      var accumulated = incS.status === "closed" ? opsAccumulateFromIncident(incS) : null;
      return ok(
        {
          incident_id: incS.incident_id,
          status: incS.status,
          approval_required: body.to_status === "needs_approval",
          executed: false,
          timeline_entry: entry,
          notifications: statusNtf,
          allowed_transitions: (OPS_TRANSITIONS[incS.status] || []).slice(),
          accumulated_knowledge_id: accumulated ? accumulated.knowledge_id : null,
        },
        "ops-status"
      );
    }

    if (method === "GET" && path === "/api/ops/status-board") {
      var boardViewer = opsUnit(params.unit_id);
      if (!boardViewer) return err("BAD_REQUEST", "unit_id가 올바르지 않습니다.", { unit_id: params.unit_id || null });
      var subs = opsDescendants(boardViewer.unit_id);
      var boardItems = OPS_INCIDENTS
        .filter(function (i) { return subs.indexOf(i.unit_id) !== -1 || i.unit_id === boardViewer.unit_id; })
        .map(function (i, idx) {
          return {
            incident_id: i.incident_id,
            unit_id: i.unit_id,
            title: i.title,
            status: i.status,
            severity: i.severity,
            elapsed_seconds: 600 * (idx + 1),
            last_transition: opsLastTransition(i),
          };
        });
      return ok(
        { viewer_unit_id: boardViewer.unit_id, subordinate_units: subs, incidents: boardItems },
        "ops-status-board"
      );
    }

    if (method === "GET" && path === "/api/dashboard/overview") {
      return ok(opsDashboardOverview(params.unit_id || null), "dashboard-overview");
    }

    if (method === "GET" && path === "/api/dashboard/equipment") {
      return ok({ items: opsDashboardEquipment() }, "dashboard-equipment");
    }

    if (method === "GET" && path === "/api/dashboard/threats") {
      return ok({ items: opsDashboardThreats() }, "dashboard-threats");
    }

    if (method === "GET" && path === "/api/dashboard/posture") {
      return ok({ score: opsDashboardOverview(null).summary.posture_score, status: "watch" }, "dashboard-posture");
    }

    if (method === "GET" && path === "/api/dashboard/calendar") {
      return ok({ items: opsDashboardOverview(null).calendar }, "dashboard-calendar");
    }

    if (method === "GET" && path === "/api/dashboard/propagation") {
      var prop = OPS_NOTIFICATIONS.slice();
      if (params.unit_id) prop = prop.filter(function (n) { return n.to_unit_id === params.unit_id; });
      return ok({ items: prop, unread_count: prop.filter(function (n) { return !n.read; }).length }, "dashboard-propagation");
    }

    if (method === "GET" && (path === "/api/knowledge" || path === "/api/knowledge/search")) {
      var kItems = OPS_KNOWLEDGE.slice();
      if (params.query || params.q) {
        var q = String(params.query || params.q).toLowerCase();
        kItems = kItems.filter(function (k) {
          return (k.title + " " + k.summary + " " + k.resolution + " " + k.tags.join(" ")).toLowerCase().indexOf(q) !== -1;
        });
      }
      if (params.source_type) {
        kItems = kItems.filter(function (k) { return k.source_type === params.source_type; });
      }
      if (params.tags) {
        var wanted = String(params.tags).split(",").map(function (t) { return t.trim(); }).filter(Boolean);
        kItems = kItems.filter(function (k) {
          return wanted.some(function (t) { return k.tags.indexOf(t) !== -1; });
        });
      }
      if (params.unit_id) {
        kItems = kItems.filter(function (k) { return k.unit_id === params.unit_id; });
      }
      // 대시보드 집계는 필터와 무관하게 전체 기준
      var tagCounts = {};
      var srcCounts = {};
      var unitCounts = {};
      OPS_KNOWLEDGE.forEach(function (k) {
        k.tags.forEach(function (t) { tagCounts[t] = (tagCounts[t] || 0) + 1; });
        srcCounts[k.source_type] = (srcCounts[k.source_type] || 0) + 1;
        if (k.unit_id) unitCounts[k.unit_id] = (unitCounts[k.unit_id] || 0) + 1;
      });
      var topTags = Object.keys(tagCounts)
        .map(function (t) { return { tag: t, count: tagCounts[t] }; })
        .sort(function (a, b) { return b.count - a.count; })
        .slice(0, 8);
      return ok(
        {
          items: kItems,
          total: OPS_KNOWLEDGE.length,
          top_tags: topTags,
          by_source: srcCounts,
          by_unit: unitCounts,
          query: params.query || params.q || null,
          source_type: params.source_type || null,
        },
        "knowledge"
      );
    }

    var mKb = path.match(/^\/api\/knowledge\/([^/]+)$/);
    if (method === "GET" && mKb) {
      var kbHit = null;
      OPS_KNOWLEDGE.forEach(function (k) { if (k.knowledge_id === mKb[1]) kbHit = k; });
      if (!kbHit) return err("NOT_FOUND", "지식을 찾을 수 없습니다.", { knowledge_id: mKb[1] });
      return ok(kbHit, "knowledge-item");
    }

    if (method === "POST" && path === "/api/knowledge") {
      if (!body.title || !body.summary) return err("BAD_REQUEST", "title과 summary가 필요합니다.");
      var evdK = body.evidence_ids || [];
      var badEvdK = evdK.filter(function (id) { return !KNOWN_EVIDENCE[id]; });
      if (badEvdK.length) return err("UNKNOWN_EVIDENCE", "존재하지 않는 근거 ID는 인용할 수 없습니다.", { unknown: badEvdK });
      var manual = opsAddKnowledge({
        source_type: "manual",
        source_id: "manual-" + (OPS_KNOWLEDGE.length + 1),
        title: String(body.title).trim(),
        summary: String(body.summary).trim(),
        tags: body.tags || [],
        evidence_ids: evdK,
        resolution: body.resolution || "",
        unit_id: body.unit_id || null,
      });
      return ok(manual, "knowledge-manual");
    }

    if (method === "POST" && path === "/api/helpdesk/inquiries") {
      if (!body.question || !String(body.question).trim()) return err("BAD_REQUEST", "question이 필요합니다.");
      if (body.unit_id && !opsUnit(body.unit_id)) return err("BAD_REQUEST", "unit_id가 올바르지 않습니다.", { unit_id: body.unit_id });
      opsInquirySeq += 1;
      var ansI = opsAnswerInquiry(body.question);
      var inq = {
        inquiry_id: "inq-" + ("00" + opsInquirySeq).slice(-3),
        unit_id: body.unit_id || null,
        question: String(body.question).trim(),
        answer: ansI.answer,
        engine: ansI.engine,
        confidence: ansI.confidence,
        citations: ansI.citations,
        fallback_used: ansI.fallback_used,
        grounded: ansI.grounded,
        status: ansI.grounded ? "answered" : "needs_review",
        created_at: opsStamp(),
        linked_knowledge_ids: ansI.citations.knowledge_ids.slice(),
      };
      OPS_INQUIRIES.push(inq);
      return ok(inq, "helpdesk-inquiry");
    }

    if (method === "POST" && path === "/api/helpdesk/conversations") {
      var message = body.question || body.message;
      if (!message || !String(message).trim()) return err("BAD_REQUEST", "message가 필요합니다.");
      if (body.unit_id && !opsUnit(body.unit_id)) return err("BAD_REQUEST", "unit_id가 올바르지 않습니다.", { unit_id: body.unit_id });
      opsInquirySeq += 1;
      var ansC = opsAnswerInquiry(message);
      var clsC = opsClassify(message);
      var convInq = {
        inquiry_id: "inq-" + ("00" + opsInquirySeq).slice(-3),
        conversation_id: "conv-inq-" + ("00" + opsInquirySeq).slice(-3),
        unit_id: body.unit_id || null,
        question: String(message).trim(),
        answer: ansC.answer,
        engine: ansC.engine,
        confidence: ansC.confidence,
        citations: ansC.citations,
        fallback_used: ansC.fallback_used,
        grounded: ansC.grounded,
        status: ansC.grounded ? "answered" : "needs_review",
        created_at: opsStamp(),
        linked_knowledge_ids: ansC.citations.knowledge_ids.slice(),
        classification: clsC,
      };
      convInq.messages = [
        { role: "user", text: convInq.question, at: convInq.created_at },
        { role: "assistant", text: convInq.answer, at: convInq.created_at, engine: convInq.engine },
      ];
      OPS_INQUIRIES.push(convInq);
      return ok({ conversation_id: convInq.conversation_id, conversation: conversationFromInquiry(convInq), classification: clsC }, "helpdesk-conv-create");
    }

    if (method === "GET" && path === "/api/helpdesk/inquiries") {
      var inqList = OPS_INQUIRIES.slice();
      if (params.unit_id) inqList = inqList.filter(function (i) { return i.unit_id === params.unit_id; });
      if (params.status) inqList = inqList.filter(function (i) { return i.status === params.status; });
      inqList = inqList.slice().reverse();
      return ok({ items: inqList }, "helpdesk-list");
    }

    if (method === "GET" && path === "/api/helpdesk/conversations") {
      var convList = OPS_INQUIRIES.slice();
      if (params.unit_id) convList = convList.filter(function (i) { return i.unit_id === params.unit_id; });
      if (params.status) convList = convList.filter(function (i) { return i.status === params.status; });
      return ok({ items: convList.slice().reverse().map(conversationFromInquiry) }, "helpdesk-conv-list");
    }

    var mConv = path.match(/^\/api\/helpdesk\/conversations\/([^/]+)\/(workbench|classify|draft-answer|resolve)$/);
    if (mConv) {
      var convHit = null;
      OPS_INQUIRIES.forEach(function (i) {
        if ((i.conversation_id || ("conv-" + i.inquiry_id)) === mConv[1]) convHit = i;
      });
      if (!convHit) return err("NOT_FOUND", "상담을 찾을 수 없습니다.", { conversation_id: mConv[1] });
      var convCls = convHit.classification || opsClassify(convHit.question);
      if (method === "GET" && mConv[2] === "workbench") {
        return ok({
          conversation: conversationFromInquiry(convHit),
          classification: convCls,
          related_knowledge: opsRetrieve(convHit.question).map(function (h) { return h.item; }),
          suggested_answer: convHit.answer,
          suggested_actions: [{ action_type: convCls.category === "password_reset" ? "identity_check" : "knowledge_grounded_reply", summary: "승인 절차와 지식DB 근거를 확인합니다.", required_approval: convCls.category !== "simple_question", executed: false }],
        }, "helpdesk-conv-workbench");
      }
      if (method === "POST" && mConv[2] === "classify") return ok(convCls, "helpdesk-conv-classify");
      if (method === "POST" && mConv[2] === "draft-answer") {
        return ok({ conversation_id: mConv[1], answer: convHit.answer, engine: convHit.engine, citations: convHit.citations }, "helpdesk-conv-draft");
      }
      if (method === "POST" && mConv[2] === "resolve") {
        convHit.status = "resolved";
        var kbFromConv = opsAddKnowledge({
          source_type: "inquiry",
          source_id: convHit.inquiry_id,
          title: "FAQ: " + convHit.question.slice(0, 60),
          summary: convHit.answer,
          tags: ["FAQ", "헬프데스크"],
          evidence_ids: convHit.citations.evidence_ids.slice(),
          resolution: "담당자 검토 후 해결 처리",
          unit_id: convHit.unit_id,
        });
        return ok({ conversation_id: mConv[1], inquiry_id: convHit.inquiry_id, status: "resolved", accumulated_knowledge_id: kbFromConv.knowledge_id }, "helpdesk-conv-resolve");
      }
    }

    var mInqResolve = path.match(/^\/api\/helpdesk\/inquiries\/([^/]+)\/resolve$/);
    if (method === "POST" && mInqResolve) {
      var inqHit = null;
      OPS_INQUIRIES.forEach(function (i) { if (i.inquiry_id === mInqResolve[1]) inqHit = i; });
      if (!inqHit) return err("NOT_FOUND", "문의를 찾을 수 없습니다.", { inquiry_id: mInqResolve[1] });
      if (inqHit.status === "resolved") return err("BAD_REQUEST", "이미 해결 처리된 문의입니다.", { inquiry_id: inqHit.inquiry_id });
      inqHit.status = "resolved";
      // 해결된 문의는 FAQ 지식으로 자동 축적 (설계 §2.2)
      var kbFromInq = opsAddKnowledge({
        source_type: "inquiry",
        source_id: inqHit.inquiry_id,
        title: "FAQ: " + inqHit.question.slice(0, 60),
        summary: inqHit.answer,
        tags: ["FAQ", "헬프데스크"],
        evidence_ids: inqHit.citations.evidence_ids.slice(),
        resolution: "담당자 검토 후 해결 처리",
        unit_id: inqHit.unit_id,
      });
      return ok(
        { inquiry_id: inqHit.inquiry_id, status: "resolved", accumulated_knowledge_id: kbFromInq.knowledge_id },
        "helpdesk-resolve"
      );
    }

    var mNtfAck = path.match(/^\/api\/ops\/notifications\/([^/]+)\/ack$/);
    if (method === "POST" && mNtfAck) {
      var target = null;
      OPS_NOTIFICATIONS.forEach(function (n) { if (n.notification_id === mNtfAck[1]) target = n; });
      if (!target) return err("NOT_FOUND", "알림을 찾을 수 없습니다.", { notification_id: mNtfAck[1] });
      target.read = true;
      return ok({ notification_id: target.notification_id, read: true }, "ops-ntf-ack");
    }

    if (method === "GET" && path === "/api/adapters/status") {
      return ok(
        {
          items: [
            { port: "utm_firewall", mode: D4D.config.DEFAULT_MODE, status: "available" },
            { port: "nac", mode: D4D.config.DEFAULT_MODE, status: "available" },
            { port: "directive", mode: D4D.config.DEFAULT_MODE, status: "available" },
            { port: "threat_intel", mode: D4D.config.DEFAULT_MODE, status: "available", fallback_reason: null },
          ],
        },
        "adapters"
      );
    }

    return err("NOT_IMPLEMENTED", "이 endpoint는 이후 티켓(B-track)에서 제공됩니다.", { method: method, path: path });
  }

  D4D.mock = { resolve: resolve, EQUIPMENT_LABELS: EQUIPMENT_LABELS };
})(window.D4D);
