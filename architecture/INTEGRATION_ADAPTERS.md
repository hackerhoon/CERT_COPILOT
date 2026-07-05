# 사이버방호 체계 연동 어댑터 설계

> 상태: 설계 원칙
> 최종 업데이트: 2026-07-04 KST
> 범위: 실제 사이버방호 체계와 시나리오 목업을 같은 인터페이스로 연결하기 위한 포트/어댑터 구조

## 1. 설계 결정

`Cyber Defense Readiness Copilot`은 내부 통제용 NAC, UTM/FW, 방화벽 정책 관리 체계, 계정/IAM, 지시사항 저장소 같은 체계를 직접 UI나 에이전트에 붙이지 않는다.

모든 외부/목업 체계는 `integration-adapters` 계층 뒤에 둔다.

```text
Training Mode / Operations Mode
  -> evidence-core
  -> integration-adapters
  -> real adapter 또는 scenario mock adapter
  -> normalized evidence / recommendation input
```

핵심 원칙:
- 같은 포트가 실제 제품 어댑터와 시나리오용 목업 어댑터를 모두 지원한다.
- UI와 copilot은 원천 체계의 세부 API, DB 구조, 제품명을 직접 알지 않는다.
- Training Mode는 기본적으로 sanitized fixture/mock adapter를 사용한다.
- Operations Mode는 배치 환경에 따라 mock, live-readonly, approval-gated live adapter를 사용할 수 있다.
- 정책 변경, 계정 조치, 단말 격리 같은 행위는 기본적으로 `proposal`만 생성하고 human approval 뒤에만 실행 가능하게 설계한다.

## 2. 현장 경험이 강제하는 요구사항

공개 데모에서는 모든 외부 연동을 adapter 뒤에 두어 fixture, mock, readonly, approval-gated 모드를 교체할 수 있게 한다.

현장에서 마주한 업무는 한 시스템 안에서 끝나지 않았다.

- UTM/FW 로그를 보고 이상 징후를 확인한다.
- Genian NAC 같은 내부 통제용 NAC에서 사용자, 노드, Agent, 고정 IP 관리대장, 정책 위반 상태를 본다.
- 방화벽 정책과 상위 조직제대 유해 IP 전파 목록이 일치하는지 확인한다.
- 계정 잠김, 업무용 홈페이지 접근 장애, 보안 정책 위반 민원을 받으면 IAM, 네트워크 경로, 정책, 단말 posture를 함께 확인한다.
- 일/주 단위 보고를 위해 근거, 조치, 미해결 사항을 다시 모은다.

따라서 제품은 단순 챗봇이나 단일 로그 뷰어가 아니라, 여러 체계의 단서를 같은 근거 모델로 모으는 작업대여야 한다.

## 3. 어댑터 모드

| 모드 | 용도 | 허용 범위 |
|---|---|---|
| `fixture` | 해커톤 데모와 테스트 | 정적 JSON/SQLite/CSV 기반, 완전 synthetic 데이터 |
| `mock` | 시나리오 재생 | 시간순 이벤트, 지연, 장애, 누락 정책 등을 재현 |
| `live-readonly` | 실제 제품 조회 연동 | 읽기 전용 조회, 마스킹/정규화 필수 |
| `live-approval-gated` | 제한적 조치 연동 | 사람이 승인한 조치만 실행, audit log 필수 |

해커톤 기본값은 `fixture` 또는 `mock`이다. live 모드는 발표에서 "가능한 확장 경로"로 설명하되, 실제 키나 민감 데이터를 노출하지 않는다.

## 4. 필수 포트

| 포트 | 실제 연동 후보 | 목업/시나리오 역할 | 정규화 출력 |
|---|---|---|---|
| `IdentityPort` | 계정/IAM/디렉터리 | 계정 잠김, 비밀번호 초기화 가능 여부 | `UserEvidence`, `AccountStatus` |
| `NacPort` | Genian NAC 같은 내부 통제용 NAC, 단말 인증/접속 통제, 노드/IP 관리대장 | 대규모 synthetic 노드 식별, Agent check-in, 고정 IP 대장 대조, 격리 여부, 정책 위반 상태 | `NacNodeEvidence`, `EndpointComplianceEvidence`, `StaticIpLedgerEvidence` |
| `UtmFirewallPort` | AhnLab TrusGuard 같은 UTM/FW, 로그 저장소, 정책 관리 화면 | 방화벽 정책, 로그 검색, 로그 ID 역추적, 블랙리스트 반영 여부 | `FirewallPolicyEvidence`, `SecurityEventEvidence`, `BlacklistComplianceEvidence` |
| `FirewallPolicyPort` | 방화벽 정책 관리 체계 | 정책 조회, blacklist 반영 여부, 변경 요청 비교 | `PolicyEvidence`, `PolicyDiff` |
| `DirectivePort` | 상위 조직제대 지시사항, 유해 IP 목록 | 필수 차단 지시와 마감 시한 | `DirectiveEvidence` |
| `TopologyPort` | 네트워크/조직 간 연결 관계 | 업무용 홈페이지 접근 장애 원인 후보 | `PathEvidence` |
| `TicketPort` | 민원/요청 접수 창구 | 계정, 접속, 보안 예외, 피싱 신고 | `RequestEvidence` |
| `PhishingDrillPort` | 해킹메일 훈련 관리 자료 | 클릭/신고/미응답 통계 | `TrainingEvidence` |
| `ThreatIntelPort` | OSINT, StealthMole | 외부 IP/domain/account 위험 보강 | `ThreatIntelEvidence` |

