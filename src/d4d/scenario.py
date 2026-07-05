"""Build defensive cyber-readiness training scenarios from collected intel.

This turns sanitized StealthMole view models into T5 training scenarios that
follow the domain model in `architecture/SYSTEM_ARCHITECTURE.md` (§7). The
scenarios are strictly **defensive**: injects present observable clues from
real threat intel, and the expected trainee actions are detection, triage,
containment-request, and reporting — never offensive/exploit steps.

Safety:
- Real personal data is never embedded. Credential evidence is expressed as
  masked samples and aggregate counts carried over from `sanitize.py`.
- Unit context is synthetic (a mock domain / mock assets), so a scenario is a
  safe replay of the operational workflow, not a copy of real accounts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# Synthetic unit context — never a real unit/domain/asset.
MOCK_DOMAIN = "mock-unit.example.mil"
MOCK_ASSET = "MOCK-WS-014"
MOCK_UNIT = "제00정보통신단 보안 관제 조직 (모의)"

SAFETY_NOTE = (
    "방어 훈련용 시나리오입니다. 관측·분석·차단요청·보고 절차만 다루며, "
    "실제 공격/침투 수행 절차나 악성코드 제작 내용은 포함하지 않습니다. "
    "조직·자산·계정은 합성값이고 외부 지표는 마스킹된 위협 인텔입니다."
)


@dataclass
class Evidence:
    """A cited, masked fact drawn from a collected view model (arch §7)."""

    id: str
    source_type: str  # e.g. "stealthmole:cl"
    claim: str
    confidence: str  # high | medium | low
    caveat: str = ""


@dataclass
class Inject:
    """One timed event in the scenario timeline (arch §7)."""

    seq: int
    offset_min: int
    source_system: str
    visible_clue: str
    hidden_truth: str
    related_entities: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class ExpectedAction:
    """A defensive action the trainee is expected to take."""

    order: int
    action: str
    rationale: str
    evidence_ids: list[str] = field(default_factory=list)
    approval_required: bool = False


@dataclass
class Scenario:
    """A defensive training scenario (arch §7 Scenario + AAR rubric)."""

    id: str
    title: str
    objective: str
    difficulty: str
    threat_context: str
    injects: list[Inject]
    expected_actions: list[ExpectedAction]
    rubric: list[str]
    evidence: list[Evidence]
    safety_note: str = SAFETY_NOTE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# -- helpers ------------------------------------------------------------


def _fmt(n: Any) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


def _first_sample(view: dict[str, Any]) -> dict[str, Any]:
    samples = (view or {}).get("samples") or []
    return samples[0] if samples else {}


def _targets(view: dict[str, Any]) -> list[str]:
    values = (view or {}).get("targets") or []
    return [str(v) for v in values if v]


def _has_collected_intel(run: dict[str, Any]) -> bool:
    return any(
        run.get(key)
        for key in (
            "ransomware_rm",
            "government_gm",
            "leaked_lm",
            "tt_targets_ip",
            "tt_targets_domain",
            "cdf_targets_ip",
            "cl_search",
            "cds_search",
            "tt_search_domain",
        )
    )


# -- scenario builders --------------------------------------------------


def build_main_demo_enrichment_scenario(run: dict[str, Any]) -> Scenario | None:
    """Main T5 demo scenario with StealthMole enrichment attached.

    This is the concrete bridge between the fixed demo in
    `submission/DEMO_SCENARIO_AAR.md` and live/sanitized StealthMole data. The
    internal workflow remains synthetic: StealthMole only increases realism for
    the external indicator, credential-risk, and harmful-IP directive evidence.
    """
    if not _has_collected_intel(run):
        return None

    cl = run.get("cl_search") or {}
    cds = run.get("cds_search") or {}
    rm = run.get("ransomware_rm") or {}
    lm = run.get("leaked_lm") or {}
    gm = run.get("government_gm") or {}
    tt_ip_targets = _targets(run.get("tt_targets_ip") or {})
    cdf_ip_targets = _targets(run.get("cdf_targets_ip") or {})

    cds_sample = _first_sample(cds)
    masked_external_ip = cds_sample.get("ip", "203.0.113.x")
    masked_host = cds_sample.get("host", "https://login.example-service.com")
    pivot_label = ", ".join((tt_ip_targets + cdf_ip_targets)[:4]) or "ip/domain pivot targets"

    threat_fragments = []
    if cl:
        threat_fragments.append(f"CL {_fmt(cl.get('totalCount', 0))} credential hits")
    if cds:
        threat_fragments.append(f"CDS {_fmt(cds.get('totalCount', 0))} stealer-related hits")
    if rm:
        threat_fragments.append(f"RM {_fmt(rm.get('totalCount', 0))} ransomware observations")
    if lm:
        threat_fragments.append(f"LM {_fmt(lm.get('totalCount', 0))} leaked-monitoring posts")
    if gm:
        threat_fragments.append(f"GM {_fmt(gm.get('totalCount', 0))} government-monitoring posts")
    if tt_ip_targets or cdf_ip_targets:
        threat_fragments.append(f"TT/CDF pivot targets: {pivot_label}")
    threat_summary = "; ".join(threat_fragments) or "StealthMole sanitized threat-intel signals available"

    evidence = [
        Evidence(
            id="EV-MAIN-TI-1",
            source_type="stealthmole:sanitized",
            claim=(
                "StealthMole sanitized run provides external threat context for the demo indicator: "
                f"{threat_summary}."
            ),
            confidence="medium",
            caveat="External intel is used only as enrichment; internal unit, asset, IP, and policy data remain synthetic.",
        ),
        Evidence(
            id="EV-MAIN-FW-1",
            source_type="mock:trusguard",
            claim=(
                "TrusGuard-like log FW-20260704-0182 shows mixed blocked/allowed outbound sessions "
                f"from synthetic source 10.23.14.52 toward masked external indicator {masked_external_ip}."
            ),
            confidence="high",
            caveat="Firewall log is a public-safe mock record shaped after TrusGuard-like fields.",
        ),
        Evidence(
            id="EV-MAIN-NAC-1",
            source_type="mock:genian-nac",
            claim=(
                "NacPort attributes 10.23.14.52 at observation time to nac-node-10243 "
                "with matching static-IP ledger, healthy Agent check-in, and limited access (policy restriction)."
            ),
            confidence="high",
            caveat="NAC node, user, unit, and switch-port values are synthetic.",
        ),
        Evidence(
            id="EV-MAIN-DIR-1",
            source_type="mock:directive+stealthmole",
            claim=(
                "Directive directive-2026-071 requires blocking a harmful external indicator; "
                "UtmFirewallPort diff shows one network scope missing the blacklist entry, "
                f"with StealthMole pivot context available via {pivot_label}."
            ),
            confidence="medium",
            caveat="Policy change is approval-required and must not be executed autonomously.",
        ),
    ]

    if cl or cds:
        evidence.append(
            Evidence(
                id="EV-MAIN-CRED-1",
                source_type="stealthmole:cl/cds",
                claim=(
                    "Credential/stealer-related evidence indicates possible account reuse or endpoint exposure. "
                    f"Example masked host: {masked_host}; masked IP: {masked_external_ip}."
                ),
                confidence="medium",
                caveat="No raw leaked credentials are rendered. Account actions require internal verification and approval.",
            )
        )

    injects = [
        Inject(
            seq=1,
            offset_min=0,
            source_system="Request Portal",
            visible_clue="사용자가 `업무용 홈페이지 접근이 안 됩니다` 민원을 제출.",
            hidden_truth="단순 장애처럼 보이지만 FW/NAC/Threat Intel 근거가 연결된 복합 사건.",
            related_entities=["request-access-failure", MOCK_ASSET],
            evidence_ids=[],
        ),
        Inject(
            seq=2,
            offset_min=1,
            source_system="TrusGuard-like UTM/FW",
            visible_clue=(
                f"FW-20260704-0182: source 10.23.14.52에서 masked external indicator {masked_external_ip}로 "
                "outbound 세션이 반복 관측됨."
            ),
            hidden_truth="출발지 IP를 NAC 노드에 귀속하고 목적지 지표의 외부 위험 맥락을 확인해야 함.",
            related_entities=["10.23.14.52", masked_external_ip],
            evidence_ids=["EV-MAIN-FW-1", "EV-MAIN-TI-1"],
        ),
        Inject(
            seq=3,
            offset_min=2,
            source_system="StealthMole ThreatIntelPort",
            visible_clue=f"Sanitized external intel says this indicator has supporting pivots: {threat_summary}.",
            hidden_truth="외부 인텔은 차단/보고 우선순위를 높이는 보강 근거이며, 단독 결론이 아님.",
            related_entities=["threat-intel", masked_external_ip],
            evidence_ids=["EV-MAIN-TI-1"],
        ),
        Inject(
            seq=4,
            offset_min=3,
            source_system="Genian NAC-like NacPort",
            visible_clue="10.23.14.52는 nac-node-10243에 귀속. Agent healthy, access limited (정책 제한).",
            hidden_truth="접속 장애와 의심 outbound는 같은 단말의 정책 미준수 상태와 연결됨.",
            related_entities=["nac-node-10243", MOCK_ASSET],
            evidence_ids=["EV-MAIN-NAC-1"],
        ),
        Inject(
            seq=5,
            offset_min=4,
            source_system="DirectivePort + UtmFirewallPort",
            visible_clue="상위 조직 유해 IP 차단 지침 대비 일부 network scope의 blacklist 반영 누락 확인.",
            hidden_truth="정책 변경 요청과 상위 조직 보고가 필요하지만 자동 변경은 금지.",
            related_entities=["directive-2026-071", "blacklist-gap"],
            evidence_ids=["EV-MAIN-DIR-1"],
        ),
        Inject(
            seq=6,
            offset_min=5,
            source_system="Trainee Workspace",
            visible_clue="대응 제출: 사용자 안내, endpoint 점검 요청, blacklist 반영 상신, 보고 초안 중 선택.",
            hidden_truth="근거 ID를 인용하고 approval-required 조치를 분리해야 AAR에서 만점.",
            related_entities=["trainee-action"],
            evidence_ids=["EV-MAIN-FW-1", "EV-MAIN-NAC-1", "EV-MAIN-DIR-1"],
        ),
    ]

    expected_actions = [
        ExpectedAction(
            order=1,
            action="민원과 UTM/FW 이벤트를 같은 case로 묶고 source IP를 확인",
            rationale="단순 사용자 장애로 닫지 않고 보안 이벤트와 연결한다.",
            evidence_ids=["EV-MAIN-FW-1"],
        ),
        ExpectedAction(
            order=2,
            action="StealthMole ThreatIntelPort로 external indicator 위험 맥락 확인",
            rationale="외부 인텔은 지표 우선순위와 보고 근거를 보강한다.",
            evidence_ids=["EV-MAIN-TI-1"],
        ),
        ExpectedAction(
            order=3,
            action="NAC IP attribution, static-IP ledger, Agent/posture 상태 확인",
            rationale="source IP를 affected endpoint와 정책 위반 상태에 연결한다.",
            evidence_ids=["EV-MAIN-NAC-1"],
        ),
        ExpectedAction(
            order=4,
            action="유해 IP 지침과 firewall blacklist compliance diff 확인 후 반영 요청 상신",
            rationale="정책 갭을 고치되 자동 정책 변경은 하지 않는다.",
            evidence_ids=["EV-MAIN-DIR-1", "EV-MAIN-TI-1"],
            approval_required=True,
        ),
        ExpectedAction(
            order=5,
            action="사용자 안내와 상황보고 초안 작성",
            rationale="단말 posture 안내, 미해결 정책 반영 action, 외부 인텔 근거를 분리해 보고한다.",
            evidence_ids=["EV-MAIN-NAC-1", "EV-MAIN-DIR-1", "EV-MAIN-TI-1"],
        ),
    ]

    rubric = [
        "StealthMole 인텔을 메인 결론이 아니라 외부 위험 보강 근거로 사용했는가",
        "FW source IP를 NAC 노드와 고정 IP 관리대장에 귀속했는가",
        "Agent/posture 미준수와 사용자 접속 장애를 함께 설명했는가",
        "유해 IP 지침과 blacklist compliance gap을 발견했는가",
        "정책 변경·격리 같은 민감 조치를 approval-required proposal로 분리했는가",
        "AAR/보고서에서 최소 4개 evidence ID를 인용했는가",
    ]

    return Scenario(
        id="SCEN-MAIN-STEALTH-000",
        title="업무망 장애·의심 outbound·유해 IP 지침 대응 (StealthMole 보강)",
        objective=(
            "기존 T5 메인 데모 사건에 StealthMole external threat intel을 연결해 "
            "더 현실적인 지표 우선순위 판단, blacklist 반영 상신, 사용자 안내, AAR을 수행한다."
        ),
        difficulty="중급",
        threat_context=(
            "업무용 홈페이지 접근 장애 민원과 TrusGuard형 outbound 로그가 동시에 관측되고, "
            "StealthMole sanitized 인텔이 외부 지표 위험을 보강하는 상황."
        ),
        injects=injects,
        expected_actions=expected_actions,
        rubric=rubric,
        evidence=evidence,
    )


def build_credential_scenario(run: dict[str, Any]) -> Scenario | None:
    """Leaked-credential intrusion-indication response (arch MVP scenario)."""
    cl = run.get("cl_search") or {}
    cds = run.get("cds_search") or {}
    if not cl and not cds:
        return None

    cl_total = cl.get("totalCount", 0)
    cds_total = cds.get("totalCount", 0)
    cds_sample = _first_sample(cds)
    masked_host = cds_sample.get("host", "https://login.example-service.com")
    masked_ip = cds_sample.get("ip", "203.0.113.x")

    evidence = [
        Evidence(
            id="EV-CRED-1",
            source_type="stealthmole:cl",
            claim=(
                f"Credential Lookout에서 조회 도메인 관련 외부 유출 계정 {_fmt(cl_total)}건 관측 "
                f"(표본 {cl.get('returned', 0)}건 중 비밀번호 포함 {cl.get('records_with_password', 0)}건)."
            ),
            confidence="high",
            caveat="공개 유출 데이터 기반. 조직 실계정과의 직접 연결은 내부 대조로 별도 확인 필요.",
        ),
        Evidence(
            id="EV-CRED-2",
            source_type="stealthmole:cds",
            claim=(
                f"Compromised Data Set에서 스틸러 감염 기기 유출 {_fmt(cds_total)}건 관측. "
                f"표본 로그인 사이트 예: {masked_host}, 감염 IP(마스킹) {masked_ip}."
            ),
            confidence="high",
            caveat="감염 기기 유출 표본. 개인정보는 마스킹됨.",
        ),
    ]

    injects = [
        Inject(
            seq=1,
            offset_min=0,
            source_system="UTM/FW 로그(모의)",
            visible_clue=f"{MOCK_ASSET} 단말에서 외부 의심 IP(마스킹 {masked_ip})로 반복 아웃바운드 세션 관측.",
            hidden_truth="유출 계정을 이용한 외부 로그인 시도가 진행 중.",
            related_entities=[MOCK_ASSET, masked_ip],
            evidence_ids=["EV-CRED-2"],
        ),
        Inject(
            seq=2,
            offset_min=10,
            source_system="OSINT/StealthMole 인텔",
            visible_clue=f"업무 도메인({MOCK_DOMAIN}) 관련 계정이 외부 유출 목록에 다수 등장, 일부 비밀번호 포함.",
            hidden_truth="유출된 계정 조합으로 credential stuffing 시도 가능.",
            related_entities=[MOCK_DOMAIN],
            evidence_ids=["EV-CRED-1"],
        ),
        Inject(
            seq=3,
            offset_min=20,
            source_system="Leaked/Telegram 모니터링(모의)",
            visible_clue="다크웹/텔레그램 채널에 메일 액세스·combolist 유통 게시글 관측.",
            hidden_truth="유출 계정이 재판매·재사용되는 정황.",
            related_entities=["combolist"],
            evidence_ids=["EV-CRED-1"],
        ),
        Inject(
            seq=4,
            offset_min=30,
            source_system="유해 IP 차단 지침(모의)",
            visible_clue="상위 조직 유해 IP 차단 지침 대비, 모의 방화벽 blacklist에 해당 대역 일부 미반영.",
            hidden_truth="지침-정책 갭으로 의심 아웃바운드가 차단되지 않고 있음.",
            related_entities=[masked_ip],
            evidence_ids=["EV-CRED-2"],
        ),
    ]

    expected_actions = [
        ExpectedAction(
            order=1,
            action="유출 영향 계정·단말 식별 및 범위 산정",
            rationale="EV-CRED-1/2 근거로 어떤 계정·자산이 노출됐는지 특정.",
            evidence_ids=["EV-CRED-1", "EV-CRED-2"],
        ),
        ExpectedAction(
            order=2,
            action="영향 계정 비밀번호 초기화·임시 잠금 요청",
            rationale="credential stuffing 성공 가능성 차단. 계정 조치는 승인 절차 필요.",
            evidence_ids=["EV-CRED-1"],
            approval_required=True,
        ),
        ExpectedAction(
            order=3,
            action="의심 IP 대역 방화벽 차단 상신 및 지침-정책 갭 보고",
            rationale="유해 IP 지침과 모의 방화벽 정책 불일치를 교정. 정책 변경은 승인 필요.",
            evidence_ids=["EV-CRED-2"],
            approval_required=True,
        ),
        ExpectedAction(
            order=4,
            action=f"{MOCK_ASSET} 백신 상태·감염 흔적 점검",
            rationale="감염 기기 유출 정황과 연결된 단말의 방호 상태 확인.",
            evidence_ids=["EV-CRED-2"],
        ),
        ExpectedAction(
            order=5,
            action="침해 정황 상황보고서 초안 작성",
            rationale="관측→분석→조치를 근거와 함께 상위 조직 보고.",
            evidence_ids=["EV-CRED-1", "EV-CRED-2"],
        ),
    ]

    rubric = [
        "두 개 인텔 근거(EV-CRED-1/2)를 모두 확인하고 인용했는가",
        "계정 조치 전에 영향 범위를 먼저 산정했는가",
        "유해 IP 지침과 방화벽 정책의 갭을 발견했는가",
        "승인이 필요한 조치(계정 잠금·정책 변경)를 임의 실행하지 않고 상신했는가",
        "보고서가 관측·근거·권고를 구분해 기술했는가",
    ]

    return Scenario(
        id="SCEN-CRED-001",
        title="유출 크리덴셜 기반 계정 침해 정황 대응",
        objective="외부 유출 인텔과 내부 로그를 연결해 침해 정황을 탐지하고, 승인 절차에 따라 계정·정책을 조치하며 보고까지 수행한다.",
        difficulty="중급",
        threat_context=(
            f"외부 위협 인텔에서 업무 도메인 관련 계정 유출({_fmt(cl_total)}건 관측)과 "
            f"스틸러 감염 기기 유출({_fmt(cds_total)}건 관측)이 확인되는 상황."
        ),
        injects=injects,
        expected_actions=expected_actions,
        rubric=rubric,
        evidence=evidence,
    )


def build_ransomware_scenario(run: dict[str, Any]) -> Scenario | None:
    """Defensive threat-hunting against an active ransomware group's TTP surface."""
    rm = run.get("ransomware_rm") or {}
    if not rm:
        return None

    total = rm.get("totalCount", 0)
    groups = sorted({s.get("attack_group") for s in rm.get("samples", []) if s.get("attack_group")})
    sectors = list((rm.get("top_sectors") or {}).keys())
    group_label = ", ".join(groups) or "관측된 활성 그룹"
    sector_label = ", ".join(sectors[:3]) or "다양한 산업"

    evidence = [
        Evidence(
            id="EV-RANSOM-1",
            source_type="stealthmole:rm",
            claim=(
                f"Ransomware Monitoring에서 공개 피해 {_fmt(total)}건 관측. "
                f"표본 공격 그룹: {group_label}. 주요 피해 섹터: {sector_label}."
            ),
            confidence="high",
            caveat="공개 유출 사이트 기반 관측. 피해 조직 실명은 시나리오에서 사용하지 않음.",
        ),
    ]

    injects = [
        Inject(
            seq=1,
            offset_min=0,
            source_system="랜섬웨어 모니터링(StealthMole)",
            visible_clue=f"활성 그룹({group_label})이 유사 섹터({sector_label}) 대상 공개 유출을 지속 중.",
            hidden_truth="동일 그룹 TTP가 우리 노출면에도 적용 가능.",
            related_entities=list(groups) or ["ransomware-group"],
            evidence_ids=["EV-RANSOM-1"],
        ),
        Inject(
            seq=2,
            offset_min=15,
            source_system="자산 인벤토리(모의)",
            visible_clue=f"{MOCK_UNIT} 외부 노출 서비스 목록과 그룹 TTP 대조 요청 접수.",
            hidden_truth="일부 외부 노출 서비스가 점검되지 않은 상태.",
            related_entities=[MOCK_UNIT],
            evidence_ids=["EV-RANSOM-1"],
        ),
    ]

    expected_actions = [
        ExpectedAction(
            order=1,
            action="관측 그룹의 공개 지표·TTP 요약 정리",
            rationale="EV-RANSOM-1 근거로 위협 프로파일을 방어 관점에서 요약.",
            evidence_ids=["EV-RANSOM-1"],
        ),
        ExpectedAction(
            order=2,
            action="외부 노출 자산 인벤토리 대조·우선순위화",
            rationale="유사 섹터 피해 패턴과 우리 노출면을 비교.",
            evidence_ids=["EV-RANSOM-1"],
        ),
        ExpectedAction(
            order=3,
            action="지표 기반 로그 검색(방어적 위협 헌팅) 및 결과 보고",
            rationale="침해 흔적 여부를 탐지하고 상위 조직 보고. 대응 조치는 승인 필요.",
            evidence_ids=["EV-RANSOM-1"],
            approval_required=True,
        ),
    ]

    rubric = [
        "위협 프로파일을 방어 관점으로 요약했는가(공격 절차가 아닌 지표·TTP)",
        "노출 자산을 위협 패턴에 근거해 우선순위화했는가",
        "위협 헌팅 결과를 근거와 함께 보고했는가",
    ]

    return Scenario(
        id="SCEN-RANSOM-002",
        title="활성 랜섬웨어 그룹 노출면 점검(위협 헌팅)",
        objective="외부에서 관측된 활성 랜섬웨어 그룹의 지표를 근거로 우리 노출면을 방어적으로 점검하고 보고한다.",
        difficulty="기초-중급",
        threat_context=f"활성 그룹({group_label})이 유사 섹터를 지속 공격 중인 상황에서 노출면 사전 점검.",
        injects=injects,
        expected_actions=expected_actions,
        rubric=rubric,
        evidence=evidence,
    )


