/**
 * 04/05 미션 데스크 (A-03).
 *
 * 실제 보안 관제 조직 작업대처럼:
 *  - 좌측 상황 피드: 세션 이벤트를 시간순으로 표시하고 주기적으로 polling해
 *    새 이벤트를 append한다 (서비스 장애 · 의심 outbound · 지시사항 gap · 단말 posture).
 *  - 중앙 장비 데스크: TrusGuard형 UTM/FW, Genian NAC, 지시사항함,
 *    ThreatIntel 5개 탭. 각 탭은 query form을 갖고, 조회 시
 *    POST /equipment/query 응답의 view_model을 port별로 렌더링한다.
 *  - 우측 조사 노트: 근거 pin / 판단 / 대응 제출은 A-04에서 붙는다.
 *
 * 데이터는 전부 API-driven이다. 화면은 evidence[]와 view_model만 그린다.
 */
window.D4D = window.D4D || {};
(function (D4D) {
  "use strict";
  var esc = D4D.ui.esc;

  var POLL_MS = 4000;

  var SEVERITY_KO = {
    temporary_failure: "일시 장애",
    policy_restriction: "정책 제한",
    suspected_compromise: "침해 의심",
    critical_compromise_possible: "중대 침해 가능",
  };

  var REDACTION_KO = { synthetic: "synthetic", masked: "masked", sanitized: "sanitized" };
  var CONF_KO = { high: "높음", medium: "보통", low: "낮음" };

  var RISK_KO = { elevated: "높음", attention: "주의", low: "낮음", info: "정보" };
  var RISK_CLASS = { elevated: "risk-high", attention: "risk-mid", low: "risk-low", info: "risk-low" };

  // 장비 탭 정의.
  //  - fields: query form 입력 (fixture 기본값이 시나리오에 맞게 채워짐)
  //  - propose: 해당 장비에서 낼 수 있는 대응 조치 제안. 차단/격리/정책 반영은
  //    approval=true 이며 서버가 승인 필요를 강제한다(자동 실행 아님).
  var TABS = [
    { port: "utm_firewall", label: "TrusGuard 로그", query_type: "firewall_log_search",
      fields: [
        { name: "source_ip", label: "Source IP", value: "10.23.14.52" },
        { name: "destination", label: "Destination", value: "203.0.113.45" },
      ],
      propose: { action_type: "policy_update_request", label: "차단 정책 제안", target: "203.0.113.45", scope: "WEB-OUT 정책",
        body: "의심 반복 outbound 목적지 203.0.113.45에 대한 차단 정책 반영을 요청합니다.",
        evidence_ids: ["fw-log-0182"], approval: true } },
    { port: "nac", label: "Genian NAC", query_type: "ip_attribution",
      fields: [{ name: "ip", label: "IP", value: "10.23.14.52" }],
      propose: { action_type: "endpoint_isolation_review", label: "단말 격리 제안", target: "nac-node-10243", scope: "업무부서 VLAN",
        body: "Access limited(정책 제한) 단말 nac-node-10243 격리 검토를 요청합니다.",
        evidence_ids: ["nac-node-10243", "endpoint-posture-10243"], approval: true } },
    { port: "directive", label: "지시사항함", query_type: "directive_compliance",
      fields: [{ name: "directive_id", label: "지시사항 ID", value: "Directive-2026-071" }],
      propose: { action_type: "policy_update_request", label: "Blacklist 반영 요청", target: "미반영 유해 IP 4건", scope: "방화벽 전 구간",
        body: "Directive-2026-071 미반영 유해 IP 4건의 blacklist 반영을 요청합니다.",
        evidence_ids: ["directive-2026-071"], approval: true } },
    { port: "threat_intel", label: "ThreatIntel", query_type: "indicator_enrichment",
      fields: [{ name: "indicator", label: "지표(IP)", value: "203.0.113.45" }],
      propose: { action_type: "policy_update_request", label: "지표 차단 제안", target: "203.0.113.45", scope: "방화벽/프록시",
        body: "C2 의심 지표 203.0.113.45의 차단 반영을 요청합니다.",
        evidence_ids: ["threat-intel-203-0-113-45"], approval: true } },
  ];

  // 세션 동안의 조사 노트 상태. render마다 초기화.
  var proposals = [];      // 제안된 조치 (승인 대기)
  var pinnedIds = [];      // pin된 근거 ID
  var evidenceClaims = {}; // evidence_id -> claim (표시용)
  var savedAssessment = null;

  // 판단 패널 enum
  var PRIORITY_OPTS = [
    { v: "parallel_triage", t: "병행 분류 (동시 대응)" },
    { v: "service_first", t: "서비스 복구 우선" },
    { v: "security_first", t: "보안 조사 우선" },
  ];
  var SEVERITY_OPTS = [
    { v: "temporary_failure", t: "일시 장애" },
    { v: "policy_restriction", t: "정책 제한" },
    { v: "suspected_compromise", t: "침해 의심" },
    { v: "critical_compromise_possible", t: "중대 침해 가능" },
  ];
  var EFFORT_OPTS = [
    { v: "quick_guidance", t: "즉시 안내" },
    { v: "approval_required_action", t: "승인 필요 조치" },
    { v: "longer_investigation", t: "추가 조사" },
    { v: "higher_report", t: "상위 조직 보고" },
  ];
  var CONF_OPTS = [
    { v: "high", t: "높음" },
    { v: "medium", t: "보통" },
    { v: "low", t: "낮음" },
  ];

  // ---- 상황 피드 ----------------------------------------------------------
  function eventRow(e) {
    return (
      '<article class="feed-event">' +
        "<time>" + esc((e.timestamp || "").slice(11, 16)) + "</time>" +
        "<div><strong>" + esc(e.title) + "</strong><span>" + esc(e.visible_text) + "</span>" +
        '<span class="pill tiny">' + esc(SEVERITY_KO[e.severity_hint] || e.severity_hint || "") + "</span></div>" +
      "</article>"
    );
  }

  function renderFeed(mount, events) {
    var list = mount.querySelector("#feed-list");
    var count = mount.querySelector("#feed-count");
    if (count) count.textContent = events.length + "건";
    if (!list) return;
    list.innerHTML = events.length
      ? events.map(eventRow).join("")
      : D4D.ui.emptyState("표시할 이벤트가 없습니다.");
  }

  // ---- view_model 렌더러 (port별) ----------------------------------------
  function tableView(vm) {
    var head = "<tr>" + (vm.columns || []).map(function (c) { return "<th>" + esc(c) + "</th>"; }).join("") + "</tr>";
    var body = (vm.rows || []).map(function (r) {
      return "<tr>" + r.map(function (cell) { return "<td>" + esc(cell) + "</td>"; }).join("") + "</tr>";
    }).join("");
    var summary = "";
    if (vm.summary) {
      var s = vm.summary;
      summary =
        '<div class="chip-row">' +
          '<span class="chip">지시사항 대상 ' + esc(s.directive_targets) + "</span>" +
          '<span class="chip">반영 ' + esc(s.reflected) + "</span>" +
          '<span class="chip warn">미반영 ' + esc(s.missing) + "</span>" +
          (s.selected_log_id ? '<span class="chip">선택 ' + esc(s.selected_log_id) + "</span>" : "") +
        "</div>";
    }
    return '<table class="compact-table">' + head + body + "</table>" + summary;
  }

  function kv(label, value) {
    return '<div class="kv"><span>' + esc(label) + "</span><b>" + esc(value) + "</b></div>";
  }

  function nacView(vm) {
    var n = vm.node || {};
    var l = vm.static_ip_ledger || {};
    return (
      '<div class="kv-card"><h4>노드</h4>' +
        kv("Node ID", n.node_id) + kv("IP", n.ip) + kv("소속", n.unit) +
        kv("사용자(masked)", n.user_label) + kv("Agent", n.agent_status) + kv("Access", n.access_state) +
      "</div>" +
      '<div class="kv-card"><h4>고정 IP 대장</h4>' +
        kv("할당 IP", l.assigned_ip) + kv("관측 IP", l.observed_ip) +
        kv("MAC 일치", l.mac_match ? "예" : "아니오") + kv("승인 근거", l.approval_ref) +
      "</div>"
    );
  }

  function directiveView(vm) {
    // 백엔드 directive_compliance view_model: {directive_id, targets, reflected,
    // missing:[ip...], approval_required}
    var missing = vm.missing || [];
    var samples = missing.map(function (ip) { return '<span class="pill tiny warn">' + esc(ip) + "</span>"; }).join(" ");
    return (
      '<div class="kv-card"><h4>지시사항 반영</h4>' +
        kv("ID", vm.directive_id) + kv("대상 수", vm.targets) + kv("반영", vm.reflected) + kv("미반영", missing.length) +
      "</div>" +
      '<div class="chip-row"><span class="chip">반영 ' + esc(vm.reflected) + '</span><span class="chip warn">미반영 ' + esc(missing.length) + "</span></div>" +
      '<div class="field-box">미반영 IP: ' + (samples || "없음") + "</div>" +
      (vm.approval_required ? '<small class="muted-note">반영은 승인 필요 조치입니다.</small>' : "")
    );
  }

  function chipsOf(obj) {
    return Object.keys(obj || {}).map(function (k) {
      return '<span class="chip">' + esc(k) + " " + esc(obj[k]) + "</span>";
    }).join(" ");
  }

  // StealthMole 데이터셋(마스킹) landscape 렌더.
  function landscapeView(ls) {
    if (!ls) return "";
    var r = ls.ransomware || {}, c = ls.credentials || {}, m = ls.monitoring || {};
    var rRecent = (r.recent || []).map(function (x) {
      return "<li><b>" + esc(x.attack_group || "?") + "</b> · " + esc(x.victim || "") +
        (x.sector ? " · " + esc(x.sector) : "") + "</li>";
    }).join("");
    var cRecent = (c.recent_samples || []).map(function (x) {
      return "<li>" + esc(x.email || x.domain || "") + " · " + esc(x.password || "") +
        (x.leaked_date ? " · " + esc(x.leaked_date) : "") + "</li>";
    }).join("");
    var titles = (m.recent_titles || []).map(function (x) {
      return "<li>" + esc(x.title || "") + (x.author ? " · " + esc(x.author) : "") + "</li>";
    }).join("");
    return (
      '<div class="kv-card ti-landscape"><h4>StealthMole 위협 인텔 · 마스킹 <small>run ' + esc(ls.dataset_run) + "</small></h4>" +
        '<div class="ti-sub">활성 랜섬웨어 (표본 ' + esc(r.sampled) + " / 피드 " + esc(r.feed_total) + ")</div>" +
        '<div class="chip-row">' + chipsOf(r.top_groups) + "</div>" +
        (rRecent ? '<ul class="mini-list">' + rRecent + "</ul>" : "") +
      "</div>" +
      '<div class="kv-card"><h4>유출 크리덴셜 노출</h4>' +
        '<div class="ti-sub">표본 ' + esc(c.sampled) + " · 비밀번호 포함 " + esc(c.with_password) +
        " · 피드 " + esc(c.feed_total) + "</div>" +
        '<div class="chip-row">' + chipsOf(c.top_domains) + "</div>" +
        (cRecent ? '<ul class="mini-list">' + cRecent + "</ul>" : "") +
      "</div>" +
      '<div class="kv-card"><h4>모니터링 피드</h4>' +
        '<div class="ti-sub">정부 ' + esc(m.government_sampled) + " · 유출 " + esc(m.leaked_sampled) + " (표본)</div>" +
        (titles ? '<ul class="mini-list">' + titles + "</ul>" : "") +
      "</div>"
    );
  }

  function threatView(vm) {
    // 백엔드 indicator_enrichment view_model: {indicator, risk, sources:[], fallback_reason, landscape?}
    var sources = (vm.sources || []).join(", ");
    var live = vm.landscape && vm.landscape.source === "stealthmole:masked";
    return (
      '<div class="kv-card"><h4>ThreatIntel 지표</h4>' +
        kv("지표", vm.indicator) + kv("위험", vm.risk) + kv("출처", sources) +
        (vm.fallback_reason ? kv("fallback", vm.fallback_reason) : "") +
      "</div>" +
      landscapeView(vm.landscape) +
      '<small class="muted-note">' + (live
        ? "StealthMole 라이브 데이터셋(마스킹) 연동 · 원문 미저장"
        : "공개 인텔 sanitized 요약 · 원문 미저장") + "</small>"
    );
  }

  function renderViewModel(port, vm) {
    if (!vm) return "";
    switch (port) {
      case "utm_firewall": return tableView(vm);
      case "nac": return nacView(vm);
      case "directive": return directiveView(vm);
      case "threat_intel": return threatView(vm);
      default: return '<pre class="raw">' + esc(JSON.stringify(vm, null, 2)) + "</pre>";
    }
  }

  function evidenceList(evidence) {
    if (!evidence || !evidence.length) return "";
    var rows = evidence.map(function (ev) {
      evidenceClaims[ev.evidence_id] = ev.claim;
      var isPinned = pinnedIds.indexOf(ev.evidence_id) >= 0;
      return (
        '<div class="evidence-item">' +
          '<div class="evidence-top"><code>' + esc(ev.evidence_id) + "</code>" +
            '<span class="pill tiny">신뢰도 ' + esc(CONF_KO[ev.confidence] || ev.confidence) + "</span>" +
            '<span class="pill tiny">' + esc(REDACTION_KO[ev.redaction] || ev.redaction) + "</span>" +
            '<button class="pin-btn" data-ev="' + esc(ev.evidence_id) + '"' + (isPinned ? ' data-pinned="true" disabled' : "") + ">" +
              (isPinned ? "pin됨" : "근거 pin") + "</button></div>" +
          "<p>" + esc(ev.claim) + "</p>" +
          (ev.caveat ? '<small class="caveat">유의: ' + esc(ev.caveat) + "</small>" : "") +
        "</div>"
      );
    }).join("");
    return '<div class="evidence-block"><h4>수집 근거 <small>조사 노트로 pin</small></h4>' + rows + "</div>";
  }

  function bindPins(mount, sid) {
    Array.prototype.forEach.call(mount.querySelectorAll(".pin-btn"), function (btn) {
      if (btn.getAttribute("data-pinned") === "true") return;
      btn.addEventListener("click", function () {
        var id = btn.getAttribute("data-ev");
        if (pinnedIds.indexOf(id) < 0) pinnedIds.push(id);
        btn.setAttribute("data-pinned", "true");
        btn.setAttribute("disabled", "disabled");
        btn.textContent = "pin됨";
        D4D.api.post("/api/training/sessions/" + encodeURIComponent(sid) + "/evidence/pins", {
          evidence_ids: pinnedIds,
          note: "미션 데스크에서 pin",
        }).then(
          function () { renderNote(mount); },
          function (e) {
            // 롤백
            pinnedIds = pinnedIds.filter(function (x) { return x !== id; });
            btn.removeAttribute("data-pinned");
            btn.removeAttribute("disabled");
            btn.textContent = "근거 pin";
            renderNote(mount);
            if (e) { /* 표시 생략 */ }
          }
        );
      });
    });
  }

  // ---- 상세 로그 분석 (drill-down) ---------------------------------------
  function analysisDetail(detail) {
    if (!detail) return "";
    var html = "";
    if (detail.fields) {
      html += '<div class="kv-card"><h4>상세</h4>' +
        Object.keys(detail.fields).map(function (k) { return kv(k, detail.fields[k]); }).join("") + "</div>";
    }
    if (detail.related_rows) {
      var rr = detail.related_rows;
      html += '<div class="kv-card"><h4>연관 로그</h4>' + tableView({ columns: rr.columns, rows: rr.rows }) + "</div>";
    }
    if (detail.checks) {
      html += '<div class="kv-card"><h4>점검 항목</h4><ul class="check-list">' +
        detail.checks.map(function (c) {
          return '<li data-pass="' + (c.pass ? "true" : "false") + '">' + (c.pass ? "✔ " : "✘ ") + esc(c.name) + "</li>";
        }).join("") + "</ul></div>";
    }
    if (detail.missing) {
      html += '<div class="field-box">미반영: ' +
        detail.missing.map(function (m) { return '<span class="pill tiny warn">' + esc(m) + "</span>"; }).join(" ") + "</div>";
    }
    return html;
  }

  function renderAnalysis(a) {
    var chips = (a.correlated_evidence_ids || []).map(function (id) { return '<span class="chip">' + esc(id) + "</span>"; }).join("");
    return (
      '<div class="analysis">' +
        '<div class="analysis-head"><strong>상세 로그 분석</strong>' +
          '<span class="pill ' + (RISK_CLASS[a.risk_level] || "") + '">위험도 ' + esc(RISK_KO[a.risk_level] || a.risk_level) + "</span></div>" +
        "<p class=\"analysis-headline\">" + esc(a.headline) + "</p>" +
        '<ul class="signal-list">' + (a.signals || []).map(function (s) { return "<li>" + esc(s) + "</li>"; }).join("") + "</ul>" +
        (chips ? '<div class="analysis-corr"><span>연관 근거</span><div class="chip-row">' + chips + "</div></div>" : "") +
        analysisDetail(a.detail) +
      "</div>"
    );
  }

  // ---- 대응 조치 제안 (승인 대기, 자동 실행 아님) ------------------------
  function proposeFormHtml(tab) {
    var p = tab.propose;
    return (
      '<div class="propose-form">' +
        '<div class="propose-title">' + esc(p.label) +
          (p.approval ? ' <span class="pill tiny warn">승인 필요</span>' : ' <span class="pill tiny">안내</span>') + "</div>" +
        '<label class="field"><span>대상</span><input type="text" id="pp-target" value="' + esc(p.target) + '"></label>' +
        '<label class="field"><span>적용 범위</span><input type="text" id="pp-scope" value="' + esc(p.scope) + '"></label>' +
        '<label class="field"><span>사유</span><textarea id="pp-body" rows="2">' + esc(p.body) + "</textarea></label>" +
        '<div class="propose-note">' +
          (p.approval
            ? "이 조치는 자동 실행되지 않습니다. 제출 시 승인 대기 목록에 제안으로만 추가됩니다."
            : "사용자 안내 조치로 기록됩니다. 시스템을 직접 변경하지 않습니다.") +
        "</div>" +
        '<button class="primary" id="pp-submit">' + (p.approval ? "승인 요청 제출" : "안내 기록") + "</button>" +
      "</div>"
    );
  }

  function submitProposal(mount, sid, tab, outputEl) {
    var p = tab.propose;
    var target = (mount.querySelector("#pp-target") || {}).value || p.target;
    var scope = (mount.querySelector("#pp-scope") || {}).value || p.scope;
    var bodyText = (mount.querySelector("#pp-body") || {}).value || p.body;
    outputEl.innerHTML = D4D.ui.loading("조치 제안 제출 중…");
    D4D.api.post("/api/training/sessions/" + encodeURIComponent(sid) + "/actions", {
      actions: [{
        action_type: p.action_type,
        title: p.label,
        body: bodyText,
        target: target,
        scope: scope,
        evidence_ids: p.evidence_ids,
        approval_required: p.approval,
      }],
    }).then(
      function (res) {
        var acts = (res.data.submitted_actions || []);
        acts.forEach(function (a) { proposals.push(a); });
        renderProposals(mount);
        var a0 = acts[0] || {};
        outputEl.innerHTML =
          '<div class="inline-note ' + (a0.approval_required ? "warn" : "") + '">' +
            "‘" + esc(a0.title || p.label) + "’ 조치가 " +
            (a0.approval_required ? "<b>승인 대기</b> 목록에 제안으로 추가되었습니다. 자동 실행되지 않았습니다." : "안내로 기록되었습니다.") +
          "</div>";
      },
      function (e) { outputEl.innerHTML = D4D.ui.errorState("조치를 제출하지 못했습니다: " + e.message); }
    );
  }

  function proposalItem(a) {
    // status/approval_forced는 백엔드가 생략할 수 있어 approval_required로 보정한다.
    var status = a.status || (a.approval_required ? "승인 대기" : "기록됨");
    return (
      '<div class="proposal-item">' +
        '<div class="proposal-top"><strong>' + esc(a.title || a.action_type) + "</strong>" +
          '<span class="pill tiny ' + (a.approval_required ? "warn" : "") + '">' + esc(status) + "</span></div>" +
        (a.target ? '<p>대상: ' + esc(a.target) + (a.scope ? " · 범위: " + esc(a.scope) : "") + "</p>" : "") +
        '<small class="muted-note">근거: ' + esc((a.evidence_ids || []).join(", ") || "없음") + "</small>" +
        (a.approval_forced ? '<small class="caveat">정책/격리 조치 — 항상 승인 필요, 자동 실행 안 됨</small>' : "") +
      "</div>"
    );
  }

  function renderProposals(mount) {
    var tray = mount.querySelector("#proposal-tray");
    var count = mount.querySelector("#prop-count");
    if (count) count.textContent = proposals.length + "건";
    if (!tray) return;
    tray.innerHTML = proposals.length
      ? proposals.map(proposalItem).join("")
      : D4D.ui.emptyState("아직 제안된 조치가 없습니다. 장비 조회 후 차단/격리/반영을 제안하십시오.");
  }

  // ---- 조사 노트 (pin된 근거) --------------------------------------------
  function renderNote(mount) {
    var list = mount.querySelector("#pinned-list");
    var count = mount.querySelector("#pin-count");
    if (count) count.textContent = pinnedIds.length + "건";
    if (!list) return;
    list.innerHTML = pinnedIds.length
      ? pinnedIds.map(function (id) {
          return '<div class="pinned-item"><code>' + esc(id) + "</code><p>" + esc(evidenceClaims[id] || "") + "</p></div>";
        }).join("")
      : D4D.ui.emptyState("아직 pin된 근거가 없습니다. 장비 조회 결과에서 근거를 pin하십시오.");
    // 판단 폼의 인용 근거 표시 갱신
    var cited = mount.querySelector("#assess-cited");
    if (cited) cited.textContent = pinnedIds.length ? pinnedIds.join(", ") : "pin된 근거 없음";
  }

  // ---- 판단 패널 (assessment) --------------------------------------------
  function optionList(opts, sel) {
    return opts.map(function (o) {
      return '<option value="' + o.v + '"' + (o.v === sel ? " selected" : "") + ">" + esc(o.t) + "</option>";
    }).join("");
  }

  function assessmentFormHtml() {
    return (
      '<div class="assess-form">' +
        '<label class="field"><span>우선순위</span><select id="as-priority">' + optionList(PRIORITY_OPTS, "parallel_triage") + "</select></label>" +
        '<label class="field"><span>심각도</span><select id="as-severity">' + optionList(SEVERITY_OPTS, "policy_restriction") + "</select></label>" +
        '<div class="field"><span>대응 노력 (복수)</span><div class="effort-box">' +
          EFFORT_OPTS.map(function (o) {
            return '<label class="chk"><input type="checkbox" data-effort="' + o.v + '"> ' + esc(o.t) + "</label>";
          }).join("") +
        "</div></div>" +
        '<label class="field"><span>확신도</span><select id="as-confidence">' + optionList(CONF_OPTS, "medium") + "</select></label>" +
        '<label class="field"><span>판단 근거</span><textarea id="as-rationale" rows="3" placeholder="근거 ID 기반으로 우선순위·심각도 판단을 서술"></textarea></label>' +
        '<div class="field-box">인용 근거: <span id="assess-cited">pin된 근거 없음</span></div>' +
        '<div class="inline-note" id="assess-note" hidden></div>' +
        '<button class="primary full" id="as-save">판단 저장</button>' +
      "</div>"
    );
  }

  function renderAssessmentPanel(mount) {
    var panel = mount.querySelector("#assessment-panel");
    if (!panel) return;
    if (savedAssessment) {
      var a = savedAssessment;
      var efforts = (a.response_efforts || []).map(function (v) {
        var m = EFFORT_OPTS.filter(function (o) { return o.v === v; })[0];
        return '<span class="pill tiny">' + esc(m ? m.t : v) + "</span>";
      }).join(" ");
      panel.innerHTML =
        '<div class="assess-saved">' +
          '<div class="kv"><span>우선순위</span><b>' + esc(labelOf(PRIORITY_OPTS, a.priority)) + "</b></div>" +
          '<div class="kv"><span>심각도</span><b>' + esc(labelOf(SEVERITY_OPTS, a.severity)) + "</b></div>" +
          '<div class="kv"><span>확신도</span><b>' + esc(labelOf(CONF_OPTS, a.confidence)) + "</b></div>" +
          '<div class="assess-efforts">' + (efforts || "—") + "</div>" +
          (a.rationale ? '<p class="assess-rationale">' + esc(a.rationale) + "</p>" : "") +
          '<div class="field-box">인용 근거: ' + esc((a.evidence_ids || []).join(", ") || "없음") + "</div>" +
          '<button class="secondary full" id="as-edit">판단 수정</button>' +
        "</div>";
      mount.querySelector("#as-edit").addEventListener("click", function () {
        savedAssessment = null;
        renderAssessmentPanel(mount);
      });
    } else {
      panel.innerHTML = assessmentFormHtml();
      renderNote(mount); // 인용 근거 표시 채우기
      mount.querySelector("#as-save").addEventListener("click", function () {
        saveAssessment(mount, mount.getAttribute("data-sid"));
      });
    }
  }

  function labelOf(opts, v) {
    var m = opts.filter(function (o) { return o.v === v; })[0];
    return m ? m.t : (v || "—");
  }

  function saveAssessment(mount, sid) {
    var efforts = [];
    Array.prototype.forEach.call(mount.querySelectorAll("#assessment-panel input[data-effort]"), function (c) {
      if (c.checked) efforts.push(c.getAttribute("data-effort"));
    });
    var body = {
      priority: (mount.querySelector("#as-priority") || {}).value,
      severity: (mount.querySelector("#as-severity") || {}).value,
      response_efforts: efforts,
      approval_required: efforts.indexOf("approval_required_action") >= 0,
      confidence: (mount.querySelector("#as-confidence") || {}).value,
      rationale: (mount.querySelector("#as-rationale") || {}).value || "",
      evidence_ids: pinnedIds.slice(),
    };
    var note = mount.querySelector("#assess-note");
    D4D.api.put("/api/training/sessions/" + encodeURIComponent(sid) + "/assessment", body).then(
      function (res) {
        savedAssessment = res.data.assessment;
        renderAssessmentPanel(mount);
        if (res.warnings && res.warnings.length) {
          // 저장은 되되 근거 부족 경고를 평가 strip 위에 표시
          showEvalWarning(mount, res.warnings.map(function (w) { return w.message; }).join(" "));
        }
        loadEvalPreview(mount, sid);
      },
      function (e) {
        if (note) { note.hidden = false; note.className = "inline-note error"; note.textContent = "판단을 저장하지 못했습니다: " + e.message; }
      }
    );
  }

  // ---- 평가 미리보기 strip ------------------------------------------------
  function showEvalWarning(mount, msg) {
    var el = mount.querySelector("#eval-strip");
    if (el) el.innerHTML = '<div class="inline-note warn">' + esc(msg) + "</div>";
  }

  function loadEvalPreview(mount, sid) {
    var el = mount.querySelector("#eval-strip");
    if (!el) return;
    if (!el.innerHTML) el.innerHTML = D4D.ui.loading("평가 미리보기…");
    D4D.api.post("/api/training/sessions/" + encodeURIComponent(sid) + "/evaluation/preview", {
      include_private_rubric_detail: false,
      reason: "mission_desk_status_strip",
    }).then(
      function (res) {
        var s = res.data.summary_strip || {};
        var warn = (res.warnings || []).map(function (w) { return w.message; })[0];
        el.innerHTML =
          '<div class="eval-strip-row">' +
            '<span class="chip">우선순위 ' + esc(s.priority) + "</span>" +
            '<span class="chip">심각도 ' + esc(s.severity) + "</span>" +
            '<span class="chip">대응 ' + esc(s.response_effort) + "</span>" +
            '<span class="chip">' + esc(s.rubric) + "</span>" +
          "</div>" +
          (warn ? '<small class="muted-note">' + esc(warn) + "</small>" : "");
      },
      function (e) { el.innerHTML = D4D.ui.errorState("평가 미리보기 실패: " + e.message); }
    );
  }

  // ---- 장비 데스크 --------------------------------------------------------
  function formHtml(tab) {
    return (
      '<div class="equip-form">' +
        tab.fields.map(function (f) {
          return '<label class="field"><span>' + esc(f.label) + "</span>" +
            '<input type="text" data-field="' + esc(f.name) + '" value="' + esc(f.value) + '"></label>';
        }).join("") +
        '<button class="primary" id="equip-run">조회</button>' +
      "</div>"
    );
  }

  function selectTab(mount, sid, tab) {
    Array.prototype.forEach.call(mount.querySelectorAll(".tab-row .tab"), function (b) {
      if (b.getAttribute("data-port") === tab.port) b.setAttribute("data-active", "true");
      else b.removeAttribute("data-active");
    });
    mount.querySelector("#equip-form").innerHTML = formHtml(tab);
    mount.querySelector("#equip-result").innerHTML =
      D4D.ui.emptyState(tab.label + " 조건을 확인하고 조회를 누르십시오.");
    mount.querySelector("#equip-run").addEventListener("click", function () {
      runQuery(mount, sid, tab);
    });
  }

  function runQuery(mount, sid, tab) {
    var result = mount.querySelector("#equip-result");
    var query = {};
    Array.prototype.forEach.call(mount.querySelectorAll("#equip-form input[data-field]"), function (inp) {
      query[inp.getAttribute("data-field")] = inp.value;
    });
    result.innerHTML = D4D.ui.loading("조회 중…");
    D4D.api.post("/api/training/sessions/" + encodeURIComponent(sid) + "/equipment/query", {
      port: tab.port,
      query_type: tab.query_type,
      query: query,
    }).then(
      function (res) {
        var d = res.data;
        result.innerHTML =
          '<div class="result-head">' + esc(tab.label) + " · " + esc(d.query_type) + "</div>" +
          renderViewModel(d.port, d.view_model) +
          evidenceList(d.evidence) +
          '<div class="ops-bar">' +
            '<button class="secondary" id="op-analyze">상세 로그 분석</button>' +
            '<button class="danger" id="op-propose">' + esc(tab.propose.label) + "</button>" +
          "</div>" +
          '<div class="op-output" id="op-output"></div>';
        bindOps(mount, sid, tab);
        bindPins(mount, sid);
      },
      function (e) {
        result.innerHTML = D4D.ui.errorState("조회하지 못했습니다: " + e.message);
      }
    );
  }

  function bindOps(mount, sid, tab) {
    var output = mount.querySelector("#op-output");
    mount.querySelector("#op-analyze").addEventListener("click", function () {
      output.innerHTML = D4D.ui.loading("상세 분석 중…");
      D4D.api.post("/api/training/sessions/" + encodeURIComponent(sid) + "/equipment/analyze", {
        port: tab.port, evidence_id: tab.propose.evidence_ids[0],
      }).then(
        function (res) { output.innerHTML = renderAnalysis(res.data); },
        function (e) {
          if (e.code === "NOT_IMPLEMENTED" || e.code === "ADAPTER_UNAVAILABLE") {
            output.innerHTML = '<div class="inline-note">이 장비의 상세 분석은 현재 백엔드에서 제공되지 않습니다.</div>';
          } else {
            output.innerHTML = D4D.ui.errorState("상세 분석에 실패했습니다: " + e.message);
          }
        }
      );
    });
    mount.querySelector("#op-propose").addEventListener("click", function () {
      output.innerHTML = proposeFormHtml(tab);
      mount.querySelector("#pp-submit").addEventListener("click", function () {
        submitProposal(mount, sid, tab, output);
      });
    });
  }

  // ---- 화면 ---------------------------------------------------------------
  function stepbar() {
    return (
      '<div class="stepbar">' +
        '<div class="step"><b>1</b><span>훈련 홈<small>완료</small></span></div>' +
        '<div class="step"><b>2</b><span>시나리오 선택<small>완료</small></span></div>' +
        '<div class="step"><b>3</b><span>임무 브리핑<small>완료</small></span></div>' +
        '<div class="step" data-current="true"><b>4</b><span>미션 데스크<small>현재 단계</small></span></div>' +
        '<div class="step"><b>5</b><span>사후 강평<small>대기</small></span></div>' +
      "</div>"
    );
  }

  function render(mount, session) {
    mount.innerHTML =
      stepbar() +
      '<div class="desk-layout">' +
        '<aside class="panel" data-tour="mission-feed">' +
          '<div class="panel-head"><h3>상황 피드 <span class="live-dot" title="실시간 polling"></span></h3>' +
            '<span id="feed-count">0건</span></div>' +
          '<div class="panel-pad feed-list" id="feed-list"></div>' +
          '<div class="panel-pad"><small class="muted-note">세션 ' + esc(session.session_id) +
            " · " + POLL_MS / 1000 + "초 간격 갱신</small></div>" +
        "</aside>" +
        '<section class="panel" data-tour="mission-equipment">' +
          '<div class="panel-head"><h3>목업 보안 장비</h3><span>TrusGuard · NAC · 지시사항 · ThreatIntel</span></div>' +
          '<div class="panel-pad">' +
            '<div class="tab-row">' +
              TABS.map(function (t, i) {
                return '<button class="tab" data-port="' + esc(t.port) + '"' +
                  (i === 0 ? ' data-active="true"' : "") + ">" + esc(t.label) + "</button>";
              }).join("") +
            "</div>" +
            '<div id="equip-form"></div>' +
            '<div id="equip-result" class="equip-result"></div>' +
          "</div>" +
        "</section>" +
        '<aside class="desk-note">' +
          '<div class="panel" data-tour="mission-pins">' +
            '<div class="panel-head"><h3>조사 노트 · pin된 근거</h3><span id="pin-count">0건</span></div>' +
            '<div class="panel-pad pinned-list" id="pinned-list"></div>' +
          "</div>" +
          '<div class="panel" data-tour="mission-assessment">' +
            '<div class="panel-head"><h3>판단</h3><span>우선순위 · 심각도 · 대응</span></div>' +
            '<div class="panel-pad" id="assessment-panel"></div>' +
            '<div class="panel-pad" id="eval-strip"></div>' +
          "</div>" +
          '<div class="panel" data-tour="mission-actions">' +
            '<div class="panel-head"><h3>제안된 조치 · 승인 대기</h3><span id="prop-count">0건</span></div>' +
            '<div class="panel-pad proposal-tray" id="proposal-tray"></div>' +
            '<div class="panel-pad"><button class="secondary full" id="btn-aar">대응 종료 · 사후 강평으로 이동</button></div>' +
          "</div>" +
        "</aside>" +
      "</div>";
    mount.setAttribute("data-sid", session.session_id);

    // 탭 클릭 바인딩
    Array.prototype.forEach.call(mount.querySelectorAll(".tab-row .tab"), function (b) {
      b.addEventListener("click", function () {
        var tab = TABS.filter(function (t) { return t.port === b.getAttribute("data-port"); })[0];
        if (tab) selectTab(mount, session.session_id, tab);
      });
    });
    selectTab(mount, session.session_id, TABS[0]);
    renderProposals(mount);
    renderNote(mount);
    renderAssessmentPanel(mount);

    mount.querySelector("#btn-aar").addEventListener("click", function () {
      D4D.router.go("/aar/" + session.session_id);
    });
    if (D4D.tour) {
      D4D.tour.mount("training-mission", [
        { selector: '[data-tour="mission-feed"]', title: "상황 피드", body: "이벤트가 시간순으로 들어옵니다. 장애 민원, 로그, 지시사항, 단말 상태를 한꺼번에 보고 우선순위를 잡습니다." },
        { selector: '[data-tour="mission-equipment"]', title: "목업 보안 장비", body: "장비 탭을 열고 조회해야 근거가 나옵니다. 정답 카드가 아니라 실제 업무처럼 필요한 체계를 확인하는 흐름입니다." },
        { selector: '#equip-run', title: "조회 실행", body: "조건은 시나리오에 맞게 기본 입력됩니다. 조회 후 나온 evidence를 조사 노트에 pin합니다." },
        { selector: '[data-tour="mission-pins"]', title: "근거 pin", body: "확인한 evidence ID를 모아 판단과 사후 강평에 인용합니다. 근거 없는 심각도 판단은 경고가 뜰 수 있습니다." },
        { selector: '[data-tour="mission-assessment"]', title: "판단 저장", body: "우선순위, 심각도, 대응 노력을 명시합니다. 저장하면 평가 미리보기 strip이 현재 판단 품질을 요약합니다." },
        { selector: '[data-tour="mission-actions"]', title: "사후 강평으로 종료", body: "조치 제안과 판단을 남긴 뒤 사후 강평으로 이동합니다. 정책/격리성 조치는 승인 대기 제안으로만 기록됩니다." },
      ]);
    }
  }

  // 이벤트 피드 polling — since_seq로 새 이벤트만 받아 append. 화면 이탈 시 정지.
  function startFeedPoll(mount, sid, seedEvents) {
    var events = seedEvents.slice();
    var lastSeq = events.reduce(function (m, e) { return Math.max(m, e.seq || 0); }, 0);
    renderFeed(mount, events);

    var timer = setInterval(function () {
      D4D.api.get("/api/training/sessions/" + encodeURIComponent(sid) + "/events", { since_seq: lastSeq }).then(
        function (res) {
          var fresh = res.data.items || [];
          if (!fresh.length) return;
          fresh.forEach(function (e) {
            events.push(e);
            lastSeq = Math.max(lastSeq, e.seq || 0);
          });
          renderFeed(mount, events);
        },
        function () { /* transient poll error — keep last render */ }
      );
    }, POLL_MS);

    D4D.router.onLeave(function () { clearInterval(timer); });
  }

  D4D.screens = D4D.screens || {};
  D4D.screens.missionDesk = function (mount, params) {
    mount.innerHTML = D4D.ui.loading("미션 데스크 진입 중…");
    proposals = [];
    pinnedIds = [];
    evidenceClaims = {};
    savedAssessment = null;
    var sid = params.sessionId;
    Promise.all([
      D4D.api.get("/api/training/sessions/" + encodeURIComponent(sid)),
      D4D.api.get("/api/training/sessions/" + encodeURIComponent(sid) + "/events"),
    ]).then(
      function (results) {
        render(mount, results[0].data);
        startFeedPoll(mount, sid, results[1].data.items || []);
      },
      function (e) { mount.innerHTML = D4D.ui.errorState("세션을 불러오지 못했습니다: " + e.message); }
    );
  };
})(window.D4D);