## 5. 인터페이스 초안

```ts
type AdapterMode = "fixture" | "mock" | "live-readonly" | "live-approval-gated";

type AdapterContext = {
  runId?: string;
  caseId?: string;
  mode: AdapterMode;
  requesterRole: "trainee" | "operator" | "instructor" | "system";
  redactionLevel: "demo" | "internal" | "strict";
};

type NormalizedEvidence = {
  id: string;
  sourcePort: string;
  sourceId: string;
  sourceMode: AdapterMode;
  claim: string;
  confidence: "low" | "medium" | "high";
  relatedEntityIds: string[];
  observedAt?: string;
  caveat?: string;
};

interface CyberDefenseAdapterPort<TQuery, TResult extends NormalizedEvidence> {
  portName: string;
  mode: AdapterMode;
  query(context: AdapterContext, query: TQuery): Promise<TResult[]>;
  healthCheck?(): Promise<{ ok: boolean; detail?: string }>;
}
```

TrusGuard형 UTM/FW 어댑터는 다음 쿼리를 우선 지원한다.

```ts
type FirewallLogQuery = {
  timeRange: { from: string; to: string };
  sessionState?: "allowed" | "blocked" | "closed";
  protocol?: "tcp" | "udp" | "icmp" | "ip";
  logId?: string;
  source?: { ip?: string; port?: number };
  destination?: { ip?: string; port?: number };
  natType?: "SNAT" | "DNAT";
};

type FirewallPolicyQuery = {
  enabled?: boolean;
  source?: string;
  destination?: string;
  service?: string;
  action?: "allow" | "block" | "security_grade" | "ipsec_vpn_allow";
  logId?: string;
};

type BlacklistComplianceQuery = {
  indicators: string[];
  requiredAction: "block" | "allow_exception";
  scopeNetworks?: string[];
};
```

TrusGuard형 fixture의 핵심 필드:
- 방화벽 정책: `enabled`, `priority`, `source`, `destination`, `service`, `action`, `schedule`, `log_enabled`, `log_id`, `ips_linked`, `qos`, `session_limit`, `description`.
- 방화벽 로그: `session_state`, `protocol`, `log_id`, `source_ip`, `source_port`, `destination_ip`, `destination_port`, `nat_type`, `translated_ip`, `bytes`, `packets`.
- 블랙리스트 compliance: `indicator`, `required_action`, `reflected_policy_ids`, `missing_networks`, `status`.

Genian NAC형 어댑터는 다음 쿼리를 우선 지원한다.

```ts
type NacNodeQuery = {
  ip?: string;
  mac?: string;
  hostname?: string;
  userId?: string;
  unit?: string;
  networkSegment?: string;
  ipAssignmentState?: "matched" | "mismatched" | "unregistered" | "duplicate" | "unknown";
  agentStatus?: "healthy" | "stale" | "not_installed" | "install_required" | "unknown";
  accessState?: "allowed" | "blocked" | "isolated" | "limited" | "unknown";
  complianceState?: "compliant" | "non_compliant" | "unknown";
  lastSeenWithinHours?: number;
};

type IpAttributionQuery = {
  ip: string;
  observedAt: string;
};

type StaticIpLedgerQuery = {
  ip?: string;
  mac?: string;
  unit?: string;
  status?: "active" | "expired" | "pending" | "revoked";
};
```

Genian NAC형 fixture의 핵심 필드:
- 노드: `node_id`, `hostname`, `ip`, `mac`, `assigned_static_ip`, `static_ip_ledger_id`, `ip_assignment_state`, `unit`, `department`, `network_segment`, `sensor_id`, `policy_server_id`, `switch_name`, `switch_port`, `user_id`.
- Agent: `agent_installed`, `agent_status`, `agent_last_check_in_at`, `endpoint_posture`, `collected_os`, `collected_software`, `collected_av_status`.
- 정책/접근 제어: `policy_group_ids`, `node_policy_id`, `enforcement_policy_id`, `access_state`, `compliance_state`, `violation_ids`, `radius_vlan`, `cwp_redirect_required`.
- 고정 IP 관리대장: `ledger_id`, `assigned_ip`, `expected_mac`, `expected_hostname`, `owner_user_id`, `approval_ref`, `valid_from`, `valid_to`, `status`.
- 규모 메타데이터: `total_nodes`, `unit_count`, `network_segment_count`, `stale_agent_count`, `unmatched_static_ip_count`.