def build_directive_scenario(run: dict[str, Any]) -> Scenario | None:
    """Harmful-IP / indicator directive compliance check."""
    tt = run.get("tt_targets_ip") or {}
    cdf = run.get("cdf_targets_ip") or {}
    if not tt and not cdf:
        return None

    tt_targets = tt.get("targets") or []
    cdf_targets = cdf.get("targets") or []
    pivot_label = ", ".join((tt_targets[:3] + cdf_targets[:2])) or "ip/domain 지표"

    evidence = [
        Evidence(
            id="EV-DIR-1",
            source_type="stealthmole:tt/cdf",
            claim=(
                "TT/CDF indicator target 조회로 IP·도메인 관련 위협 피벗 경로 확인 "
                f"(예: {pivot_label})."
            ),
            confidence="medium",
            caveat="target 가용성은 계정 권한/설정에 따라 달라질 수 있음.",
        ),
    ]

    injects = [
        Inject(
            seq=1,
            offset_min=0,
            source_system="유해 IP 차단 지침(모의)",
            visible_clue="상위 조직에서 신규 유해 IP/도메인 차단 지침 하달.",
            hidden_truth="지침 지표 일부가 모의 방화벽 blacklist에 미반영.",
            related_entities=["harmful-ip-directive"],
            evidence_ids=["EV-DIR-1"],
        ),
        Inject(
            seq=2,
            offset_min=10,
            source_system="OSINT/StealthMole 인텔",
            visible_clue=f"지침 지표를 외부 인텔로 보강 조회 가능({pivot_label}).",
            hidden_truth="일부 지표는 활성 위협과 연관.",
            related_entities=["ip", "domain"],
            evidence_ids=["EV-DIR-1"],
        ),
    ]

    expected_actions = [
        ExpectedAction(
            order=1,
            action="지침 지표와 모의 방화벽 정책 대조",
            rationale="차단 지침이 정책에 반영됐는지 확인.",
            evidence_ids=["EV-DIR-1"],
        ),
        ExpectedAction(
            order=2,
            action="외부 인텔로 지표 위험도 보강 후 미반영 항목 차단 상신",
            rationale="근거를 붙여 차단 정책 변경을 상신. 정책 변경은 승인 필요.",
            evidence_ids=["EV-DIR-1"],
            approval_required=True,
        ),
        ExpectedAction(
            order=3,
            action="준수 점검 결과 보고",
            rationale="지침 준수 상태와 조치 내역을 상위 조직 보고.",
            evidence_ids=["EV-DIR-1"],
        ),
    ]

    rubric = [
        "지침 지표와 정책을 빠짐없이 대조했는가",
        "외부 인텔로 위험도를 보강했는가",
        "정책 변경을 임의 실행하지 않고 근거와 함께 상신했는가",
    ]

    return Scenario(
        id="SCEN-DIR-003",
        title="유해 IP 차단 지침 준수 점검",
        objective="유해 IP/도메인 차단 지침이 방화벽 정책에 반영됐는지 외부 인텔로 보강해 점검하고 상신·보고한다.",
        difficulty="기초",
        threat_context="신규 유해 IP/도메인 차단 지침 하달 후 정책 반영 상태 점검이 필요한 상황.",
        injects=injects,
        expected_actions=expected_actions,
        rubric=rubric,
        evidence=evidence,
    )


def build_scenarios(run: dict[str, Any]) -> list[Scenario]:
    """Build every scenario the collected data supports, in demo order."""
    builders = (
        build_main_demo_enrichment_scenario,
        build_credential_scenario,
        build_ransomware_scenario,
        build_directive_scenario,
    )
    return [s for s in (b(run) for b in builders) if s is not None]
