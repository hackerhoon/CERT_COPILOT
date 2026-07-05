/**
 * Lightweight coach-mark tour for app screens.
 *
 * Screens register their own small step list after render. The first step
 * opens automatically; the fixed "가이드" button restarts the tour if needed.
 */
window.D4D = window.D4D || {};
(function (D4D) {
  "use strict";

  var current = { screenKey: null, steps: [], index: 0 };
  var launcher = null;
  var layer = null;
  var spotlight = null;
  var popover = null;
  var previousFocus = null;
  var repositionTimer = null;
  var autoStartTimer = null;

  function esc(s) {
    return D4D.ui && D4D.ui.esc ? D4D.ui.esc(s) : String(s || "");
  }

  function visibleTarget(selector) {
    var target = document.querySelector(selector);
    if (!target) return null;
    var rect = target.getBoundingClientRect();
    if (!rect.width || !rect.height) return null;
    return target;
  }

  function ensureLauncher() {
    if (launcher) return launcher;
    launcher = document.createElement("button");
    launcher.type = "button";
    launcher.className = "tour-launcher";
    launcher.setAttribute("aria-label", "현재 훈련 화면 가이드 보기");
    launcher.textContent = "가이드";
    launcher.addEventListener("click", function () { start(0); });
    document.body.appendChild(launcher);
    return launcher;
  }

  function ensureLayer() {
    if (layer) return;
    layer = document.createElement("div");
    layer.className = "tour-layer";
    layer.hidden = true;
    layer.innerHTML =
      '<div class="tour-spotlight" aria-hidden="true"></div>' +
      '<section class="tour-popover" role="dialog" aria-modal="true" aria-live="polite"></section>';
    document.body.appendChild(layer);
    spotlight = layer.querySelector(".tour-spotlight");
    popover = layer.querySelector(".tour-popover");
    layer.addEventListener("click", function (e) {
      if (e.target && e.target.getAttribute("data-tour-close") === "true") close();
      if (e.target && e.target.getAttribute("data-tour-next") === "true") next();
      if (e.target && e.target.getAttribute("data-tour-prev") === "true") prev();
    });
  }

  function bindGlobal() {
    window.addEventListener("resize", schedulePosition);
    window.addEventListener("scroll", schedulePosition, true);
    document.addEventListener("keydown", onKey);
  }

  function unbindGlobal() {
    window.removeEventListener("resize", schedulePosition);
    window.removeEventListener("scroll", schedulePosition, true);
    document.removeEventListener("keydown", onKey);
  }

  function onKey(e) {
    if (e.key === "Escape") close();
    if (e.key === "ArrowRight") next();
    if (e.key === "ArrowLeft") prev();
  }

  function schedulePosition() {
    if (layer && !layer.hidden) {
      window.clearTimeout(repositionTimer);
      repositionTimer = window.setTimeout(position, 40);
    }
  }

  function scheduleAutoStart() {
    window.clearTimeout(autoStartTimer);
    autoStartTimer = window.setTimeout(function () {
      if (!current.steps.length) return;
      start(0);
    }, 120);
  }

  function start(index) {
    if (!current.steps.length) return;
    window.clearTimeout(autoStartTimer);
    previousFocus = document.activeElement;
    ensureLayer();
    bindGlobal();
    layer.hidden = false;
    document.body.setAttribute("data-tour-active", "true");
    show(index || 0, 1);
  }

  function close() {
    window.clearTimeout(autoStartTimer);
    if (!layer) return;
    layer.hidden = true;
    document.body.removeAttribute("data-tour-active");
    unbindGlobal();
    if (previousFocus && typeof previousFocus.focus === "function") previousFocus.focus();
  }

  function next() { show(current.index + 1, 1); }
  function prev() { show(current.index - 1, -1); }

  function show(index, direction) {
    if (!current.steps.length) return close();
    if (index < 0) index = 0;
    if (index >= current.steps.length) return close();

    var step = current.steps[index];
    var target = visibleTarget(step.selector);
    if (!target) {
      var nextIndex = index + (direction < 0 ? -1 : 1);
      if (nextIndex < 0 || nextIndex >= current.steps.length) return close();
      return show(nextIndex, direction);
    }

    current.index = index;
    target.scrollIntoView({ block: "center", inline: "nearest", behavior: "smooth" });
    renderPopover(step, index);
    window.setTimeout(position, 180);
  }

  function renderPopover(step, index) {
    var isLast = index === current.steps.length - 1;
    popover.innerHTML =
      '<div class="tour-kicker">화면 가이드 · ' + (index + 1) + "/" + current.steps.length + "</div>" +
      "<h3>" + esc(step.title) + "</h3>" +
      "<p>" + esc(step.body) + "</p>" +
      '<div class="tour-actions">' +
        '<button class="secondary tiny" type="button" data-tour-close="true">닫기</button>' +
        '<span class="tour-spacer"></span>' +
        '<button class="secondary tiny" type="button" data-tour-prev="true"' + (index === 0 ? " disabled" : "") + ">이전</button>" +
        '<button class="primary tiny" type="button" data-tour-next="true">' + (isLast ? "완료" : "다음") + "</button>" +
      "</div>";
    var primary = popover.querySelector(".primary");
    if (primary) primary.focus();
  }

  function position() {
    var step = current.steps[current.index];
    var target = step && visibleTarget(step.selector);
    if (!target) return;

    var pad = step.pad == null ? 7 : Number(step.pad);
    var rect = target.getBoundingClientRect();
    var left = Math.max(10, rect.left - pad);
    var top = Math.max(10, rect.top - pad);
    var width = Math.min(window.innerWidth - left - 10, rect.width + pad * 2);
    var height = Math.min(window.innerHeight - top - 10, rect.height + pad * 2);
    spotlight.style.left = left + "px";
    spotlight.style.top = top + "px";
    spotlight.style.width = width + "px";
    spotlight.style.height = height + "px";

    var popRect = popover.getBoundingClientRect();
    var spaceBelow = window.innerHeight - (rect.bottom + pad);
    var popTop = spaceBelow > popRect.height + 18
      ? rect.bottom + pad + 12
      : rect.top - popRect.height - pad - 12;
    if (popTop < 12) popTop = 12;
    if (popTop + popRect.height > window.innerHeight - 12) {
      popTop = Math.max(12, window.innerHeight - popRect.height - 12);
    }

    var popLeft = rect.left;
    if (popLeft + popRect.width > window.innerWidth - 12) {
      popLeft = window.innerWidth - popRect.width - 12;
    }
    if (popLeft < 12) popLeft = 12;

    popover.style.left = popLeft + "px";
    popover.style.top = popTop + "px";
  }

  function mount(screenKey, steps) {
    current.screenKey = screenKey;
    current.steps = (steps || []).filter(function (step) { return step && step.selector; });
    current.index = 0;
    if (!current.steps.length) return hideLauncher();
    ensureLauncher().hidden = false;
    scheduleAutoStart();
  }

  function hideLauncher() {
    window.clearTimeout(autoStartTimer);
    if (launcher) launcher.hidden = true;
    close();
  }

  D4D.tour = { mount: mount, hideLauncher: hideLauncher, close: close };
})(window.D4D);
