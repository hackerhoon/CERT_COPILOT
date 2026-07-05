/**
 * Tiny in-memory session store. Holds the selected scenario and active
 * training session so screens can share context across routes without a
 * global framework. Not persisted — a page reload restarts the flow at 홈.
 */
window.D4D = window.D4D || {};
(function (D4D) {
  "use strict";
  D4D.store = {
    selectedScenarioId: null,
    scenarioTitleById: {},
    session: null,
    // Operations Mode 조직 컨텍스트 (A-07). units는 /api/ops/units 응답,
    // opsUnitId는 현재 관점 조직. role이 higher면 상위 조직(읽기) 관점이다.
    opsUnits: [],
    opsUnitId: null,
    setOpsUnits: function (units, defaultUnitId) {
      this.opsUnits = units || [];
      if (!this.opsUnitId || !this.opsUnit()) {
        this.opsUnitId = defaultUnitId || (this.opsUnits[0] && this.opsUnits[0].unit_id) || null;
      }
    },
    setOpsUnit: function (unitId) {
      this.opsUnitId = unitId;
    },
    opsUnit: function () {
      var id = this.opsUnitId;
      for (var i = 0; i < this.opsUnits.length; i++) {
        if (this.opsUnits[i].unit_id === id) return this.opsUnits[i];
      }
      return null;
    },
    rememberScenario: function (id, title) {
      this.selectedScenarioId = id;
      if (title) this.scenarioTitleById[id] = title;
    },
    setSession: function (session) {
      this.session = session;
    },
    reset: function () {
      this.selectedScenarioId = null;
      this.scenarioTitleById = {};
      this.session = null;
      this.opsUnits = [];
      this.opsUnitId = null;
    },
  };
})(window.D4D);
