/**
 * App configuration.
 *
 * API_BASE controls where the client sends requests.
 *   - null  -> use the in-browser mock client (fixtures matching architecture/API_SPEC.md)
 *   - "http://127.0.0.1:8000" -> call the real FastAPI server (이성진 B-track)
 *
 * When the FastAPI server is ready, set API_BASE to its origin and the same
 * screens keep working against real endpoints. No screen code knows the URL.
 */
window.D4D = window.D4D || {};
window.D4D.config = {
  // 백엔드(이성진 B-track) 통합 연결. standalone(정적 파일)으로 mock만 쓰려면
  // 이 값을 null로 되돌린다.
  API_BASE: null,
  DEFAULT_MODE: "fixture",
  // simulated latency for the mock client so loading states are visible
  MOCK_LATENCY_MS: 220,
};
