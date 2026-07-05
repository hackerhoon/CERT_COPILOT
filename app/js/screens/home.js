/**
 * 01 훈련 홈. GET /api/training/home.
 * First screen on load. 훈련 시작 -> #/scenarios.
 */
window.D4D = window.D4D || {};
(function (D4D) {
  "use strict";
  var esc = D4D.ui.esc;

  function scoreCard(s) {
    return (
      '<div class="summary-card"><strong>' + esc(s.name) + "</strong>" +
      '<span>' + esc(s.score) + " / 100</span>" +
      '<div class="scorebar"><i style="width:' + Number(s.score) + '%"></i></div></div>'
    );
  }

  function aarRow(a) {
    return (
      "<tr><td>" + esc(a.scenario_title) + "</td>" +
      '<td><span class="pill grade-' + esc(a.grade) + '">' + esc(a.grade) + "</span></td>" +
      "<td>" + esc(a.key_feedback) + "</td></tr>"
    );
  }

  function render(mount, data) {
    var rec = data.recommended_scenario;
    var progress = data.weekly_progress || {};
    var progressPct = progress.percent == null ? 0 : Number(progress.percent);
    var weaknesses = data.common_weaknesses || [];
    var recReason = rec.reason || rec.training_goals.join(", ");
    mount.innerHTML =
      '<div class="home-grid" data-tour="home-overview">' +
        '<section class="home-main">' +
          '<div class="welcome">' +
            "<h2>" + esc(data.headline || "훈련을 통해 사이버방호 임무 역량을 강화하십시오.") + "</h2>" +
            '<div class="welcome-actions">' +
              '<button class="primary" id="btn-start" data-tour="home-start">훈련 시작</button>' +
            "</div>" +
          "</div>" +
          '<div class="panel" data-tour="home-recommended">' +
            '<div class="panel-head"><h3>추천 훈련</h3><span>' + esc(recReason) + "</span></div>" +
            '<div class="training-card">' +
              '<div class="mock-thumb">△</div>' +
              "<div><strong>" + esc(rec.title) + "</strong><span>" +
                D4D.ui.difficultyLabel(rec.difficulty) + " · " + esc(rec.estimated_minutes) + "분 · " +
                esc(rec.training_goals.join(", ")) + "</span></div>" +
              '<button class="secondary" id="btn-rec" data-tour="home-rec-start">바로 시작</button>' +
            "</div>" +
          "</div>" +
          '<div class="summary-grid" data-tour="home-progress">' + data.skill_summary.map(scoreCard).join("") + "</div>" +
          '<div class="panel">' +
            '<div class="panel-head"><h3>최근 사후 강평</h3><span>지난 훈련</span></div>' +
            '<div class="panel-pad"><table class="compact-table">' +
              "<thead><tr><th>시나리오</th><th>등급</th><th>핵심 피드백</th></tr></thead>" +
              "<tbody>" + data.recent_aars.map(aarRow).join("") + "</tbody>" +
            "</table></div>" +
          "</div>" +
        "</section>" +
        '<aside class="home-side">' +
          '<div class="panel"><div class="panel-head"><h3>역할</h3></div>' +
            '<div class="panel-pad"><p class="role-line">' + esc(data.role_label) + "</p></div></div>" +
          '<div class="panel"><div class="panel-head"><h3>' + esc(progress.label || "이번 주 진행") +
            "</h3><span>" + esc(progress.caption || "훈련") + "</span></div>" +
            '<div class="ring">' + progressPct + "%</div></div>" +
          '<div class="panel"><div class="panel-head"><h3>공통 약점</h3></div>' +
            '<div class="panel-pad"><ul class="note-list">' +
              (weaknesses.length
                ? weaknesses.map(function (w) { return "<li>" + esc(w) + "</li>"; }).join("")
                : "<li>기록된 공통 약점이 없습니다.</li>") +
            "</ul></div></div>" +
        "</aside>" +
      "</div>";

    function start() { D4D.router.go("/scenarios"); }
    function startRec() {
      D4D.store.rememberScenario(rec.scenario_id, rec.title);
      D4D.router.go("/briefing/" + rec.scenario_id);
    }
    mount.querySelector("#btn-start").addEventListener("click", start);
    mount.querySelector("#btn-rec").addEventListener("click", startRec);
    if (D4D.tour) {
      D4D.tour.mount("training-home", [
        { selector: '[data-tour="home-start"]', title: "정석 흐름 시작", body: "처음이면 여기서 시나리오 선택 화면으로 들어가 전체 훈련 흐름을 따라갑니다." },
        { selector: '[data-tour="home-recommended"]', title: "추천 훈련", body: "현재 숙련도와 약점 기준으로 가장 보여 주기 좋은 훈련이 잡혀 있습니다. 시간이 없을 때는 바로 시작으로 브리핑에 들어갑니다." },
        { selector: '[data-tour="home-progress"]', title: "숙련도 요약", body: "사후 강평 결과가 쌓이면 영역별 점수와 약점이 바뀝니다. 지금은 데모용 synthetic 진행 상태입니다." },
      ]);
    }
  }

  D4D.screens = D4D.screens || {};
  D4D.screens.home = function (mount) {
    mount.innerHTML = D4D.ui.loading("훈련 홈 불러오는 중…");
    D4D.api.get("/api/training/home").then(
      function (res) { render(mount, res.data); },
      function (e) { mount.innerHTML = D4D.ui.errorState("훈련 홈을 불러오지 못했습니다: " + e.message); }
    );
  };
})(window.D4D);
