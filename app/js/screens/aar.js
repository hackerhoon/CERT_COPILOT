/**
 * 06 사후 강평 (A-05).
 *
 * 훈련의 보상 화면. 점수/등급이 아니라 "무엇을 어떤 순서로 조사했고 무엇을
 * 놓쳤는가"를 보여 준다.
 *   - 진입 시 POST /aar 로 생성 요청 후 GET /aar 로 리플레이 데이터 로드.
 *   - 점수/등급, 조사 타임라인(late 강조), 확인/누락 근거, 동적 평가
 *     (우선순위·심각도·대응 노력 피드백), 다음 훈련 추천.
 *   - "운영 보조 케이스로 재사용" → POST /api/ops/cases/from-training-session.
 *     Training evidence가 Operations Mode에서 재사용됨을 보여 준다(shared core).
 */
window.D4D = window.D4D || {};
(function (D4D) {
  "use strict";
  var esc = D4D.ui.esc;

  function stepbar() {
    var steps = ["훈련 홈", "시나리오 선택", "임무 브리핑", "미션 데스크", "사후 강평"];
    return (
      '<div class="stepbar">' +
      steps.map(function (label, i) {
        var st = i < 4 ? "완료" : "현재 단계";
        var cur = i === 4 ? ' data-current="true"' : "";
        return '<div class="step"' + cur + "><b>" + (i + 1) + "</b><span>" + label + "<small>" + st + "</small></span></div>";
      }).join("") +
      "</div>"
    );
  }

  function timelineRow(t) {
    var mm = Math.floor((t.at_seconds || 0) / 60);
    var ss = ("0" + ((t.at_seconds || 0) % 60)).slice(-2);
    return (
      '<li class="tl-item" data-status="' + esc(t.status) + '">' +
        '<span class="tl-time">' + mm + ":" + ss + "</span>" +
        '<span class="tl-label">' + esc(t.label) + "</span>" +
        '<span class="pill tiny ' + (t.status === "late" ? "warn" : "") + '">' + (t.status === "late" ? "지연" : "적시") + "</span>" +
      "</li>"
    );
  }

  function evidenceChips(ids, cls) {
    if (!ids || !ids.length) return '<span class="muted-note">없음</span>';
    return ids.map(function (id) { return '<span class="chip ' + (cls || "") + '">' + esc(id) + "</span>"; }).join(" ");
  }

  function feedbackBlock(ev) {
    if (!ev) return "";
    var rows = [
      ["우선순위", ev.priority_feedback],
      ["심각도", ev.severity_feedback],
      ["대응 노력", ev.effort_feedback],
    ].filter(function (r) { return r[1]; });
    var hits = (ev.rubric_hits || []).map(function (h) { return "<li>" + esc(h) + "</li>"; }).join("");
    var misses = (ev.rubric_misses || []).map(function (m) { return "<li>" + esc(m) + "</li>"; }).join("");
    return (
      '<div class="eval-feedback">' +
        rows.map(function (r) {
          return '<div class="fb-row"><span>' + esc(r[0]) + "</span><p>" + esc(r[1]) + "</p></div>";
        }).join("") +
        (ev.overall_note ? '<p class="fb-overall">' + esc(ev.overall_note) + "</p>" : "") +
        '<div class="rubric-grid">' +
          '<div><h4>잘한 점</h4><ul class="checklist good">' + (hits || "<li>—</li>") + "</ul></div>" +
          '<div><h4>보강할 점</h4><ul class="checklist bad">' + (misses || "<li>—</li>") + "</ul></div>" +
        "</div>" +
      "</div>"
    );
  }

  function render(mount, data) {
    var ev = data.dynamic_evaluation || {};
    mount.innerHTML =
      stepbar() +
      '<div class="aar-head" data-tour="aar-score">' +
        '<div class="grade-badge grade-' + esc(data.grade) + '"><b>' + esc(data.grade) + "</b><span>등급</span></div>" +
        '<div class="score-block"><div class="score-num">' + esc(data.score) + '<small>/100</small></div>' +
          '<div class="scorebar"><i style="width:' + Number(data.score) + '%"></i></div>' +
          "<p>" + esc(data.summary || "") + "</p></div>" +
      "</div>" +
      '<div class="aar-layout">' +
        '<section class="brief-stack">' +
          '<div class="panel" data-tour="aar-timeline"><div class="panel-head"><h3>조사 타임라인</h3><span>리플레이</span></div>' +
            '<div class="panel-pad"><ul class="timeline">' + (data.timeline || []).map(timelineRow).join("") + "</ul></div></div>" +
          '<div class="panel"><div class="panel-head"><h3>동적 평가</h3><span>rubric 기반</span></div>' +
            '<div class="panel-pad">' + feedbackBlock(ev) + "</div></div>" +
        "</section>" +
        '<aside class="brief-stack">' +
          '<div class="panel" data-tour="aar-evidence"><div class="panel-head"><h3>근거 점검</h3></div>' +
            '<div class="panel-pad">' +
              '<div class="ev-line"><span>확인한 근거</span><div>' + evidenceChips(data.checked_evidence) + "</div></div>" +
              '<div class="ev-line"><span>놓치거나 늦은 근거</span><div>' + evidenceChips(data.missed_or_late_evidence, "warn") + "</div></div>" +
            "</div></div>" +
          '<div class="panel" data-tour="aar-next"><div class="panel-head"><h3>다음 훈련</h3></div>' +
            '<div class="panel-pad">' + (data.next_drills || []).map(function (d) {
              return '<button class="drill-card" data-scenario="' + esc(d.scenario_id) + '"><strong>' + esc(d.title) +
                "</strong><span>" + esc(d.reason) + "</span></button>";
            }).join("") + "</div></div>" +
          '<div class="panel" data-tour="aar-reuse"><div class="panel-head"><h3>운영 재사용</h3><span>shared core</span></div>' +
            '<div class="panel-pad">' +
              "<p class=\"muted-note\">이 훈련 근거를 그대로 Operations Mode 사건으로 넘겨 운영 보조를 시연합니다.</p>" +
              '<button class="primary full"' + (data.operations_reuse_available ? "" : " disabled") + ' id="btn-reuse">운영 보조 케이스로 재사용</button>' +
              '<div id="reuse-out"></div>' +
            "</div></div>" +
          '<div class="panel-pad"><button class="secondary full" id="btn-home">훈련 홈으로</button></div>' +
        "</aside>" +
      "</div>";

    Array.prototype.forEach.call(mount.querySelectorAll(".drill-card"), function (b) {
      b.addEventListener("click", function () {
        D4D.router.go("/briefing/" + b.getAttribute("data-scenario"));
      });
    });
    mount.querySelector("#btn-home").addEventListener("click", function () { D4D.router.go("/home"); });

    var reuseBtn = mount.querySelector("#btn-reuse");
    if (reuseBtn && data.operations_reuse_available) {
      reuseBtn.addEventListener("click", function () {
        reuseBtn.disabled = true;
        reuseBtn.textContent = "케이스 생성 중…";
        D4D.api.post("/api/ops/cases/from-training-session", {
          session_id: data.session_id,
          reuse_evidence_ids: (data.checked_evidence || []).concat(data.missed_or_late_evidence || []),
        }).then(
          function (res) { renderReuse(mount, res.data); },
          function (e) {
            reuseBtn.disabled = false;
            reuseBtn.textContent = "운영 보조 케이스로 재사용";
            mount.querySelector("#reuse-out").innerHTML = D4D.ui.errorState("케이스 생성 실패: " + e.message);
          }
        );
      });
    }
    if (D4D.tour) {
      D4D.tour.mount("training-aar", [
        { selector: '[data-tour="aar-score"]', title: "결과 요약", body: "점수보다 중요한 것은 어떤 근거와 판단 흐름이 점수에 반영됐는지입니다." },
        { selector: '[data-tour="aar-timeline"]', title: "조사 순서", body: "훈련 중 어떤 조사를 제때 했고 어떤 단서가 늦었는지 리플레이합니다." },
        { selector: '[data-tour="aar-evidence"]', title: "근거 점검", body: "확인한 evidence와 놓쳤거나 늦은 evidence가 분리됩니다. 다음 훈련의 보강 지점입니다." },
        { selector: '[data-tour="aar-next"]', title: "다음 훈련", body: "현재 결과를 기준으로 이어서 할 drill을 추천합니다." },
        { selector: '[data-tour="aar-reuse"]', title: "운영 재사용", body: "같은 evidence model을 Operations Mode 사건으로 넘겨 훈련과 실제 업무가 같은 코어를 쓴다는 점을 보여 줍니다." },
      ]);
    }
  }

  function renderReuse(mount, c) {
    var out = mount.querySelector("#reuse-out");
    var btn = mount.querySelector("#btn-reuse");
    if (btn) { btn.textContent = "재사용 완료 · " + esc(c.case_id); }
    out.innerHTML =
      '<div class="ops-case">' +
        '<div class="ops-case-head"><span class="pill tiny">' + esc(c.status) + "</span><code>" + esc(c.case_id) + "</code></div>" +
        '<div class="field-box"><strong>운영자 노트 초안</strong><p>' + esc(c.operator_note) + "</p></div>" +
        '<div class="ops-outputs"><span>추천 산출물</span><ul class="checklist">' +
          (c.recommended_outputs || []).map(function (o) { return "<li>" + esc(o) + "</li>"; }).join("") +
        "</ul></div>" +
        '<small class="muted-note">동일 evidence model을 Operations Mode가 그대로 재사용합니다. 실제 조치는 실행되지 않습니다.</small>' +
      "</div>";
  }

  D4D.screens = D4D.screens || {};
  D4D.screens.aar = function (mount, params) {
    mount.innerHTML = D4D.ui.loading("사후 강평 생성 중…");
    var sid = params.sessionId;
    // 먼저 생성 요청, 이어서 리플레이 데이터 로드.
    D4D.api.post("/api/training/sessions/" + encodeURIComponent(sid) + "/aar", {
      include_dynamic_evaluation: true,
      include_operations_reuse_hint: true,
    }).then(
      function () {
        return D4D.api.get("/api/training/sessions/" + encodeURIComponent(sid) + "/aar");
      }
    ).then(
      function (res) { render(mount, res.data); },
      function (e) { mount.innerHTML = D4D.ui.errorState("사후 강평을 불러오지 못했습니다: " + e.message); }
    );
  };
})(window.D4D);
