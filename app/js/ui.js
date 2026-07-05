/**
 * Shared UI helpers: HTML escaping, small formatters, loading/empty/error
 * blocks, and the left-nav controller. Kept framework-free.
 */
window.D4D = window.D4D || {};
(function (D4D) {
  "use strict";

  function esc(s) {
    return String(s === undefined || s === null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  var DIFFICULTY_KO = { basic: "초급", intermediate: "중급", advanced: "숙련" };
  function difficultyLabel(d) { return DIFFICULTY_KO[d] || d; }

  function loading(text) {
    return '<div class="state loading"><span class="spinner"></span>' + esc(text || "불러오는 중…") + "</div>";
  }
  function emptyState(text) {
    return '<div class="state empty">' + esc(text || "표시할 내용이 없습니다.") + "</div>";
  }
  function errorState(text) {
    return '<div class="state error">' + esc(text || "오류가 발생했습니다.") + "</div>";
  }

  // Left-nav controller. The nav markup lives in index.html; we just toggle
  // the active item by its data-nav key.
  var nav = {
    setActive: function (key) {
      var items = document.querySelectorAll(".side-nav a[data-nav]");
      Array.prototype.forEach.call(items, function (a) {
        if (a.getAttribute("data-nav") === key) a.setAttribute("data-active", "true");
        else a.removeAttribute("data-active");
      });
    },
    // 훈련/사이버 방호/헬프데스크 모드 표시 상태. 라우터가 라우트의 mode로 호출한다.
    // body[data-app-mode]가 nav 그룹 표시와 헤더 탭 활성 상태를 함께 결정한다.
    setMode: function (mode) {
      mode = mode === "ops" || mode === "helpdesk" ? mode : "training";
      document.body.setAttribute("data-app-mode", mode);
      var tabs = document.querySelectorAll(".mode-tab[data-mode-tab]");
      Array.prototype.forEach.call(tabs, function (t) {
        if (t.getAttribute("data-mode-tab") === mode) t.setAttribute("data-active", "true");
        else t.removeAttribute("data-active");
      });
    },
  };

  D4D.ui = { esc: esc, difficultyLabel: difficultyLabel, loading: loading, emptyState: emptyState, errorState: errorState };
  D4D.nav = nav;
})(window.D4D);
