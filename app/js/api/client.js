/**
 * API client adapter.
 *
 * Screens call D4D.api.get/post/put with a path and get back a Promise that
 * resolves to { data, warnings, meta } or rejects with an ApiError.
 *
 * The adapter picks its transport from D4D.config.API_BASE:
 *   - null           -> D4D.mock.resolve (fixtures)
 *   - a base URL      -> window.fetch against the real FastAPI server
 *
 * Screen code is identical in both cases. This is the "API base URL과 client
 * adapter 분리" requirement from ticket A-01.
 */
window.D4D = window.D4D || {};
(function (D4D) {
  "use strict";

  function ApiError(code, message, details) {
    this.name = "ApiError";
    this.code = code;
    this.message = message || code;
    this.details = details || {};
  }
  ApiError.prototype = Object.create(Error.prototype);

  function buildQuery(params) {
    if (!params) return "";
    var parts = [];
    Object.keys(params).forEach(function (k) {
      if (params[k] === undefined || params[k] === null || params[k] === "") return;
      parts.push(encodeURIComponent(k) + "=" + encodeURIComponent(params[k]));
    });
    return parts.length ? "?" + parts.join("&") : "";
  }

  function unwrap(env) {
    if (env && env.error) {
      throw new ApiError(env.error.code, env.error.message, env.error.details);
    }
    return { data: env.data, warnings: env.warnings || [], meta: env.meta || {} };
  }

  function viaMock(method, path, params, body) {
    return new Promise(function (resolve) {
      var latency = D4D.config.MOCK_LATENCY_MS || 0;
      setTimeout(function () {
        resolve(unwrap(D4D.mock.resolve(method, path, params, body)));
      }, latency);
    });
  }

  function viaHttp(method, path, params, body) {
    var url = D4D.config.API_BASE + path + buildQuery(params);
    var init = { method: method, headers: { "Content-Type": "application/json" } };
    if (body) init.body = JSON.stringify(body);
    return window
      .fetch(url, init)
      .then(function (res) { return res.json(); })
      .then(unwrap);
  }

  function request(method, path, params, body) {
    if (D4D.config.API_BASE) return viaHttp(method, path, params, body);
    return viaMock(method, path, params, body);
  }

  D4D.api = {
    ApiError: ApiError,
    get: function (path, params) { return request("GET", path, params, null); },
    post: function (path, body) { return request("POST", path, null, body); },
    put: function (path, body) { return request("PUT", path, null, body); },
    isMock: function () { return !D4D.config.API_BASE; },
  };
})(window.D4D);
