/**
 * App bootstrap. Wires the top-bar clock, the mode badge, static nav links,
 * and starts the router. Runs after all modules are loaded (script order in
 * index.html).
 */
window.D4D = window.D4D || {};
(function (D4D) {
  "use strict";

  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function startClock() {
    var el = document.querySelector(".app-clock");
    if (!el) return;
    function tick() {
      var d = new Date();
      el.textContent = pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
    }
    tick();
    window.setInterval(tick, 1000);
  }

  function showModeBadge() {
    var badge = document.querySelector(".mode-badge");
    var note = document.querySelector("[data-api-status]");
    var isMock = D4D.api.isMock();

    if (badge) {
      badge.textContent = isMock ? "mock fixture" : "live FastAPI · 확인 중";
      badge.setAttribute("data-mock", isMock ? "true" : "false");
    }
    if (note) {
      note.textContent = isMock
        ? "브라우저 내 mock fixture 사용 · config.js에서 API_BASE 지정 시 실 API 연결"
        : "실제 FastAPI 연결 확인 중 · 데이터는 synthetic/masked fixture";
    }

    if (isMock) return;

    window
      .fetch(D4D.config.API_BASE + "/api/health")
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (env) {
        var data = (env && env.data) || {};
        var storage = data.storage_backend ? " · " + data.storage_backend : "";
        if (badge) badge.textContent = "live FastAPI" + storage;
        if (note) note.textContent = "실제 API 연결됨 · " + D4D.config.API_BASE + " · 데이터는 synthetic/masked fixture";
      })
      .catch(function () {
        if (badge) {
          badge.textContent = "API 연결 실패";
          badge.setAttribute("data-mock", "error");
        }
        if (note) note.textContent = "API_BASE는 설정됐지만 health check 실패 · 백엔드 8000번 포트 확인 필요";
      });
  }

  // 훈련/실제 상황 모드 탭 (A-07). 탭은 각 모드의 시작 라우트로 이동만 하고,
  // 활성 표시는 라우터가 라우트의 mode로 D4D.nav.setMode를 호출해 맞춘다.
  function wireModeTabs() {
    var tabs = document.querySelectorAll(".mode-tab[data-mode-tab]");
    Array.prototype.forEach.call(tabs, function (tab) {
      tab.addEventListener("click", function () {
        var mode = tab.getAttribute("data-mode-tab");
        if (mode === "ops") D4D.router.go("/dashboard");
        else if (mode === "helpdesk") D4D.router.go("/helpdesk/inbox");
        else D4D.router.go("/home");
      });
    });
  }

  function wireReset() {
    var btn = document.getElementById("btn-reset");
    if (!btn) return;
    btn.addEventListener("click", function () {
      D4D.store.reset();
      D4D.router.go("/home");
      // 이미 홈이면 go가 재렌더하지 않으므로 강제 새로고침
      if (D4D.router.current() === "/home") {
        var screen = D4D.screens.home;
        var mount = document.getElementById("screen");
        if (screen && mount) screen(mount, {});
      }
    });
  }

  function boot() {
    startClock();
    showModeBadge();
    wireModeTabs();
    wireReset();
    D4D.router.start();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})(window.D4D);
