/**
 * 03 임무 브리핑. GET /api/scenarios/{id}.
 * 임무 시작 -> POST /api/training/sessions -> #/mission/{session_id}.
 * Response contains no hidden ground truth (API_SPEC 5.3).
 */
window.D4D = window.D4D || {};
(function (D4D) {
  "use strict";
  var esc = D4D.ui.esc;

  function stepbar(current) {
    var steps = ["훈련 홈", "시나리오 선택", "임무 브리핑", "미션 데스크", "사후 강평"];
    return (
      '<div class="stepbar">' +
      steps.map(function (label, i) {
        var state = i + 1 < current ? "완료" : i + 1 === current ? "현재 단계" : "대기";
        var cur = i + 1 === current ? ' data-current="true"' : "";
        return '<div class="step"' + cur + "><b>" + (i + 1) + "</b><span>" + label + "<small>" + state + "</small></span></div>";
      }).join("") +
      "</div>"
    );
  }

  function render(mount, data) {
    var b = data.briefing;
    var metaBits = [];
    if (data.difficulty) metaBits.push(D4D.ui.difficultyLabel(data.difficulty));
    if (data.estimated_minutes != null) metaBits.push(esc(data.estimated_minutes) + "분");
    mount.innerHTML =
      stepbar(3) +
      '<div class="brief-head">' +
        "<h2>" + esc(data.title) + "</h2>" +
        (metaBits.length ? '<div class="brief-meta">' +
          metaBits.map(function (m) { return '<span class="pill">' + m + "</span>"; }).join("") +
          "</div>" : "") +
      "</div>" +
      '<div class="brief-layout">' +
        '<section class="brief-stack">' +
          '<div class="brief-card" data-tour="briefing-context"><strong>상황</strong><p>' + esc(b.situation) + "</p></div>" +
          '<div class="brief-card"><strong>역할</strong><p>' + esc(b.role) + "</p></div>" +
          '<div class="brief-card"><strong>목표</strong><p>' + esc(b.objective) + "</p></div>" +
          '<div class="brief-card"><strong>사용 가능 환경</strong><div class="env-grid">' +
            data.available_equipment.map(function (e) { return '<span class="pill">' + esc(e.label) + "</span>"; }).join("") +
          "</div></div>" +
          '<div class="brief-actions">' +
            '<button class="primary" id="btn-mission" data-tour="briefing-start">임무 시작</button>' +
            '<button class="secondary" id="btn-back">시나리오 다시 선택</button>' +
          "</div>" +
          '<div class="inline-note" id="start-note" hidden></div>' +
        "</section>" +
        '<aside class="panel" data-tour="briefing-rules">' +
          '<div class="panel-head"><h3>제한 사항</h3><span>안전 경계</span></div>' +
          '<div class="panel-pad"><ul class="checklist">' +
            b.constraints.map(function (c) { return "<li>" + esc(c) + "</li>"; }).join("") +
          "</ul></div>" +
          '<div class="panel-head"><h3>평가 기준</h3><span>rubric 요약</span></div>' +
          '<div class="panel-pad"><ul class="checklist">' +
            data.rubric_summary.map(function (r) { return "<li>" + esc(r) + "</li>"; }).join("") +
          "</ul></div>" +
        "</aside>" +
      "</div>";

    mount.querySelector("#btn-back").addEventListener("click", function () { D4D.router.go("/scenarios"); });

    var startBtn = mount.querySelector("#btn-mission");
    var note = mount.querySelector("#start-note");
    startBtn.addEventListener("click", function () {
      startBtn.disabled = true;
      startBtn.textContent = "세션 시작 중…";
      D4D.api.post("/api/training/sessions", {
        scenario_id: data.scenario_id,
        mode: D4D.config.DEFAULT_MODE,
        difficulty: data.difficulty || "intermediate",
        hint_policy: "on_request",
      }).then(
        function (res) {
          D4D.store.setSession(res.data);
          D4D.router.go("/mission/" + res.data.session_id);
        },
        function (e) {
          startBtn.disabled = false;
          startBtn.textContent = "임무 시작";
          note.hidden = false;
          note.className = "inline-note error";
          note.textContent = "세션을 시작하지 못했습니다: " + e.message;
        }
      );
    });
    if (D4D.tour) {
      D4D.tour.mount("training-briefing", [
        { selector: '[data-tour="briefing-context"]', title: "상황 먼저 확인", body: "훈련에서 공개되는 배경만 보고 시작합니다. 숨겨진 정답이나 ground truth는 이 화면에 나오지 않습니다." },
        { selector: '[data-tour="briefing-rules"]', title: "안전 경계와 평가 기준", body: "실제 조치는 실행하지 않고 승인 요청까지만 제안합니다. 사후 강평은 이 기준과 근거 ID를 함께 봅니다." },
        { selector: '[data-tour="briefing-start"]', title: "세션 시작", body: "임무 시작을 누르면 개인 훈련 세션이 만들어지고 미션 데스크로 이동합니다." },
      ]);
    }
  }

  D4D.screens = D4D.screens || {};
  D4D.screens.briefing = function (mount, params) {
    mount.innerHTML = D4D.ui.loading("임무 브리핑 불러오는 중…");
    D4D.api.get("/api/scenarios/" + encodeURIComponent(params.scenarioId)).then(
      function (res) { render(mount, res.data); },
      function (e) {
        if (e.code === "SCENARIO_NOT_FOUND") {
          mount.innerHTML = D4D.ui.errorState("시나리오를 찾을 수 없습니다. 시나리오 선택으로 돌아가십시오.");
        } else {
          mount.innerHTML = D4D.ui.errorState("브리핑을 불러오지 못했습니다: " + e.message);
        }
      }
    );
  };
})(window.D4D);
