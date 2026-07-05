/**
 * Operations Mode 화면 (A-07 셸 · A-08 상황 접수/알림 피드).
 *
 * 훈련 모드와 같은 앱에서 전환되는 실제 상황/업무 지원 라우트다. 화면마다
 * 조직 컨텍스트 바(내 조직 / 상위 조직 관점)를 공유한다.
 *
 * 구현 상태:
 *   #/ops/incidents      A-08 접수 폼 + A-09 상태별 컬럼 보드(상위 조직은 상태판 집계 포함)
 *   #/ops/notifications  A-08 — 알림 피드(미확인 우선·ack·상위 조직 합류)
 *   #/ops/incidents/:id  A-09 — timeline·근거·상태 전이(해당 조직만, 상위 조직 읽기)
 *   #/knowledge          A-10 — 지식 검색(키워드/태그/조직)·카드·축적 대시보드
 *   #/helpdesk           A-11 — 문의→검색 기반 답변(citation 강제)→해결 시 지식 축적
 *
 * 조직/사건/알림은 `GET /api/ops/units`·`/api/ops/incidents`·`/api/ops/notifications`
 * (B-08/B-09 계약)에서 온다. live API가 아직 해당 endpoint를 제공하지 않으면 units는
 * synthetic 폴백으로 셸 진입을 보장하고, 데이터 화면은 배포 대기 안내를 보여준다.
 */