StealthMole형 ThreatIntelPort는 다음 쿼리를 우선 지원한다.

```ts
type ThreatIntelQuery = {
  indicatorType: "ip" | "domain" | "url" | "email" | "id" | "hash" | "keyword";
  indicator: string;
  modules?: Array<"cl" | "cds" | "cb" | "tt" | "cdf" | "rm" | "gm" | "lm">;
  scenarioId?: string;
  maxSamples?: number;
  mode: "fixture" | "mock" | "live-readonly";
};

type ThreatIntelEvidence = NormalizedEvidence & {
  sourcePort: "ThreatIntelPort";
  provider: "stealthmole" | "osint-fixture";
  modulesUsed: string[];
  indicatorType: ThreatIntelQuery["indicatorType"];
  indicatorMasked: string;
  riskLevel: "none" | "low" | "medium" | "high" | "unknown";
  riskScore?: number;
  counts: Record<string, number>;
  maskedSamples: Array<{
    module: string;
    label: string;
    observedAt?: string;
    maskedValue?: string;
  }>;
  scenarioUse: "priority" | "directive_validation" | "credential_exposure" | "report_context";
  rawStored: false;
};
```

ThreatIntel fixture의 핵심 필드:
- `run_id`, `generated_at`, `profile`, `provider`.
- `quota_summary`: `/user/quotas` 기반 service별 allowed/used/remaining.
- `indicator_enrichment`: indicator type, masked indicator, modules used, risk level, counts, masked samples.
- `scenario_links`: 연결된 `scenario_id`, `inject_id`, `evidence_id`, `use_reason`.
- `safety`: `sanitized=true`, `raw_saved=false`, `contains_raw_credential=false`.

운영 규칙:
- `ThreatIntelPort`는 raw API response를 반환하지 않는다.
- UI, AAR, 보고서는 `indicatorMasked`, `counts`, `maskedSamples`, `claim`, `caveat`만 사용한다.
- live mode는 항상 `/user/quotas` smoke test 뒤에 시작하고, 실패하면 fixture/mock으로 fallback한다.
- external intel은 내부 침해 단정 근거가 아니라 우선순위, 지시사항 검증, 보고 맥락 보강 근거로만 사용한다.

조치형 인터페이스는 별도로 분리한다.

```ts
type ActionProposal = {
  id: string;
  actionType: "account_reset" | "policy_change_request" | "endpoint_isolation_request" | "user_guidance" | "report";
  rationale: string;
  evidenceIds: string[];
  approvalRequired: true;
};
```

## 6. 훈련과 운영의 재사용 방식

훈련 시나리오:
- `mock` 어댑터가 UTM/FW 이벤트, TrusGuard형 방화벽 정책, 로그 ID, Genian NAC형 노드/IP/Agent 상태, AV 미업데이트, 유해 IP/블랙리스트 반영 누락을 시간순으로 노출한다.
- 훈련생은 실제 업무처럼 근거를 조회하지만 모든 데이터는 synthetic이다.
- AAR은 어떤 포트를 조회했고 어떤 근거를 놓쳤는지 평가한다.

운영 보조:
- 같은 쿼리와 같은 `NormalizedEvidence` 모델을 사용한다.
- 배치 환경에서 실제 제품 연동이 가능하면 `live-readonly` 어댑터를 붙인다.
- 조치가 필요한 경우 즉시 실행하지 않고 `ActionProposal`과 보고 초안을 생성한다.

## 7. 안전 경계

- 실제 네트워크 주소, 실제 정책명, 실제 로그 원문, 실제 식별번호은 저장소/데모/발표에 넣지 않는다.
- live adapter는 기본적으로 읽기 전용이다.
- write 계열 조치는 모두 human approval과 audit log를 요구한다.
- StealthMole 등 외부 threat intel은 raw response를 그대로 보여 주지 않고 sanitized evidence로 변환한다.
- 시나리오 목업은 실제 제품명을 과도하게 특정하지 않고, 제품군 수준의 역할만 표현한다.

## 8. 구현 우선순위

해커톤에서는 다음 순서로 구현한다.

1. `fixture` 기반 `UtmFirewallPort`, `DirectivePort`.
2. `NacPort` fixture를 추가해 Genian NAC형 대규모 synthetic 노드, 고정 IP 관리대장, Agent check-in, 단말 통제/정책 위반 상태를 시나리오에 반영.
3. `ThreatIntelPort` fixture를 추가해 StealthMole sanitized indicator enrichment를 메인 시나리오에 반영.
4. `EvidenceCore`가 모든 포트 결과를 `NormalizedEvidence`로 합치는 경로.
5. Operations Mode가 같은 포트를 조회해 민원 해결 근거를 보여 주는 얇은 뷰.
6. live-readonly adapter는 시간이 남을 때만 stub 또는 인터페이스 수준으로 제시.
