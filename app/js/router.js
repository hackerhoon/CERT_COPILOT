/**
 * Hash-based router. Works from file:// (double-click) and any static server.
 *
 * Routes:
 *   #/home                     훈련 홈           (01)
 *   #/scenarios                시나리오 선택      (02)
 *   #/briefing/:scenarioId     임무 브리핑        (03)
 *   #/mission/:sessionId       미션 데스크        (04/05) — A-03 placeholder
 *   #/aar/:sessionId           사후 강평          (06)   — A-05 placeholder
 *
 * Operations Mode (A-07 — 셸/골격, 데이터 화면은 A-08~A-11):
 *   #/dashboard                통합 대시보드
 *   #/dashboard/equipment      보안 장비 상태
 *   #/dashboard/threats        위협 동향
 *   #/dashboard/search         통합 검색
 *   #/ops/incidents            상위 조직/하급제대 전파/수신
 *   #/ops/incidents/:id        사건 상세
 *   #/ops/notifications        알림 피드
 *   #/helpdesk                 헬프데스크(문의/답변)
 *   #/helpdesk/inbox           인입 채팅
 *   #/helpdesk/conversations/:conversationId  대응 워크벤치
 *   #/helpdesk/integrations    연동 상태
 *   #/knowledge                지식DB
 *
 * Each route entry maps to a screen render function and the nav key to
 * highlight. The router owns the <main id="screen">, passes params + the
 * mount element to the screen, and screens navigate with D4D.router.go().
 */
window.D4D = window.D4D || {};
(function (D4D) {
  "use strict";

  var routes = [
    { pattern: /^\/home$/, screen: "home", nav: "home" },
    { pattern: /^\/scenarios$/, screen: "scenarios", nav: "scenarios" },
    { pattern: /^\/briefing\/([^/]+)$/, screen: "briefing", nav: "briefing", params: ["scenarioId"] },
    { pattern: /^\/mission\/([^/]+)$/, screen: "missionDesk", nav: "mission", params: ["sessionId"] },
    { pattern: /^\/aar\/([^/]+)$/, screen: "aar", nav: "aar", params: ["sessionId"] },
    { pattern: /^\/dashboard$/, screen: "dashboard", nav: "dashboard", mode: "ops" },
    { pattern: /^\/dashboard\/equipment$/, screen: "dashboardEquipment", nav: "dashboard-equipment", mode: "ops" },
    { pattern: /^\/dashboard\/threats$/, screen: "dashboardThreats", nav: "dashboard-threats", mode: "ops" },
    { pattern: /^\/dashboard\/search$/, screen: "dashboardSearch", nav: "dashboard-search", mode: "ops" },
    { pattern: /^\/ops\/incidents$/, screen: "opsIncidents", nav: "ops-incidents", mode: "ops" },
    { pattern: /^\/ops\/incidents\/([^/]+)$/, screen: "opsIncidentDetail", nav: "ops-incidents", params: ["incidentId"], mode: "ops" },
    { pattern: /^\/ops\/notifications$/, screen: "opsNotifications", nav: "ops-notifications", mode: "ops" },
    { pattern: /^\/helpdesk$/, screen: "helpdesk", nav: "helpdesk", mode: "helpdesk" },
    { pattern: /^\/helpdesk\/inbox$/, screen: "helpdeskInbox", nav: "helpdesk-inbox", mode: "helpdesk" },
    { pattern: /^\/helpdesk\/conversations\/([^/]+)$/, screen: "helpdeskWorkbench", nav: "helpdesk-inbox", params: ["conversationId"], mode: "helpdesk" },
    { pattern: /^\/helpdesk\/integrations$/, screen: "helpdeskIntegrations", nav: "helpdesk-integrations", mode: "helpdesk" },
    { pattern: /^\/knowledge$/, screen: "knowledge", nav: "knowledge", mode: "helpdesk" },
  ];

  function currentPath() {
    var h = window.location.hash || "";
    if (h.charAt(0) === "#") h = h.slice(1);
    return h || "/home";
  }

  function match(path) {
    for (var i = 0; i < routes.length; i++) {
      var r = routes[i];
      var m = path.match(r.pattern);
      if (m) {
        var params = {};
        (r.params || []).forEach(function (name, idx) {
          params[name] = decodeURIComponent(m[idx + 1]);
        });
        return { route: r, params: params };
      }
    }
    return null;
  }

  function render() {
    var path = currentPath();
    var hit = match(path);
    var mount = document.getElementById("screen");
    if (!mount) return;

    if (!hit) {
      D4D.router.go("/home");
      return;
    }

    // Tear down the previous screen (e.g. stop feed polling) before swapping.
    if (typeof D4D.router._cleanup === "function") {
      try { D4D.router._cleanup(); } catch (e) { /* ignore */ }
    }
    D4D.router._cleanup = null;
    if (D4D.tour) D4D.tour.hideLauncher();

    var screen = D4D.screens && D4D.screens[hit.route.screen];
    if (!screen) {
      mount.innerHTML = '<div class="empty">화면을 불러올 수 없습니다: ' + hit.route.screen + "</div>";
      return;
    }

    D4D.nav.setMode(hit.route.mode || "training");
    D4D.nav.setActive(hit.route.nav);
    mount.scrollTop = 0;
    screen(mount, hit.params);
  }

  D4D.router = {
    start: function () {
      window.addEventListener("hashchange", render);
      render();
    },
    go: function (path) {
      var target = "#" + path;
      if (window.location.hash === target) {
        render();
      } else {
        window.location.hash = target;
      }
    },
    // A screen can register a teardown fn; the router runs it on the next
    // navigation. Used by the mission desk to stop its feed poll timer.
    onLeave: function (fn) { this._cleanup = fn; },
    current: currentPath,
  };
})(window.D4D);