window.D4D = window.D4D || {};
(function (D4D) {
  "use strict";

  var esc = function (s) { return D4D.ui.esc(s); };

  // live units API 장애 대비 폴백. 백엔드 B-08 fixture(operations.py)와 동일해야 한다.
  var FALLBACK_UNITS = [
    { unit_id: "unit-corps-cyber", name: "상위 조직-통합보안관제센터", parent_unit_id: null, role: "higher" },
    { unit_id: "unit-bn-a", name: "현장 보안팀-A", parent_unit_id: "unit-corps-cyber", role: "field" },
    { unit_id: "unit-bn-b", name: "현장 보안팀-B", parent_unit_id: "unit-corps-cyber", role: "field" },
  ];

  var SEVERITY_KO = { low: "낮음", medium: "보통", high: "높음", critical: "심각" };
  var STATUS_KO = { received: "접수", in_progress: "조치중", contained: "조치완료", closed: "종결", escalated: "상위 조직 이관", needs_approval: "승인 대기" };

  function severityBadge(sev) {
    return '<span class="ops-sev" data-sev="' + esc(sev) + '">' + esc(SEVERITY_KO[sev] || sev) + "</span>";
  }

  function unitName(unitId) {
    var units = D4D.store.opsUnits;
    for (var i = 0; i < units.length; i++) {
      if (units[i].unit_id === unitId) return units[i].name;
    }
    return unitId;
  }

  function loadUnits() {
    if (D4D.store.opsUnits.length) {
      return Promise.resolve({ fallback: false });
    }
    return D4D.api
      .get("/api/ops/units")
      .then(function (res) {
        D4D.store.setOpsUnits(res.data.items || [], res.data.default_viewer_unit_id || res.data.default_unit_id);
        return { fallback: false };
      })
      .catch(function () {
        D4D.store.setOpsUnits(FALLBACK_UNITS.slice(), "unit-bn-a");
        return { fallback: true };
      });
  }

  function roleLabel(role) {
    return role === "higher" ? "상위 조직" : "현장";
  }

  function unitBarHtml(fallback) {
    var current = D4D.store.opsUnit();
    var options = D4D.store.opsUnits
      .map(function (u) {
        var sel = current && u.unit_id === current.unit_id ? " selected" : "";
        return '<option value="' + esc(u.unit_id) + '"' + sel + ">" +
          esc(u.name) + " (" + roleLabel(u.role) + ")</option>";
      })
      .join("");
    var higher = current && current.role === "higher";
    return (
      '<div class="ops-unit-bar" data-tour="ops-unit">' +
        '<label>조직 관점 <select id="ops-unit-select">' + options + "</select></label>" +
        '<span class="ops-view-badge" data-view="' + (higher ? "higher" : "field") + '">' +
          (higher ? "상위 조직 관점 · 하위 조직 읽기 전용" : "내 조직 관점 · 조치 수행") +
        "</span>" +
        (fallback
          ? '<span class="ops-fallback-note">units API 미제공 → synthetic 폴백</span>'
          : "") +
      "</div>"
    );
  }

  function bindUnitBar(mount, rerender) {
    var sel = mount.querySelector("#ops-unit-select");
    if (sel) {
      sel.addEventListener("change", function () {
        D4D.store.setOpsUnit(sel.value);
        rerender();
      });
    }
  }

  function headHtml(title, desc) {
    var path = D4D.router && D4D.router.current ? D4D.router.current() : "";
    var tag = path.indexOf("/helpdesk") === 0 || path.indexOf("/knowledge") === 0 ? "헬프데스크 모드" : "사이버 방호 대시보드";
    return (
      '<header class="screen-head" data-tour="ops-head">' +
        "<h1>" + esc(title) + '<span class="ops-mode-tag">' + esc(tag) + "</span></h1>" +
        "<p>" + esc(desc) + "</p>" +
      "</header>"
    );
  }

  // live 서버가 아직 B-09를 제공하지 않을 때의 안내 상자.
  function pendingBackendHtml(what, ticket) {
    return (
      '<div class="ops-placeholder" data-tour="ops-pending">' +
        "<strong>" + esc(what) + " API 대기</strong>" +
        "<p>live 서버(" + esc(D4D.config.API_BASE || "") + ")가 아직 " + esc(ticket) + " endpoint를 제공하지 않습니다.</p>" +
        '<p>mock 데모: <code>app/js/config.js</code>의 <code>API_BASE</code>를 <code>null</code>로 두면 fixture로 전체 흐름을 시연할 수 있습니다.</p>' +
      "</div>"
    );
  }

  var SAFETY_LINE = '<p class="ops-safety">synthetic 조직 계층만 사용 · 알림은 인앱 레코드(외부 발송 없음) · write-like 조치는 승인 요청 제안까지만</p>';

  function mountTour(screenKey, steps) {
    if (!D4D.tour) return;
    D4D.tour.mount("ops-" + screenKey, steps);
  }

  /* ---------------- A-13/A-14: 사이버 방호 대시보드 ---------------- */

  function tileHtml(tile) {
    var cits = (tile.citations || []).map(function (id) { return "<code>" + esc(id) + "</code>"; }).join(" ");
    return (
      '<a class="kb-card" href="' + esc(tile.route || "#/dashboard") + '">' +
        '<div class="kb-card-top">' + severityBadge(tile.severity || "low") + '<strong>' + esc(tile.title) + "</strong></div>" +
        '<p class="kb-summary">출처: ' + esc(tile.source_type || "-") + " · metric " + esc(tile.metric || 0) + "</p>" +
        '<div class="kb-meta">' + (cits ? "<span>근거: " + cits + "</span>" : "<span>근거 없음</span>") + "</div>" +
      "</a>"
    );
  }

  function dashboardScreen(mount) {
    mount.innerHTML = D4D.ui.loading("사이버 방호 대시보드 불러오는 중…");
    loadUnits().then(function (state) {
      var current = D4D.store.opsUnit();
      var unitId = current ? current.unit_id : null;
      D4D.api.get("/api/dashboard/overview", { unit_id: unitId })
        .then(function (res) { render(res.data); })
        .catch(function () { render(null); });

      function render(data) {
        if (!data) {
          mount.innerHTML = '<section class="ops-screen">' + headHtml("통합 대시보드", "보안 관제 조직 핵심 상태를 한 화면에 모읍니다.") + pendingBackendHtml("대시보드", "B-15") + "</section>";
          mountTour("dashboard-pending", [
            { selector: '[data-tour="ops-head"]', title: "통합 대시보드", body: "사이버 방호 대시보드는 장비 상태, 전파/수신, 위협 동향, 지식 축적을 한 화면에 모으는 시작점입니다." },
            { selector: '[data-tour="ops-pending"]', title: "API 대기 상태", body: "백엔드 endpoint가 아직 붙지 않았을 때는 이 안내가 뜹니다. mock 또는 live 연결 상태를 먼저 확인하세요." },
          ]);
          return;
        }
        var s = data.summary || {};
        var kpis = [
          ["방호태세", (s.posture_score || 0) + "점"],
          ["미확인 전파", (s.unacked_propagations || 0) + "건"],
          ["고위험 사건", (s.open_incidents || 0) + "건"],
          ["장비 경보", (s.equipment_warnings || 0) + "건"],
          ["지식 축적", (s.knowledge_items || 0) + "건"],
        ].map(function (row) {
          return '<div class="kb-card"><div class="kb-card-top"><strong>' + esc(row[1]) + '</strong></div><p class="kb-summary">' + esc(row[0]) + "</p></div>";
        }).join("");
        var equipment = (data.equipment || []).map(function (e) {
          return '<div class="kb-card"><div class="kb-card-top">' + statusBadge(e.status === "normal" ? "contained" : "needs_approval") + '<strong>' + esc(e.label) + '</strong></div><p class="kb-summary">경보 ' + esc(e.warning_count) + "건 · " + esc(e.last_seen_at) + "</p></div>";
        }).join("");
        var threats = (data.threats || []).map(function (t) {
          return '<div class="kb-card"><div class="kb-card-top">' + severityBadge(t.severity) + '<strong>' + esc(t.title) + '</strong></div><p class="kb-summary">' + esc(t.summary) + "</p></div>";
        }).join("");
        var calendar = (data.calendar || []).map(function (task) {
          return '<li class="ntf-item"><div class="ntf-main"><strong>' + esc(task.title) + '</strong></div><div class="ntf-meta"><span>' + esc(task.due_at) + "</span><span>" + esc(task.status) + "</span></div></li>";
        }).join("");
        mount.innerHTML =
          '<section class="ops-screen">' +
            headHtml("통합 대시보드", "보안 장비·위협 동향·전파/수신·방호태세·일정·노하우를 한 화면에서 봅니다.") +
            unitBarHtml(state.fallback) +
            '<div class="kb-cards" data-tour="dashboard-kpis">' + kpis + "</div>" +
            '<div class="panel ops-panel" data-tour="dashboard-priority"><div class="panel-head"><h3>우선 확인 타일</h3><span>citation 기반</span></div><div class="kb-cards" style="padding:16px">' + (data.tiles || []).map(tileHtml).join("") + "</div></div>" +
            '<div class="panel ops-panel" data-tour="dashboard-equipment"><div class="panel-head"><h3>보안 장비 상태</h3><span>adapter read model</span></div><div class="kb-cards" style="padding:16px">' + equipment + "</div></div>" +
            '<div class="panel ops-panel" data-tour="dashboard-threats"><div class="panel-head"><h3>StealthMole 위협 동향</h3><span>masked trend</span></div><div class="kb-cards" style="padding:16px">' + threats + "</div></div>" +
            '<div class="panel ops-panel" data-tour="dashboard-calendar"><div class="panel-head"><h3>일정/임무</h3><span>오늘</span></div><ul class="ntf-list">' + calendar + "</ul></div>" +
            SAFETY_LINE +
          "</section>";
        bindUnitBar(mount, function () { dashboardScreen(mount); });
        mountTour("dashboard", [
          { selector: '[data-tour="ops-head"]', title: "통합 대시보드", body: "운영자가 처음 보는 관제 홈입니다. 요약 점수와 위험 신호를 훑고 아래 타일로 내려갑니다." },
          { selector: '[data-tour="ops-unit"]', title: "조직 관점 선택", body: "내 조직 관점은 조치 수행, 상위 조직 관점은 하위 조직 상태를 읽기 전용으로 보는 흐름입니다." },
          { selector: '[data-tour="dashboard-kpis"]', title: "핵심 지표", body: "방호태세, 미확인 전파, 고위험 사건처럼 운영자가 먼저 판단해야 하는 숫자만 모아둡니다." },
          { selector: '[data-tour="dashboard-priority"]', title: "우선 확인 타일", body: "citation이 붙은 항목부터 열어 사건, 장비, 지식DB 근거로 이어집니다." },
          { selector: '[data-tour="dashboard-equipment"]', title: "장비 상태", body: "UTM/FW, NAC, 지시사항함, ThreatIntel adapter 이상 여부를 여기서 빠르게 확인합니다." },
        ]);
      }
    });
  }

  function dashboardEquipmentScreen(mount) {
    mount.innerHTML = D4D.ui.loading("장비 상태 불러오는 중…");
    D4D.api.get("/api/dashboard/equipment", {}).then(function (res) {
      var cards = (res.data.items || []).map(function (e) {
        return '<div class="kb-card"><div class="kb-card-top">' + statusBadge(e.status === "normal" ? "contained" : "needs_approval") + '<strong>' + esc(e.label) + '</strong></div><p class="kb-summary">경보 ' + esc(e.warning_count) + "건 · source " + esc(e.source_mode) + '</p><div class="kb-meta"><span>근거: ' + (e.evidence_ids || []).map(function (id) { return "<code>" + esc(id) + "</code>"; }).join(" ") + "</span></div></div>";
      }).join("");
      mount.innerHTML = '<section class="ops-screen">' + headHtml("보안 장비 상태", "UTM/FW, NAC, 지시사항함, ThreatIntel adapter 상태입니다.") + '<div class="kb-cards" data-tour="equipment-cards">' + cards + "</div>" + SAFETY_LINE + "</section>";
      mountTour("dashboard-equipment", [
        { selector: '[data-tour="ops-head"]', title: "보안 장비 상태", body: "장비별 adapter read model을 한 화면에서 확인합니다. 실제 조치가 아니라 상태와 근거 확인용입니다." },
        { selector: '[data-tour="equipment-cards"]', title: "장비 카드", body: "경보 수, source mode, evidence ID를 보고 어떤 체계부터 열어볼지 결정합니다." },
      ]);
    }).catch(function () {
      mount.innerHTML = '<section class="ops-screen">' + headHtml("보안 장비 상태", "UTM/FW, NAC, 지시사항함, ThreatIntel adapter 상태입니다.") + pendingBackendHtml("보안 장비 상태", "B-15") + "</section>";
      mountTour("dashboard-equipment-pending", [
        { selector: '[data-tour="ops-head"]', title: "보안 장비 상태", body: "장비별 adapter 상태를 확인하는 화면입니다." },
        { selector: '[data-tour="ops-pending"]', title: "API 대기 상태", body: "장비 상태 endpoint가 아직 응답하지 않으면 이 안내가 보입니다. 백엔드 재시작 또는 mock 연결을 확인하세요." },
      ]);
    });
  }

  function dashboardThreatsScreen(mount) {
    mount.innerHTML = D4D.ui.loading("위협 동향 불러오는 중…");
    D4D.api.get("/api/dashboard/threats", {}).then(function (res) {
      var cards = (res.data.items || []).map(function (t) {
        return '<div class="kb-card"><div class="kb-card-top">' + severityBadge(t.severity) + '<strong>' + esc(t.title) + '</strong></div><p class="kb-summary">' + esc(t.summary) + '</p><div class="kb-tags">' + (t.tags || []).map(function (tag) { return '<span class="kb-tag">' + esc(tag) + "</span>"; }).join("") + "</div></div>";
      }).join("");
      mount.innerHTML = '<section class="ops-screen">' + headHtml("위협 동향", "StealthMole 기반 masked 위협 trend를 업무 판단 근거로 보여 줍니다.") + '<div class="kb-cards" data-tour="threat-cards">' + cards + "</div>" + SAFETY_LINE + "</section>";
      mountTour("dashboard-threats", [
        { selector: '[data-tour="ops-head"]', title: "위협 동향", body: "외부 위협 인텔은 판단 보강용입니다. raw 데이터가 아니라 masked trend만 보여 줍니다." },
        { selector: '[data-tour="threat-cards"]', title: "동향 카드", body: "심각도와 태그를 보고 현재 사건이나 장비 경보와 연결할 만한 근거를 찾습니다." },
      ]);
    }).catch(function () {
      mount.innerHTML = '<section class="ops-screen">' + headHtml("위협 동향", "StealthMole 기반 masked 위협 trend를 업무 판단 근거로 보여 줍니다.") + pendingBackendHtml("위협 동향", "B-15") + "</section>";
      mountTour("dashboard-threats-pending", [
        { selector: '[data-tour="ops-head"]', title: "위협 동향", body: "외부 위협 인텔을 현재 대응 판단에 연결하는 화면입니다." },
        { selector: '[data-tour="ops-pending"]', title: "API 대기 상태", body: "위협 동향 endpoint가 아직 응답하지 않으면 이 안내가 보입니다. 데이터 연결 후 카드가 표시됩니다." },
      ]);
    });
  }

  function dashboardSearchScreen(mount) {
    mount.innerHTML =
      '<section class="ops-screen">' +
        headHtml("통합 검색", "지식DB, 사건, 상담, 위협, 장비 근거를 이 한 곳에서 검색합니다.") +
        '<div class="panel ops-panel" data-tour="search-form"><form id="dash-search-form" class="kb-search"><input id="dash-q" type="text" placeholder="예: 유해 IP 지시 미반영"><select id="dash-source"><option value="">전체 출처</option><option value="incident">사건</option><option value="inquiry">상담</option><option value="aar">사후 강평</option><option value="manual">수동 지식</option></select><button class="primary" type="submit">검색</button></form></div>' +
        '<div id="dash-results" class="kb-cards" data-tour="search-results"></div>' +
        SAFETY_LINE +
      "</section>";
    var form = mount.querySelector("#dash-search-form");
    var results = mount.querySelector("#dash-results");
    function run() {
      var q = mount.querySelector("#dash-q").value.trim();
      var source = mount.querySelector("#dash-source").value;
      results.innerHTML = D4D.ui.loading("검색 중…");
      D4D.api.get("/api/knowledge/search", { q: q, source_type: source }).then(function (res) {
        var items = res.data.items || [];
        results.innerHTML = items.length ? items.map(knowledgeCardHtml).join("") : D4D.ui.emptyState("검색 결과가 없습니다.");
      }).catch(function () {
        results.innerHTML = pendingBackendHtml("통합 검색", "B-16");
      });
    }
    form.addEventListener("submit", function (e) { e.preventDefault(); run(); });
    run();
    mountTour("dashboard-search", [
      { selector: '[data-tour="ops-head"]', title: "통합 검색", body: "사건, 상담, 사후 강평, 수동 지식을 한 곳에서 찾는 진입점입니다." },
      { selector: '[data-tour="search-form"]', title: "검색 조건", body: "키워드를 넣고 출처를 좁히면 필요한 근거만 빠르게 줄일 수 있습니다." },
      { selector: '[data-tour="search-results"]', title: "근거 결과", body: "검색 결과 카드를 열어 과거 처리, evidence ID, 출처를 확인한 뒤 현재 대응에 인용합니다." },
    ]);
  }

  /* ---------------- A-08: 상황 접수 + 사건 목록 ---------------- */

  function incidentFormHtml(current) {
    if (current && current.role === "higher") {
      return (
        '<div class="panel ops-panel" data-tour="incident-form">' +
          '<div class="panel-head"><h3>상황 접수</h3><span>읽기 전용</span></div>' +
          '<p class="ops-note">상위 조직 관점은 읽기 전용입니다. 접수는 해당(현장) 조직 관점에서 수행합니다.</p>' +
        "</div>"
      );
    }
    return (
      '<div class="panel ops-panel" data-tour="incident-form">' +
        '<div class="panel-head"><h3>상황 접수</h3><span>' + esc(current ? current.name : "") + "</span></div>" +
        '<form id="ops-incident-form" class="ops-form">' +
          '<label>제목<input name="title" type="text" maxlength="120" placeholder="예: 의심 outbound 다수 관측" required></label>' +
          "<label>심각도<select name=\"severity\">" +
            '<option value="low">낮음 — 직속 상위 조직까지 통보</option>' +
            '<option value="medium" selected>보통 — 직속 상위 조직까지 통보</option>' +
            '<option value="high">높음 — 상위 조직 2단계까지 통보</option>' +
            '<option value="critical">심각 — 최상위 조직까지 통보</option>' +
          "</select></label>" +
          '<label>메모(선택)<textarea name="note" rows="2" placeholder="관측 내용 요약 (synthetic만)"></textarea></label>' +
          '<label>근거 ID(선택, 쉼표 구분)<input name="evidence" type="text" placeholder="예: fw-log-0182, nac-node-10243"></label>' +
          '<div class="ops-form-foot">' +
            '<button class="primary" type="submit">접수 · 자동 통보</button>' +
            '<span id="ops-form-msg" class="ops-form-msg"></span>' +
          "</div>" +
        "</form>" +
      "</div>"
    );
  }

  // A-09: 상태별 컬럼 보드. escalated/needs_approval은 인접 컬럼에 배지로 얹는다.
  var BOARD_COLUMNS = [
    { key: "received", label: "접수", also: ["escalated"] },
    { key: "in_progress", label: "조치중", also: ["needs_approval"] },
    { key: "contained", label: "조치완료", also: [] },
    { key: "closed", label: "종결", also: [] },
  ];

  function statusBadge(status) {
    return '<span class="ops-status" data-status="' + esc(status) + '">' + esc(STATUS_KO[status] || status) + "</span>";
  }

  function incidentCardHtml(i) {
    return (
      '<a class="ops-card" href="#/ops/incidents/' + esc(i.incident_id) + '">' +
        '<span class="ops-card-top">' + severityBadge(i.severity) + statusBadge(i.status) + "</span>" +
        "<strong>" + esc(i.title) + "</strong>" +
        '<span class="ops-card-meta">' + esc(unitName(i.unit_id)) + " · <code>" + esc(i.incident_id) + "</code></span>" +
      "</a>"
    );
  }

  function incidentBoardHtml(items) {
    var cols = BOARD_COLUMNS.map(function (col) {
      var inCol = items.filter(function (i) {
        return i.status === col.key || col.also.indexOf(i.status) !== -1;
      });
      return (
        '<div class="ops-col">' +
          '<div class="ops-col-head">' + esc(col.label) + " <span>" + inCol.length + "</span></div>" +
          (inCol.length ? inCol.map(incidentCardHtml).join("") : '<p class="ops-col-empty">없음</p>') +
        "</div>"
      );
    });
    return '<div class="ops-board">' + cols.join("") + "</div>";
  }

  function fmtElapsed(sec) {
    if (sec >= 3600) return Math.floor(sec / 3600) + "시간 " + Math.floor((sec % 3600) / 60) + "분";
    return Math.floor(sec / 60) + "분";
  }

  function statusBoardHtml(board) {
    if (!board || !board.incidents.length) return "";
    var rows = board.incidents
      .map(function (i) {
        return (
          "<tr>" +
            "<td>" + esc(unitName(i.unit_id)) + "</td>" +
            '<td><a href="#/ops/incidents/' + esc(i.incident_id) + '"><code>' + esc(i.incident_id) + "</code></a> " + esc(i.title) + "</td>" +
            "<td>" + severityBadge(i.severity) + "</td>" +
            "<td>" + statusBadge(i.status) + "</td>" +
            "<td>" + fmtElapsed(i.elapsed_seconds) + "</td>" +
            "<td><code>" + esc(i.last_transition) + "</code></td>" +
          "</tr>"
        );
      })
      .join("");
    return (
      '<div class="panel ops-panel" data-tour="status-board">' +
        '<div class="panel-head"><h3>하위 조직 상태판</h3><span>읽기 전용 · 1-2 조치 상태 공유</span></div>' +
        '<table class="ops-table"><thead><tr>' +
          "<th>조직</th><th>사건</th><th>심각도</th><th>상태</th><th>경과</th><th>최근 전이</th>" +
        "</tr></thead><tbody>" + rows + "</tbody></table>" +
      "</div>"
    );
  }

  function opsIncidentsScreen(mount) {
    mount.innerHTML = D4D.ui.loading("Operations 컨텍스트 불러오는 중…");
    var rerender = function () { opsIncidentsScreen(mount); };

    loadUnits().then(function (state) {
      var current = D4D.store.opsUnit();
      var unitId = current ? current.unit_id : null;
      var higher = current && current.role === "higher";

      var incidentsReq = D4D.api.get("/api/ops/incidents", { unit_id: unitId });
      var boardReq = higher
        ? D4D.api.get("/api/ops/status-board", { unit_id: unitId }).catch(function () { return null; })
        : Promise.resolve(null);

      Promise.all([incidentsReq, boardReq])
        .then(function (results) {
          renderIncidents(results[0].data.items || [], results[1] ? results[1].data : null, null);
        })
        .catch(function () {
          renderIncidents(null, null, "pending");
        });

      function renderIncidents(items, board, pending) {
        var boardHtml = pending
          ? pendingBackendHtml("사건 보드", "B-09/B-10")
          : '<div class="panel ops-panel" data-tour="incident-board">' +
              '<div class="panel-head"><h3>사건 보드</h3><span>' +
                (higher ? "하위 조직 합류 표시" : "내 조직") +
              "</span></div>" +
              incidentBoardHtml(items) +
            "</div>" +
            (higher ? statusBoardHtml(board) : "");

        mount.innerHTML =
          '<section class="ops-screen">' +
            headHtml("상위 조직/하급제대 전파/수신", "사건 접수 시 해당 조직와 상위 조직 체인에 자동 통보되고, 조치 상태는 상위 조직 조직에 읽기 전용으로 공유됩니다.") +
            unitBarHtml(state.fallback) +
            '<div id="ops-created-banner"></div>' +
            incidentFormHtml(current) +
            boardHtml +
            SAFETY_LINE +
          "</section>";

        bindUnitBar(mount, rerender);
        bindIncidentForm(mount, unitId, rerender);
        mountTour("incidents", [
          { selector: '[data-tour="ops-head"]', title: "전파/수신 화면", body: "사건을 접수하면 해당 조직와 상위 조직 체인에 인앱 알림이 전파되고 상태가 공유됩니다." },
          { selector: '[data-tour="ops-unit"]', title: "관점 먼저 선택", body: "현장 조직 관점에서는 접수와 상태 전이를 수행하고, 상위 조직 관점에서는 하위 조직 현황을 읽기 전용으로 봅니다." },
          { selector: '[data-tour="incident-form"]', title: "상황 접수", body: "제목, 심각도, 메모, 근거 ID를 넣고 접수하면 심각도 규칙에 따라 자동 통보됩니다." },
          { selector: '[data-tour="incident-board"]', title: "사건 보드", body: "접수, 조치중, 조치완료, 종결 컬럼으로 현재 처리 단계를 확인합니다. 카드를 누르면 상세로 들어갑니다." },
          { selector: '[data-tour="status-board"]', title: "하위 조직 상태판", body: "상위 조직 관점일 때 하위 조직의 조치 경과와 최근 전이를 한 번에 확인합니다." },
        ]);
      }
    });
  }

  function bindIncidentForm(mount, unitId, rerender) {
    var form = mount.querySelector("#ops-incident-form");
    if (!form) return;
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var msg = mount.querySelector("#ops-form-msg");
      var title = form.querySelector('[name="title"]').value.trim();
      var severity = form.querySelector('[name="severity"]').value;
      var note = form.querySelector('[name="note"]').value.trim();
      var evidenceRaw = form.querySelector('[name="evidence"]').value.trim();
      var evidenceIds = evidenceRaw
        ? evidenceRaw.split(",").map(function (s) { return s.trim(); }).filter(Boolean)
        : [];
      if (!title) {
        if (msg) msg.textContent = "제목을 입력하세요.";
        return;
      }
      if (msg) msg.textContent = "접수 중…";
      D4D.api
        .post("/api/ops/incidents", {
          unit_id: unitId,
          title: title,
          severity: severity,
          note: note,
          evidence_ids: evidenceIds,
        })
        .then(function (res) {
          var d = res.data;
          var names = (d.notified_unit_ids || []).map(unitName).join(", ");
          // 접수 성공 → 목록 재로딩. 배너는 재렌더 후 채운다.
          rerender();
          window.setTimeout(function () {
            var banner = document.getElementById("ops-created-banner");
            if (banner) {
              banner.innerHTML =
                '<div class="ops-banner">사건 <code>' + esc(d.incident_id) + "</code> 접수 완료 · " +
                "자동 통보: " + esc(names) + " (" + severityBadge(d.severity) + " 전파 규칙)</div>";
            }
          }, 0);
        })
        .catch(function (errRes) {
          if (msg) msg.textContent = "접수 실패: " + (errRes && errRes.message ? errRes.message : "오류");
        });
    });
  }

  /* ---------------- A-08: 알림 피드 ---------------- */

  function notificationItemsHtml(items) {
    if (!items.length) {
      return '<p class="ops-note">알림이 없습니다.</p>';
    }
    return (
      '<ul class="ntf-list">' +
      items
        .map(function (n) {
          return (
            '<li class="ntf-item" data-read="' + (n.read ? "true" : "false") + '">' +
              '<div class="ntf-main">' +
                severityBadge(n.severity) +
                '<span class="ntf-kind">' + (n.kind === "incident_opened" ? "상황 발생" : esc(n.kind)) + "</span>" +
                '<strong>' + esc(n.title) + "</strong>" +
              "</div>" +
              '<div class="ntf-meta">' +
                "<span>수신: " + esc(unitName(n.to_unit_id)) + "</span>" +
                '<a href="#/ops/incidents/' + esc(n.incident_id) + '">' + esc(n.incident_id) + "</a>" +
                "<span>" + esc(n.created_at) + "</span>" +
                (n.read
                  ? '<span class="ntf-read">확인됨</span>'
                  : '<button type="button" class="ntf-ack" data-ntf="' + esc(n.notification_id) + '">확인</button>') +
              "</div>" +
            "</li>"
          );
        })
        .join("") +
      "</ul>"
    );
  }

  function opsNotificationsScreen(mount) {
    mount.innerHTML = D4D.ui.loading("알림 불러오는 중…");
    var rerender = function () { opsNotificationsScreen(mount); };

    loadUnits().then(function (state) {
      var current = D4D.store.opsUnit();
      var unitId = current ? current.unit_id : null;
      var higher = current && current.role === "higher";

      D4D.api
        .get("/api/ops/notifications", { unit_id: unitId })
        .then(function (res) {
          render(res.data.items || [], res.data.unread_count || 0, null);
        })
        .catch(function () {
          render(null, 0, "pending");
        });

      function render(items, unread, pending) {
        var bodyHtml = pending
          ? pendingBackendHtml("알림 피드", "B-09")
          : '<div class="panel ops-panel" data-tour="notification-feed">' +
              '<div class="panel-head"><h3>알림 피드</h3><span>미확인 ' + unread + "건 우선</span></div>" +
              (higher ? '<p class="ops-note">상위 조직 관점 — 하위 조직에서 전파된 알림이 합류해 보입니다.</p>' : "") +
              notificationItemsHtml(items) +
            "</div>";

        mount.innerHTML =
          '<section class="ops-screen">' +
            headHtml("알림 피드", "사건 발생·상태 변경 시 해당 조직와 상위 조직 체인에 생성되는 인앱 통보입니다(외부 발송 없음).") +
            unitBarHtml(state.fallback) +
            bodyHtml +
            SAFETY_LINE +
          "</section>";

        bindUnitBar(mount, rerender);
        mountTour("notifications", [
          { selector: '[data-tour="ops-head"]', title: "알림 피드", body: "상황 발생과 상태 변경이 외부 발송 없이 인앱 알림으로 쌓입니다." },
          { selector: '[data-tour="ops-unit"]', title: "수신 조직 선택", body: "조직 관점을 바꾸면 해당 조직가 받은 알림만 보거나 상위 조직 관점에서 하위 알림을 합류해 볼 수 있습니다." },
          { selector: '[data-tour="notification-feed"]', title: "미확인 우선", body: "읽지 않은 알림이 먼저 보입니다. 확인 버튼을 눌러 운영자가 봤다는 기록을 남깁니다." },
        ]);
        Array.prototype.forEach.call(mount.querySelectorAll(".ntf-ack"), function (btn) {
          btn.addEventListener("click", function () {
            D4D.api
              .post("/api/ops/notifications/" + btn.getAttribute("data-ntf") + "/ack", {})
              .then(rerender)
              .catch(rerender);
          });
        });
      }
    });
  }

  /* ---------------- A-09: 사건 상세 · 상태 전이 ---------------- */

  var TRANSITION_KO = {
    in_progress: "조치 시작",
    contained: "조치 완료",
    closed: "종결",
    needs_approval: "승인 필요 조치 상신(제안)",
    escalated: "상위 조직 이관",
  };

  function timelineHtml(items) {
    if (!items.length) return '<p class="ops-note">기록이 없습니다.</p>';
    return (
      '<ol class="ops-timeline">' +
      items
        .map(function (t) {
          var move = t.from
            ? esc(STATUS_KO[t.from] || t.from) + " → " + esc(STATUS_KO[t.to] || t.to)
            : "접수 (" + esc(STATUS_KO[t.to] || t.to) + ")";
          var evd = (t.evidence_ids || []).length
            ? '<span class="ops-evd">근거: ' + t.evidence_ids.map(function (id) { return "<code>" + esc(id) + "</code>"; }).join(" ") + "</span>"
            : "";
          return (
            "<li>" +
              '<div class="ops-tl-head"><strong>' + move + "</strong><span>" + esc(t.at) + "</span></div>" +
              '<div class="ops-tl-body">' +
                "<span>" + esc(unitName(t.actor_unit)) + "</span>" +
                (t.note ? "<span>" + esc(t.note) + "</span>" : "") +
                evd +
              "</div>" +
            "</li>"
          );
        })
        .join("") +
      "</ol>"
    );
  }

  function transitionPanelHtml(inc, viewerUnitId) {
    if (inc.status === "closed") {
      return '<p class="ops-note">종결된 사건입니다. 조치 경위는 timeline에 비휘발로 남습니다.</p>';
    }
    if (viewerUnitId !== inc.unit_id) {
      return '<p class="ops-note">상위 조직 관점 — 읽기 전용입니다. 상태 전이는 발생 조직(' + esc(unitName(inc.unit_id)) + ")만 수행합니다.</p>";
    }
    var buttons = (inc.allowed_transitions || [])
      .map(function (to) {
        var approval = to === "needs_approval";
        return (
          '<button type="button" class="ops-transition' + (approval ? " approval" : "") + '" data-to="' + esc(to) + '">' +
            esc(TRANSITION_KO[to] || to) +
          "</button>"
        );
      })
      .join("");
    return (
      '<div class="ops-transition-panel">' +
        '<label>조치 메모(선택)<input id="ops-tr-note" type="text" maxlength="160" placeholder="예: 차단 정책 반영 요청 상신"></label>' +
        '<div class="ops-transition-btns">' + buttons + "</div>" +
        '<p class="ops-note">승인 필요 조치는 제안으로만 기록됩니다(실행 아님). 전이 시 상위 조직 조직에 상태 변경 알림이 전파됩니다.</p>' +
      "</div>"
    );
  }

  function opsIncidentDetailScreen(mount, params) {
    mount.innerHTML = D4D.ui.loading("사건 불러오는 중…");
    var incidentId = params && params.incidentId;
    var rerender = function () { opsIncidentDetailScreen(mount, params); };

    loadUnits().then(function (state) {
      var current = D4D.store.opsUnit();
      var viewerUnitId = current ? current.unit_id : null;

      D4D.api
        .get("/api/ops/incidents/" + incidentId)
        .then(function (res) { render(res.data); })
        .catch(function (errRes) {
          mount.innerHTML =
            '<section class="ops-screen">' +
              headHtml("사건 상세", "사건을 불러올 수 없습니다.") +
              unitBarHtml(state.fallback) +
              (errRes && errRes.code === "NOT_FOUND"
                ? D4D.ui.errorState("사건을 찾을 수 없습니다: " + incidentId)
                : pendingBackendHtml("사건 상세", "B-10")) +
            "</section>";
          bindUnitBar(mount, rerender);
        });

      function render(inc) {
        var evdChips = (inc.evidence_ids || []).length
          ? inc.evidence_ids.map(function (id) { return "<code>" + esc(id) + "</code>"; }).join(" ")
          : '<span class="ops-note">인용된 근거 없음</span>';
        var ntfRows = (inc.notifications || [])
          .map(function (n) {
            return (
              "<li>" +
                (n.kind === "incident_opened" ? "상황 발생" : "상태 변경") + " → " + esc(unitName(n.to_unit_id)) +
                " · " + esc(n.created_at) + (n.read ? " · 확인됨" : " · 미확인") +
              "</li>"
            );
          })
          .join("");

        mount.innerHTML =
          '<section class="ops-screen">' +
            headHtml("사건 상세", "상태 전이는 발생 조직만 수행하고, 모든 전이는 timeline에 비휘발로 기록됩니다.") +
            unitBarHtml(state.fallback) +
            '<div class="panel ops-panel" data-tour="incident-summary">' +
              '<div class="panel-head"><h3>' + esc(inc.title) + "</h3><span><code>" + esc(inc.incident_id) + "</code></span></div>" +
              '<div class="ops-detail-meta">' +
                severityBadge(inc.severity) + statusBadge(inc.status) +
                "<span>발생 조직: " + esc(unitName(inc.unit_id)) + "</span>" +
                "<span>접수: " + esc(inc.created_at) + "</span>" +
              "</div>" +
              '<div class="ops-detail-evd">근거: ' + evdChips + "</div>" +
            "</div>" +
            '<div id="ops-tr-banner"></div>' +
            '<div class="panel ops-panel" data-tour="transition-panel">' +
              '<div class="panel-head"><h3>상태 전이</h3><span>' + esc(STATUS_KO[inc.status] || inc.status) + "</span></div>" +
              transitionPanelHtml(inc, viewerUnitId) +
            "</div>" +
            '<div class="panel ops-panel" data-tour="timeline-panel">' +
              '<div class="panel-head"><h3>Timeline</h3><span>비휘발 기록</span></div>' +
              timelineHtml(inc.timeline || []) +
            "</div>" +
            '<div class="panel ops-panel" data-tour="notification-history">' +
              '<div class="panel-head"><h3>알림 이력</h3><span>인앱 레코드</span></div>' +
              (ntfRows ? '<ul class="ops-ntf-history">' + ntfRows + "</ul>" : '<p class="ops-note">알림 없음</p>') +
            "</div>" +
            SAFETY_LINE +
          "</section>";

        bindUnitBar(mount, rerender);
        mountTour("incident-detail", [
          { selector: '[data-tour="ops-head"]', title: "사건 상세", body: "하나의 사건에서 근거, 상태 전이, timeline, 알림 이력을 함께 봅니다." },
          { selector: '[data-tour="incident-summary"]', title: "사건 요약", body: "심각도, 현재 상태, 발생 조직, 근거 ID를 먼저 확인합니다." },
          { selector: '[data-tour="transition-panel"]', title: "상태 전이", body: "발생 조직 관점일 때만 조치 시작, 조치 완료, 종결 같은 전이를 수행할 수 있습니다." },
          { selector: '[data-tour="timeline-panel"]', title: "비휘발 Timeline", body: "누가 언제 어떤 상태로 바꿨는지 남아 다음 운영자와 상위 조직 조직가 추적할 수 있습니다." },
          { selector: '[data-tour="notification-history"]', title: "알림 이력", body: "어느 조직에 어떤 알림이 전달됐고 확인됐는지 기록으로 봅니다." },
        ]);
        Array.prototype.forEach.call(mount.querySelectorAll(".ops-transition"), function (btn) {
          btn.addEventListener("click", function () {
            var noteEl = mount.querySelector("#ops-tr-note");
            D4D.api
              .post("/api/ops/incidents/" + inc.incident_id + "/status", {
                to_status: btn.getAttribute("data-to"),
                actor_unit_id: viewerUnitId,
                note: noteEl ? noteEl.value.trim() : "",
                evidence_ids: [],
              })
              .then(function (res) {
                rerender();
                window.setTimeout(function () {
                  var banner = document.getElementById("ops-tr-banner");
                  if (banner) {
                    var d = res.data;
                    banner.innerHTML =
                      '<div class="ops-banner">상태가 ' + esc(STATUS_KO[d.status] || d.status) + "(으)로 전이되었습니다" +
                      (d.approval_required ? " · <strong>승인 대기 제안으로 기록 (실행 아님)</strong>" : "") +
                      (d.notifications && d.notifications.length
                        ? " · 상위 조직 통보: " + d.notifications.map(function (n) { return esc(unitName(n.to_unit_id)); }).join(", ")
                        : "") +
                      "</div>";
                  }
                }, 0);
              })
              .catch(function (errRes) {
                var banner = document.getElementById("ops-tr-banner");
                if (banner) {
                  banner.innerHTML = '<div class="ops-banner error">전이 실패: ' + esc(errRes && errRes.message ? errRes.message : "오류") + "</div>";
                }
              });
          });
        });
      }
    });
  }

  /* ---------------- A-10: 지식DB ---------------- */

  var SOURCE_KO = { incident: "사건", action: "조치", aar: "훈련 사후 강평", inquiry: "문의 FAQ", manual: "수동" };

  function displayText(value) {
    return String(value == null ? "" : value)
      .replace(/훈련AAR/g, "훈련 사후 강평")
      .replace(/AAR/g, "사후 강평");
  }

  function knowledgeCardHtml(k) {
    var tags = k.tags.map(function (t) { return '<span class="kb-tag">' + esc(displayText(t)) + "</span>"; }).join("");
    var evd = (k.evidence_ids || []).map(function (id) { return "<code>" + esc(id) + "</code>"; }).join(" ");
    return (
      '<article class="kb-card">' +
        '<div class="kb-card-top">' +
          '<span class="kb-source" data-source="' + esc(k.source_type) + '">' + esc(SOURCE_KO[k.source_type] || k.source_type) + "</span>" +
          "<strong>" + esc(displayText(k.title)) + "</strong>" +
        "</div>" +
        '<p class="kb-summary">' + esc(displayText(k.summary)) + "</p>" +
        (k.resolution ? '<p class="kb-resolution">과거 처리: ' + esc(displayText(k.resolution)) + "</p>" : "") +
        '<div class="kb-tags">' + tags + "</div>" +
        '<div class="kb-meta">' +
          (evd ? "<span>근거: " + evd + "</span>" : '<span class="ops-note">근거 없음</span>') +
          "<span>" + esc(k.unit_id ? unitName(k.unit_id) : "-") + "</span>" +
          "<span>" + esc(k.created_at) + "</span>" +
          "<span>출처: <code>" + esc(k.source_id) + "</code></span>" +
        "</div>" +
      "</article>"
    );
  }

  function knowledgeScreen(mount) {
    var filters = { query: "", tag: "", unit: "" };

    function screenRender() {
      mount.innerHTML = D4D.ui.loading("지식DB 불러오는 중…");
      loadUnits().then(function (state) {
        D4D.api
          .get("/api/knowledge", {
            query: filters.query || null,
            tags: filters.tag || null,
            unit_id: filters.unit || null,
          })
          .then(function (res) { render(state, res.data); })
          .catch(function () {
            mount.innerHTML =
              '<section class="ops-screen">' +
                headHtml("지식DB", "축적된 업무 지식을 검색합니다.") +
                unitBarHtml(state.fallback) +
                pendingBackendHtml("지식DB", "B-11") +
              "</section>";
            bindUnitBar(mount, screenRender);
          });
      });
    }

    function render(state, data) {
      var srcSummary = Object.keys(data.by_source || {})
        .map(function (s) { return esc(SOURCE_KO[s] || s) + " " + data.by_source[s]; })
        .join(" · ");
      var unitSummary = Object.keys(data.by_unit || {})
        .map(function (u) { return esc(unitName(u)) + " " + data.by_unit[u]; })
        .join(" · ");
      var tagChips = (data.top_tags || [])
        .map(function (t) {
          var active = filters.tag === t.tag ? ' data-active="true"' : "";
          return '<button type="button" class="kb-tag-chip" data-tag="' + esc(t.tag) + '"' + active + ">" +
            esc(displayText(t.tag)) + " <span>" + t.count + "</span></button>";
        })
        .join("");
      var unitOptions = ['<option value="">전체 조직</option>']
        .concat(
          D4D.store.opsUnits.map(function (u) {
            var sel = filters.unit === u.unit_id ? " selected" : "";
            return '<option value="' + esc(u.unit_id) + '"' + sel + ">" + esc(u.name) + "</option>";
          })
        )
        .join("");
      var cards = (data.items || []).length
        ? data.items.map(knowledgeCardHtml).join("")
        : D4D.ui.emptyState("조건에 맞는 지식이 없습니다.");

      mount.innerHTML =
        '<section class="ops-screen">' +
          headHtml("지식DB", "사건·조치·사후 강평·해결 문의에서 자동 축적되는 비휘발 업무 지식입니다. 담당자가 인수인계해도 DB에 남습니다(2-2).") +
          unitBarHtml(state.fallback) +
          '<div class="panel ops-panel" data-tour="knowledge-stats">' +
            '<div class="panel-head"><h3>축적 현황</h3><span>총 ' + (data.total || 0) + "건</span></div>" +
            '<div class="kb-dash">' +
              "<span>출처: " + (srcSummary || "-") + "</span>" +
              "<span>조직 기여: " + (unitSummary || "-") + "</span>" +
            "</div>" +
          "</div>" +
          '<div class="panel ops-panel" data-tour="knowledge-search">' +
            '<div class="panel-head"><h3>검색</h3><span>키워드 · 태그 · 조직</span></div>' +
            '<form id="kb-search-form" class="kb-search">' +
              '<input id="kb-query" type="text" placeholder="키워드 (예: 유해 IP, 격리, 크리덴셜)" value="' + esc(filters.query) + '">' +
              '<select id="kb-unit">' + unitOptions + "</select>" +
              '<button class="primary" type="submit">검색</button>' +
              '<button type="button" id="kb-clear">초기화</button>' +
            "</form>" +
            '<div class="kb-tag-chips">' + tagChips + "</div>" +
          "</div>" +
          '<div class="kb-cards" data-tour="knowledge-cards">' + cards + "</div>" +
          SAFETY_LINE +
        "</section>";

      bindUnitBar(mount, screenRender);
      mountTour("knowledge", [
        { selector: '[data-tour="ops-head"]', title: "지식DB", body: "사건, 사후 강평, 문의 해결 결과가 축적되는 비휘발 업무 지식 화면입니다." },
        { selector: '[data-tour="ops-unit"]', title: "조직 필터", body: "현재 조직 관점에 맞춰 지식 기여와 검색 결과를 좁혀 볼 수 있습니다." },
        { selector: '[data-tour="knowledge-stats"]', title: "축적 현황", body: "출처별·조직별로 어떤 지식이 쌓였는지 먼저 확인합니다." },
        { selector: '[data-tour="knowledge-search"]', title: "검색과 태그", body: "키워드, 태그, 조직 필터를 조합해 과거 처리 절차를 찾습니다." },
        { selector: '[data-tour="knowledge-cards"]', title: "지식 카드", body: "요약, 과거 처리, evidence, source ID를 현재 대응이나 상담 답변에 인용합니다." },
      ]);
      var form = mount.querySelector("#kb-search-form");
      if (form) {
        form.addEventListener("submit", function (e) {
          e.preventDefault();
          filters.query = mount.querySelector("#kb-query").value.trim();
          filters.unit = mount.querySelector("#kb-unit").value;
          screenRender();
        });
      }
      var clearBtn = mount.querySelector("#kb-clear");
      if (clearBtn) {
        clearBtn.addEventListener("click", function () {
          filters.query = ""; filters.tag = ""; filters.unit = "";
          screenRender();
        });
      }
      Array.prototype.forEach.call(mount.querySelectorAll(".kb-tag-chip"), function (chip) {
        chip.addEventListener("click", function () {
          var t = chip.getAttribute("data-tag");
          filters.tag = filters.tag === t ? "" : t;
          screenRender();
        });
      });
    }

    screenRender();
  }

  /* ---------------- A-11: 헬프데스크 ---------------- */

  var ENGINE_KO = { rule: "규칙/검색", llm: "LLM API" };

  function citationHtml(citations) {
    var kids = (citations && citations.knowledge_ids) || [];
    var evds = (citations && citations.evidence_ids) || [];
    if (!kids.length && !evds.length) return "";
    return (
      '<div class="inq-citations">' +
        (kids.length
          ? "<span>지식 근거: " + kids.map(function (id) { return '<a href="#/knowledge"><code>' + esc(id) + "</code></a>"; }).join(" ") + "</span>"
          : "") +
        (evds.length
          ? "<span>evidence: " + evds.map(function (id) { return "<code>" + esc(id) + "</code>"; }).join(" ") + "</span>"
          : "") +
      "</div>"
    );
  }

  function inquiryItemHtml(inq) {
    var resolved = inq.status === "resolved";
    return (
      '<li class="inq-item" data-grounded="' + (inq.grounded ? "true" : "false") + '">' +
        '<div class="inq-q"><strong>Q.</strong> ' + esc(inq.question) + "</div>" +
        '<div class="inq-a">' +
          '<span class="inq-engine">' + esc(ENGINE_KO[inq.engine] || inq.engine) + " · " + esc(inq.confidence) + "</span>" +
          (inq.grounded ? "" : '<span class="inq-warn">근거 부족</span>') +
          "<p>" + esc(inq.answer) + "</p>" +
          citationHtml(inq.citations) +
        "</div>" +
        '<div class="inq-foot">' +
          "<span>" + esc(inq.unit_id ? unitName(inq.unit_id) : "-") + " · " + esc(inq.created_at) + "</span>" +
          (resolved
            ? '<span class="inq-resolved">해결됨 · 지식 축적</span>'
            : '<button type="button" class="inq-resolve" data-inq="' + esc(inq.inquiry_id) + '">해결 처리 → 지식 축적</button>') +
        "</div>" +
      "</li>"
    );
  }

  function helpdeskScreen(mount) {
    mount.innerHTML = D4D.ui.loading("헬프데스크 불러오는 중…");
    var rerender = function () { helpdeskScreen(mount); };

    loadUnits().then(function (state) {
      var current = D4D.store.opsUnit();
      var unitId = current ? current.unit_id : null;

      D4D.api
        .get("/api/helpdesk/inquiries", {})
        .then(function (res) { render(res.data.items || []); })
        .catch(function () { render(null); });

      function render(items) {
        var listHtml =
          items === null
            ? pendingBackendHtml("헬프데스크", "B-12")
            : '<div class="panel ops-panel">' +
                '<div class="panel-head"><h3>문의 이력</h3><span>' + items.length + "건</span></div>" +
                (items.length
                  ? '<ul class="inq-list">' + items.map(inquiryItemHtml).join("") + "</ul>"
                  : '<p class="ops-note">아직 문의가 없습니다. 위에서 첫 문의를 등록해 보세요.</p>') +
              "</div>";

        mount.innerHTML =
          '<section class="ops-screen">' +
            headHtml("헬프데스크", "문의를 지식DB에서 검색해 답변합니다(2-1). 답변에는 항상 근거 인용 또는 근거 부족 표시가 붙고, 해결된 문의는 FAQ 지식으로 축적됩니다.") +
            unitBarHtml(state.fallback) +
            '<div class="panel ops-panel" data-tour="inquiry-form">' +
              '<div class="panel-head"><h3>문의 등록</h3><span>' + esc(current ? current.name : "") + "</span></div>" +
              '<form id="inq-form" class="ops-form">' +
                '<label>문의 내용<textarea name="question" rows="2" maxlength="300" placeholder="예: 유해 IP 지시 반영이 일부 누락됐을 때 절차는?" required></textarea></label>' +
                '<div class="ops-form-foot">' +
                  '<button class="primary" type="submit">문의 → 답변 받기</button>' +
                  '<span id="inq-form-msg" class="ops-form-msg"></span>' +
                "</div>" +
              "</form>" +
            "</div>" +
            '<div id="inq-banner"></div>' +
            listHtml +
            SAFETY_LINE +
          "</section>";

        bindUnitBar(mount, rerender);
        mountTour("helpdesk-inquiries", [
          { selector: '[data-tour="ops-head"]', title: "헬프데스크 문의", body: "문의 내용을 지식DB에서 검색해 근거 있는 답변 또는 근거 부족 상태로 돌려줍니다." },
          { selector: '[data-tour="ops-unit"]', title: "문의 조직", body: "문의가 어느 조직 관점에서 들어왔는지 선택합니다. 답변과 축적 지식에 함께 남습니다." },
          { selector: '[data-tour="inquiry-form"]', title: "문의 등록", body: "질문을 입력하고 답변 받기를 누르면 검색 기반 답변이 생성됩니다." },
          { selector: ".inq-list", title: "문의 이력", body: "답변의 근거 인용과 근거 부족 표시를 확인하고, 해결 처리하면 FAQ 지식으로 축적됩니다." },
        ]);
        var form = mount.querySelector("#inq-form");
        if (form) {
          form.addEventListener("submit", function (e) {
            e.preventDefault();
            var q = form.querySelector('[name="question"]').value.trim();
            var msg = mount.querySelector("#inq-form-msg");
            if (!q) { if (msg) msg.textContent = "문의 내용을 입력하세요."; return; }
            if (msg) msg.textContent = "답변 생성 중…";
            D4D.api
              .post("/api/helpdesk/inquiries", { unit_id: unitId, question: q })
              .then(rerender)
              .catch(function (errRes) {
                if (msg) msg.textContent = "실패: " + (errRes && errRes.message ? errRes.message : "오류");
              });
          });
        }
        Array.prototype.forEach.call(mount.querySelectorAll(".inq-resolve"), function (btn) {
          btn.addEventListener("click", function () {
            D4D.api
              .post("/api/helpdesk/inquiries/" + btn.getAttribute("data-inq") + "/resolve", {})
              .then(function (res) {
                rerender();
                window.setTimeout(function () {
                  var banner = document.getElementById("inq-banner");
                  if (banner) {
                    banner.innerHTML =
                      '<div class="ops-banner">문의가 해결 처리되어 지식 <code>' +
                      esc(res.data.accumulated_knowledge_id) +
                      "</code>(으)로 축적되었습니다. 담당자가 인수인계해도 지식DB에 남습니다.</div>";
                  }
                }, 0);
              })
              .catch(rerender);
          });
        });
      }
    });
  }

  /* ---------------- A-16/A-17: 헬프데스크 모드 ---------------- */

  var CATEGORY_KO = {
    simple_question: "단순 문의",
    password_reset: "비밀번호 변경",
    firewall_policy_request: "방화벽 정책 요청",
    network_equipment_issue: "네트워크/장비 이상",
    incident_report: "침해사고 신고",
  };

  function conversationCardHtml(c) {
    return (
      '<a class="inq-item" href="#/helpdesk/conversations/' + esc(c.conversation_id) + '" data-grounded="' + (c.status !== "needs_review") + '">' +
        '<div class="inq-q"><strong>' + esc(CATEGORY_KO[c.category] || c.category) + "</strong> · " + esc(c.priority) + "</div>" +
        '<div class="inq-a"><span class="inq-engine">' + esc(c.autopilot_level) + " · " + esc(c.confidence) + "</span><p>" + esc(c.question) + "</p></div>" +
        '<div class="inq-foot"><span>' + esc(c.unit_id ? unitName(c.unit_id) : "-") + " · " + esc(c.created_at || "") + "</span><span>" + esc(c.status) + "</span></div>" +
      "</a>"
    );
  }

  function helpdeskInboxScreen(mount) {
    mount.innerHTML = D4D.ui.loading("헬프데스크 인입 채팅 불러오는 중…");
    var rerender = function () { helpdeskInboxScreen(mount); };
    loadUnits().then(function (state) {
      var current = D4D.store.opsUnit();
      var unitId = current ? current.unit_id : null;
      D4D.api.get("/api/helpdesk/conversations", {}).then(function (res) {
        render(res.data.items || []);
      }).catch(function () { render(null); });

      function render(items) {
        var grouped = {};
        (items || []).forEach(function (c) {
          grouped[c.category] = (grouped[c.category] || 0) + 1;
        });
        var queue = Object.keys(CATEGORY_KO).map(function (cat) {
          return '<div class="kb-card"><div class="kb-card-top"><strong>' + esc(grouped[cat] || 0) + "건</strong></div><p class=\"kb-summary\">" + esc(CATEGORY_KO[cat]) + "</p></div>";
        }).join("");
        mount.innerHTML =
          '<section class="ops-screen">' +
            headHtml("인입 채팅", "장병 문의 채팅을 받고 유형별로 자동 분류해 운영자 대응 워크벤치로 넘깁니다.") +
            unitBarHtml(state.fallback) +
            '<div class="panel ops-panel" data-tour="conversation-form">' +
              '<div class="panel-head"><h3>채팅 인입</h3><span>' + esc(current ? current.name : "") + "</span></div>" +
              '<form id="conv-form" class="ops-form">' +
                '<label>문의 메시지<textarea name="message" rows="2" maxlength="300" placeholder="예: 온나라 계정 비밀번호 초기화가 필요합니다." required></textarea></label>' +
                '<div class="ops-form-foot"><button class="primary" type="submit">채팅 인입 · 자동 분류</button><span id="conv-form-msg" class="ops-form-msg"></span></div>' +
              "</form>" +
            "</div>" +
            '<div class="panel ops-panel" data-tour="conversation-queue"><div class="panel-head"><h3>유형별 큐</h3><span>자동 분류</span></div><div class="kb-cards" style="padding:16px">' + queue + "</div></div>" +
            '<div class="panel ops-panel" data-tour="conversation-list"><div class="panel-head"><h3>상담 대기열</h3><span>' + (items ? items.length : 0) + "건</span></div>" +
              (items === null ? pendingBackendHtml("상담 대기열", "B-17") : (items.length ? '<ul class="inq-list">' + items.map(conversationCardHtml).join("") + "</ul>" : '<p class="ops-note">아직 상담이 없습니다.</p>')) +
            "</div>" +
            SAFETY_LINE +
          "</section>";
        bindUnitBar(mount, rerender);
        mountTour("helpdesk-inbox", [
          { selector: '[data-tour="ops-head"]', title: "인입 채팅", body: "장병 문의를 접수해 유형과 우선순위를 자동 분류하는 헬프데스크 시작 화면입니다." },
          { selector: '[data-tour="ops-unit"]', title: "담당 조직", body: "문의가 들어온 조직 관점을 먼저 맞춥니다." },
          { selector: '[data-tour="conversation-form"]', title: "채팅 인입", body: "문의 메시지를 입력하고 자동 분류를 누르면 대응 워크벤치로 이동합니다." },
          { selector: '[data-tour="conversation-queue"]', title: "유형별 큐", body: "비밀번호 변경, 방화벽 정책 요청, 장비 이상 같은 유형별 부담을 빠르게 봅니다." },
          { selector: '[data-tour="conversation-list"]', title: "상담 대기열", body: "열린 상담을 눌러 자동 분류, 관련 지식, 추천 조치를 검토합니다." },
        ]);
        var form = mount.querySelector("#conv-form");
        if (form) {
          form.addEventListener("submit", function (e) {
            e.preventDefault();
            var msg = form.querySelector('[name="message"]').value.trim();
            var note = mount.querySelector("#conv-form-msg");
            if (!msg) { if (note) note.textContent = "문의 메시지를 입력하세요."; return; }
            if (note) note.textContent = "분류 중…";
            D4D.api.post("/api/helpdesk/conversations", { unit_id: unitId, message: msg })
              .then(function (res) { D4D.router.go("/helpdesk/conversations/" + res.data.conversation_id); })
              .catch(function (errRes) { if (note) note.textContent = "실패: " + (errRes && errRes.message ? errRes.message : "오류"); });
          });
        }
      }
    });
  }

  function helpdeskWorkbenchScreen(mount, params) {
    var id = params.conversationId;
    mount.innerHTML = D4D.ui.loading("대응 워크벤치 불러오는 중…");
    D4D.api.get("/api/helpdesk/conversations/" + id + "/workbench", {}).then(function (res) {
      var data = res.data;
      var c = data.conversation;
      var cls = data.classification || {};
      var related = (data.related_knowledge || []).map(knowledgeCardHtml).join("");
      var actions = (data.suggested_actions || []).map(function (a) {
        return '<div class="kb-card"><div class="kb-card-top">' + statusBadge(a.required_approval ? "needs_approval" : "contained") + '<strong>' + esc(a.action_type) + '</strong></div><p class="kb-summary">' + esc(a.summary) + '</p><div class="kb-meta"><span>approval: ' + esc(a.required_approval) + "</span><span>executed: " + esc(a.executed) + "</span></div></div>";
      }).join("");
      mount.innerHTML =
        '<section class="ops-screen">' +
          headHtml("대응 워크벤치", "자동 분류·관련 지식·답변 초안·승인 필요 조치를 한 화면에서 확인합니다.") +
          '<div id="conv-banner"></div>' +
          '<div class="panel ops-panel" data-tour="workbench-conversation"><div class="panel-head"><h3>상담</h3><span><code>' + esc(c.conversation_id) + "</code></span></div>" +
            '<ul class="inq-list"><li class="inq-item"><div class="inq-q"><strong>Q.</strong> ' + esc(c.question) + '</div><div class="inq-a"><span class="inq-engine">' + esc(CATEGORY_KO[c.category] || c.category) + " · " + esc(c.autopilot_level) + '</span><p>' + esc(c.answer || "") + "</p>" + citationHtml(c.citations) + "</div></li></ul></div>" +
          '<div class="panel ops-panel" data-tour="workbench-classification"><div class="panel-head"><h3>자동 분류</h3><span>' + esc(cls.confidence || "-") + '</span></div><div class="kb-dash"><span>유형: ' + esc(CATEGORY_KO[cls.category] || cls.category) + '</span><span>우선순위: ' + esc(cls.priority) + '</span><span>필수 확인: ' + esc((cls.required_fields || []).join(", ") || "-") + "</span></div></div>" +
          '<div class="panel ops-panel" data-tour="workbench-actions"><div class="panel-head"><h3>추천 조치</h3><span>실행 아님</span></div><div class="kb-cards" style="padding:16px">' + actions + "</div></div>" +
          '<div class="panel ops-panel" data-tour="workbench-knowledge"><div class="panel-head"><h3>관련 지식</h3><span>통합 검색 결과</span></div><div class="kb-cards" style="padding:16px">' + (related || D4D.ui.emptyState("관련 지식 없음")) + "</div></div>" +
          '<div class="ops-form-foot" data-tour="workbench-resolve"><button class="primary" id="conv-resolve" type="button">상담 종료 · 지식DB 후보 등록</button><a class="button-like" href="#/helpdesk/inbox">대기열로</a></div>' +
          SAFETY_LINE +
        "</section>";
      var btn = mount.querySelector("#conv-resolve");
      mountTour("helpdesk-workbench", [
        { selector: '[data-tour="ops-head"]', title: "대응 워크벤치", body: "상담 하나를 처리하기 위한 답변, 분류, 추천 조치, 관련 지식을 한 화면에 모았습니다." },
        { selector: '[data-tour="workbench-conversation"]', title: "상담 답변", body: "질문과 답변 초안을 보고 근거 citation이 붙었는지 확인합니다." },
        { selector: '[data-tour="workbench-classification"]', title: "자동 분류", body: "문의 유형, 우선순위, 필수 확인 항목을 보고 담당자가 추가 확인할 내용을 정합니다." },
        { selector: '[data-tour="workbench-actions"]', title: "추천 조치", body: "표시되는 조치는 실행이 아니라 제안입니다. 승인 필요 여부와 executed=false를 확인합니다." },
        { selector: '[data-tour="workbench-resolve"]', title: "상담 종료", body: "처리 후 지식DB 후보로 등록해 다음 운영자가 같은 문의를 빠르게 처리하게 합니다." },
      ]);
      if (btn) {
        btn.addEventListener("click", function () {
          D4D.api.post("/api/helpdesk/conversations/" + id + "/resolve", {}).then(function (r) {
            var banner = mount.querySelector("#conv-banner");
            if (banner) banner.innerHTML = '<div class="ops-banner">상담 종료 · 지식 <code>' + esc(r.data.accumulated_knowledge_id) + "</code> 후보가 등록되었습니다.</div>";
          });
        });
      }
    }).catch(function () {
      mount.innerHTML = '<section class="ops-screen">' + headHtml("대응 워크벤치", "상담을 찾을 수 없습니다.") + D4D.ui.errorState("상담 로드 실패") + "</section>";
      mountTour("helpdesk-workbench-error", [
        { selector: '[data-tour="ops-head"]', title: "대응 워크벤치", body: "상담 상세를 불러오지 못했을 때는 대기열에서 상담 ID를 다시 선택합니다." },
      ]);
    });
  }

  function helpdeskIntegrationsScreen(mount) {
    mount.innerHTML =
      '<section class="ops-screen">' +
        headHtml("연동 상태", "채팅 인입, 계정 검증, 지식 검색, LLM endpoint 상태를 데모용으로 확인합니다.") +
        '<div class="kb-cards" data-tour="integration-cards">' +
          '<div class="kb-card"><div class="kb-card-top"><strong>ChatIngressPort</strong></div><p class="kb-summary">fixture/mock stream 사용</p></div>' +
          '<div class="kb-card"><div class="kb-card-top"><strong>UserDirectoryPort</strong></div><p class="kb-summary">synthetic 계정 검증 · raw 식별자 저장 없음</p></div>' +
          '<div class="kb-card"><div class="kb-card-top"><strong>Knowledge Search</strong></div><p class="kb-summary">/api/knowledge/search citation 기반</p></div>' +
          '<div class="kb-card"><div class="kb-card-top"><strong>LLM API</strong></div><p class="kb-summary">OpenAI-compatible /v1/chat/completions · 실패 시 rule fallback</p></div>' +
        "</div>" +
        SAFETY_LINE +
      "</section>";
    mountTour("helpdesk-integrations", [
      { selector: '[data-tour="ops-head"]', title: "연동 상태", body: "헬프데스크가 기대하는 외부 포트와 폴백 경로를 데모용으로 확인합니다." },
      { selector: '[data-tour="integration-cards"]', title: "연동 카드", body: "채팅 인입, 계정 검증, 지식 검색, LLM API가 어떤 mode로 동작하는지 확인합니다." },
    ]);
  }

  D4D.screens = D4D.screens || {};
  D4D.screens.dashboard = dashboardScreen;
  D4D.screens.dashboardEquipment = dashboardEquipmentScreen;
  D4D.screens.dashboardThreats = dashboardThreatsScreen;
  D4D.screens.dashboardSearch = dashboardSearchScreen;
  D4D.screens.opsIncidents = opsIncidentsScreen;
  D4D.screens.opsNotifications = opsNotificationsScreen;
  D4D.screens.opsIncidentDetail = opsIncidentDetailScreen;
  D4D.screens.helpdesk = helpdeskScreen;
  D4D.screens.helpdeskInbox = helpdeskInboxScreen;
  D4D.screens.helpdeskWorkbench = helpdeskWorkbenchScreen;
  D4D.screens.helpdeskIntegrations = helpdeskIntegrationsScreen;
  D4D.screens.knowledge = knowledgeScreen;
})(window.D4D);
