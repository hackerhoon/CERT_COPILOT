/**
 * 02 시나리오 선택. GET /api/scenarios (+ difficulty filter).
 * Select a card -> navigate to #/briefing/{id}.
 *
 * The shell (stepbar + filter panel + list container + detail container) is
 * rendered once and stays put. Only the list and detail regions are swapped
 * when the filter changes, so the filter control and the applied value remain
 * visible — including when a filter matches zero scenarios.
 */
window.D4D = window.D4D || {};
(function (D4D) {
  "use strict";
  var esc = D4D.ui.esc;

  // Persists the applied filter across list reloads within this screen.
  var state = { difficulty: "" };

  function stepbar(current) {
    var steps = ["훈련 홈", "시나리오 선택", "임무 브리핑", "미션 데스크", "사후 강평"];
    return (
      '<div class="stepbar">' +
      steps.map(function (label, i) {
        var st = i + 1 < current ? "완료" : i + 1 === current ? "현재 단계" : "대기";
        var cur = i + 1 === current ? ' data-current="true"' : "";
        return '<div class="step"' + cur + "><b>" + (i + 1) + "</b><span>" + label + "<small>" + st + "</small></span></div>";
      }).join("") +
      "</div>"
    );
  }

  function card(s, active) {
    return (
      '<article class="scenario-card" data-id="' + esc(s.scenario_id) + '"' + (active ? ' data-active="true"' : "") + ">" +
        '<div class="scenario-card-inner">' +
          '<div class="scenario-thumb">' + esc(s.title.charAt(0)) + "</div>" +
          '<div class="scenario-card-body">' +
            "<header><strong>" + esc(s.title) + '</strong><span class="pill ' +
              (s.difficulty === "intermediate" ? "warn" : "") + '">' + D4D.ui.difficultyLabel(s.difficulty) + "</span></header>" +
            "<p>" + esc(s.summary || "") + "</p>" +
            '<div class="tag-row"><span class="pill">' + esc(s.estimated_minutes) + "분</span>" +
              s.available_equipment.map(function (p) {
                return '<span class="pill">' + esc(D4D.mock.EQUIPMENT_LABELS[p] || p) + "</span>";
              }).join("") + "</div>" +
          "</div>" +
          '<div class="radio-mark" aria-hidden="true"></div>' +
        "</div>" +
      "</article>"
    );
  }

  function detailPanel(s) {
    if (!s) {
      return (
        '<div class="panel-head"><h3>훈련 목표</h3></div>' +
        '<div class="panel-pad">' + D4D.ui.emptyState("표시할 시나리오가 없습니다.") + "</div>"
      );
    }
    return (
      '<div class="panel-head"><h3>훈련 목표</h3><span>선택 시나리오</span></div>' +
      '<div class="panel-pad">' +
        '<ul class="checklist">' + s.training_goals.map(function (g) { return "<li>" + esc(g) + "</li>"; }).join("") + "</ul>" +
        '<div class="field-box">사용 장비: ' + s.available_equipment.map(function (p) { return esc(D4D.mock.EQUIPMENT_LABELS[p] || p); }).join(", ") + "</div>" +
        '<div class="field-box">세션 설정: 힌트 기본 · 제한 ' + esc(s.estimated_minutes) + "분 · 개인 훈련</div>" +
        '<button class="primary full" id="btn-select">이 시나리오로 브리핑</button>' +
      "</div>"
    );
  }

  function statusText(count) {
    var label = state.difficulty ? "난이도: " + D4D.ui.difficultyLabel(state.difficulty) : "필터: 전체";
    return label + " · " + count + "건";
  }

  // Update only the list + detail regions; the shell/filter stay in place.
  function fillList(mount, items) {
    var listEl = mount.querySelector("#scenario-list");
    var detailEl = mount.querySelector("#scenario-detail");
    var statusEl = mount.querySelector("#filter-status");

    statusEl.textContent = statusText(items.length);
    statusEl.setAttribute("data-filtered", state.difficulty ? "true" : "false");

    if (!items.length) {
      listEl.innerHTML = D4D.ui.emptyState("조건에 맞는 시나리오가 없습니다. 난이도 필터를 바꾸거나 전체로 두십시오.");
      detailEl.innerHTML = detailPanel(null);
      mountTour(mount);
      return;
    }

    var selected = items.filter(function (s) { return s.scenario_id === D4D.store.selectedScenarioId; })[0] || items[0];
    listEl.innerHTML = items.map(function (s) { return card(s, s.scenario_id === selected.scenario_id); }).join("");
    detailEl.innerHTML = detailPanel(selected);
    D4D.store.rememberScenario(selected.scenario_id, selected.title);
    bindDetail(mount, selected);

    Array.prototype.forEach.call(listEl.querySelectorAll(".scenario-card"), function (el) {
      el.addEventListener("click", function () {
        var s = items.filter(function (x) { return x.scenario_id === el.getAttribute("data-id"); })[0];
        if (!s) return;
        D4D.store.rememberScenario(s.scenario_id, s.title);
        Array.prototype.forEach.call(listEl.querySelectorAll(".scenario-card"), function (c) {
          if (c === el) c.setAttribute("data-active", "true");
          else c.removeAttribute("data-active");
        });
        detailEl.innerHTML = detailPanel(s);
        bindDetail(mount, s);
      });
    });
    mountTour(mount);
  }

  function mountTour(mount) {
    if (!D4D.tour) return;
    D4D.tour.mount("training-scenarios", [
      { selector: '[data-tour="scenario-filter"]', title: "난이도 필터", body: "초급, 중급, 숙련 시나리오를 빠르게 좁힙니다. 필터를 바꿔도 현재 적용 상태와 건수가 계속 보입니다." },
      { selector: '[data-tour="scenario-list"]', title: "시나리오 카드", body: "카드를 누르면 오른쪽 훈련 목표가 바뀝니다. 데모에서는 중급 시나리오가 가장 전체 흐름을 잘 보여 줍니다." },
      { selector: '#btn-select', title: "브리핑으로 이동", body: "선택한 시나리오의 역할, 제한 사항, 평가 기준을 확인하는 단계로 넘어갑니다." },
    ]);
  }

  function bindDetail(mount, s) {
    var btn = mount.querySelector("#btn-select");
    if (btn && s) {
      btn.addEventListener("click", function () {
        D4D.store.rememberScenario(s.scenario_id, s.title);
        D4D.router.go("/briefing/" + s.scenario_id);
      });
    }
  }

  function loadList(mount) {
    var listEl = mount.querySelector("#scenario-list");
    listEl.innerHTML = D4D.ui.loading("시나리오 불러오는 중…");
    D4D.api.get("/api/scenarios", state.difficulty ? { difficulty: state.difficulty } : {}).then(
      function (res) { fillList(mount, res.data.items || []); },
      function (e) { listEl.innerHTML = D4D.ui.errorState("시나리오를 불러오지 못했습니다: " + e.message); }
    );
  }

  D4D.screens = D4D.screens || {};
  D4D.screens.scenarios = function (mount) {
    mount.innerHTML =
      stepbar(2) +
      '<div class="scenario-layout">' +
        '<aside class="panel" data-tour="scenario-filter">' +
          '<div class="panel-head"><h3>필터</h3><span id="filter-status" data-filtered="false"></span></div>' +
          '<div class="panel-pad filters">' +
            '<label class="field"><span>난이도</span>' +
              '<select id="f-difficulty">' +
                '<option value="">전체</option>' +
                '<option value="basic">초급</option>' +
                '<option value="intermediate">중급</option>' +
                '<option value="advanced">숙련</option>' +
              "</select></label>" +
            '<button class="secondary full" id="f-reset">필터 초기화</button>' +
          "</div>" +
        "</aside>" +
        '<section class="scenario-list" id="scenario-list" data-tour="scenario-list"></section>' +
        '<aside class="panel" id="scenario-detail"></aside>' +
      "</div>";

    var select = mount.querySelector("#f-difficulty");
    select.value = state.difficulty; // reflect the applied filter
    select.addEventListener("change", function (e) {
      state.difficulty = e.target.value;
      loadList(mount);
    });
    mount.querySelector("#f-reset").addEventListener("click", function () {
      state.difficulty = "";
      select.value = "";
      loadList(mount);
    });

    loadList(mount);
  };
})(window.D4D);
