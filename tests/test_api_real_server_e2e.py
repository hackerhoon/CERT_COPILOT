"""Real-server E2E tests for the D4D readiness API.

These tests intentionally start uvicorn in a subprocess and call HTTP endpoints
through urllib. They catch integration mistakes that FastAPI TestClient can
hide, such as missing router registration, bad JSON serialization, and server
startup failures.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{2}-\d{8}\b"),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"secret[_ -]?key", re.IGNORECASE),
    re.compile(r"access[_ -]?key", re.IGNORECASE),
    re.compile(r"bearer\s+[a-z0-9._-]+", re.IGNORECASE),
]


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ApiResponseError(AssertionError):
    pass


class RealServerE2ETest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.sqlite_path = str(Path(cls.tmpdir.name) / "readiness-e2e.sqlite3")
        cls._start_server()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._stop_server()
        cls.tmpdir.cleanup()

    @classmethod
    def _start_server(cls) -> None:
        cls.port = free_port()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC)
        env["D4D_STORAGE_BACKEND"] = "sqlite"
        env["D4D_SQLITE_PATH"] = cls.sqlite_path
        cls.server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "d4d.api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(cls.port),
                "--log-level",
                "warning",
            ],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls._wait_for_server()

    @classmethod
    def _stop_server(cls) -> None:
        cls.server.terminate()
        try:
            cls.server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.server.kill()
            cls.server.wait(timeout=5)

    @classmethod
    def restart_server(cls) -> None:
        cls._stop_server()
        cls._start_server()

    @classmethod
    def _wait_for_server(cls) -> None:
        deadline = time.time() + 12
        last_error: Exception | None = None
        while time.time() < deadline:
            if cls.server.poll() is not None:
                raise RuntimeError("uvicorn exited early")
            try:
                payload = cls.get_json("/api/health")
                if payload["data"]["status"] == "ok":
                    return
            except Exception as exc:  # noqa: BLE001 - startup retry loop
                last_error = exc
                time.sleep(0.2)
        raise RuntimeError(f"server did not become ready: {last_error}")

    @classmethod
    def request_json(
        cls,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        expected_status: int = 200,
    ) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = Request(
            cls.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=4) as resp:
                raw = resp.read().decode("utf-8")
                status = resp.status
        except HTTPError as exc:
            raw = exc.read().decode("utf-8")
            status = exc.code
            exc.close()
        except URLError as exc:
            raise ApiResponseError(f"request failed: {method} {path}: {exc}") from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ApiResponseError(f"non-JSON response: {method} {path}: {raw}") from exc
        if status != expected_status:
            raise ApiResponseError(f"unexpected status {status} for {method} {path}: {payload}")
        return payload

    @classmethod
    def get_json(cls, path: str, *, expected_status: int = 200) -> dict[str, Any]:
        return cls.request_json("GET", path, expected_status=expected_status)

    @classmethod
    def post_json(cls, path: str, body: dict[str, Any] | None = None, *, expected_status: int = 200) -> dict[str, Any]:
        return cls.request_json("POST", path, body or {}, expected_status=expected_status)

    @classmethod
    def put_json(cls, path: str, body: dict[str, Any], *, expected_status: int = 200) -> dict[str, Any]:
        return cls.request_json("PUT", path, body, expected_status=expected_status)

    def assert_success_envelope(self, payload: dict[str, Any]) -> None:
        self.assertIsInstance(payload.get("request_id"), str)
        self.assertIn("data", payload)
        self.assertIsInstance(payload.get("warnings"), list)
        self.assertEqual(payload.get("meta", {}).get("mode"), "fixture")
        self.assertRegex(payload.get("meta", {}).get("generated_at", ""), r"^\d{4}-\d{2}-\d{2}T")

    def assert_error_envelope(self, payload: dict[str, Any], code: str) -> None:
        self.assertIsInstance(payload.get("request_id"), str)
        self.assertEqual(payload.get("error", {}).get("code"), code)
        self.assertIn("message", payload.get("error", {}))
        self.assertIn("retryable", payload.get("error", {}))

    def assert_public_safe(self, payload: dict[str, Any]) -> None:
        text = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("hidden_ground_truth", text)
        self.assertNotIn("do_not_expose", text)
        self.assertNotIn("raw_response", text)
        for pattern in SENSITIVE_PATTERNS:
            self.assertIsNone(pattern.search(text), f"sensitive-looking token leaked: {pattern.pattern}")

    def start_session(self) -> str:
        payload = self.post_json(
            "/api/training/sessions",
            {
                "scenario_id": "scen-main-outbound-001",
                "mode": "fixture",
                "difficulty": "intermediate",
                "hint_policy": "on_request",
            },
        )
        self.assert_success_envelope(payload)
        self.assertEqual(payload["data"]["status"], "running")
        return payload["data"]["session_id"]

    def discover_core_evidence(self, session_id: str) -> set[str]:
        found: set[str] = set()
        queries = [
            (
                "utm_firewall",
                "firewall_log_search",
                {"source_ip": "10.23.14.52", "destination": "203.0.113.45"},
            ),
            ("nac", "ip_attribution", {"ip": "10.23.14.52"}),
            ("directive", "directive_compliance", {"directive_id": "Directive-2026-071"}),
            ("threat_intel", "indicator_enrichment", {"indicator": "203.0.113.45"}),
        ]
        for port, query_type, query in queries:
            payload = self.post_json(
                f"/api/training/sessions/{session_id}/equipment/query",
                {"port": port, "query_type": query_type, "query": query},
            )
            self.assert_success_envelope(payload)
            self.assertEqual(payload["data"]["port"], port)
            self.assertIn("view_model", payload["data"])
            for evidence in payload["data"]["evidence"]:
                self.assertFalse(evidence["raw_available"])
                found.add(evidence["evidence_id"])
        return found

    def test_01_health_and_adapter_status_are_real_http(self) -> None:
        health = self.get_json("/api/health")
        self.assert_success_envelope(health)
        self.assertEqual(health["data"]["service"], "cyber-defense-readiness-api")
        self.assertEqual(health["data"]["storage_backend"], "sqlite")

        adapters = self.get_json("/api/adapters/status")
        self.assert_success_envelope(adapters)
        ports = {item["port"]: item for item in adapters["data"]["items"]}
        self.assertEqual(ports["utm_firewall"]["status"], "available")
        self.assertEqual(ports["nac"]["mode"], "fixture")
        self.assert_public_safe(adapters)

    def test_02_home_and_scenario_catalog_are_public_safe(self) -> None:
        home = self.get_json("/api/training/home")
        self.assert_success_envelope(home)
        self.assertEqual(home["data"]["recommended_scenario"]["scenario_id"], "scen-main-outbound-001")
        self.assertGreaterEqual(len(home["data"]["skill_summary"]), 4)
        self.assert_public_safe(home)

        scenarios = self.get_json("/api/scenarios?difficulty=intermediate&max_minutes=15")
        self.assert_success_envelope(scenarios)
        self.assertEqual(len(scenarios["data"]["items"]), 1)
        self.assertIn("utm_firewall", scenarios["data"]["items"][0]["available_equipment"])

    def test_03_catalog_filters_and_missing_scenario_errors(self) -> None:
        goal = self.get_json("/api/scenarios?goal=IP%20%EA%B7%80%EC%86%8D")
        self.assert_success_envelope(goal)
        self.assertEqual(goal["data"]["items"][0]["scenario_id"], "scen-main-outbound-001")

        basic = self.get_json("/api/scenarios?difficulty=basic")
        self.assert_success_envelope(basic)
        self.assertEqual(basic["data"]["items"][0]["scenario_id"], "scen-harmful-ip-002")

        advanced = self.get_json("/api/scenarios?difficulty=advanced")
        self.assert_success_envelope(advanced)
        self.assertEqual(advanced["data"]["items"][0]["scenario_id"], "scen-cred-ransom-003")

        empty = self.get_json("/api/scenarios?max_minutes=1")
        self.assert_success_envelope(empty)
        self.assertEqual(empty["data"]["items"], [])

        missing = self.get_json("/api/scenarios/does-not-exist", expected_status=404)
        self.assert_error_envelope(missing, "SCENARIO_NOT_FOUND")

    def test_04_scenario_briefing_hides_ground_truth(self) -> None:
        briefing = self.get_json("/api/scenarios/scen-main-outbound-001")
        self.assert_success_envelope(briefing)
        self.assertIn("briefing", briefing["data"])
        self.assertEqual(len(briefing["data"]["available_equipment"]), 5)
        self.assert_public_safe(briefing)

    def test_05_session_start_get_and_event_feed(self) -> None:
        session_id = self.start_session()
        current = self.get_json(f"/api/training/sessions/{session_id}")
        self.assert_success_envelope(current)
        self.assertEqual(current["data"]["session_id"], session_id)
        self.assertEqual(current["data"]["status"], "running")

        events = self.get_json(f"/api/training/sessions/{session_id}/events")
        self.assert_success_envelope(events)
        titles = [item["title"] for item in events["data"]["items"]]
        self.assertIn("서비스 장애", titles)
        self.assertIn("의심 outbound", titles)

        later = self.get_json(f"/api/training/sessions/{session_id}/events?since_seq=2")
        self.assert_success_envelope(later)
        self.assertTrue(all(item["seq"] > 2 for item in later["data"]["items"]))
        self.assert_public_safe(events)

    def test_06_session_errors_are_enveloped(self) -> None:
        bad_start = self.post_json(
            "/api/training/sessions",
            {"scenario_id": "missing", "mode": "fixture"},
            expected_status=404,
        )
        self.assert_error_envelope(bad_start, "SCENARIO_NOT_FOUND")

        missing = self.get_json("/api/training/sessions/not-a-session", expected_status=404)
        self.assert_error_envelope(missing, "SESSION_NOT_FOUND")

    def test_07_equipment_query_discovers_all_core_evidence(self) -> None:
        session_id = self.start_session()
        found = self.discover_core_evidence(session_id)
        self.assertTrue({"fw-log-0182", "nac-node-10243", "endpoint-posture-10243", "directive-2026-071"}.issubset(found))

        state = self.get_json(f"/api/training/sessions/{session_id}")
        self.assert_success_envelope(state)
        self.assertTrue(set(found).issubset(set(state["data"]["discovered_evidence_ids"])))

    def test_08_equipment_query_validates_session_and_port(self) -> None:
        missing_session = self.post_json(
            "/api/training/sessions/missing/equipment/query",
            {"port": "utm_firewall", "query_type": "firewall_log_search", "query": {}},
            expected_status=404,
        )
        self.assert_error_envelope(missing_session, "SESSION_NOT_FOUND")

        session_id = self.start_session()
        bad_port = self.post_json(
            f"/api/training/sessions/{session_id}/equipment/query",
            {"port": "unknown", "query_type": "noop", "query": {}},
            expected_status=400,
        )
        self.assert_error_envelope(bad_port, "ADAPTER_UNAVAILABLE")

    def test_09_evidence_pinning_is_validated_and_idempotent(self) -> None:
        session_id = self.start_session()
        self.discover_core_evidence(session_id)

        bad_pin = self.post_json(
            f"/api/training/sessions/{session_id}/evidence/pins",
            {"evidence_ids": ["missing-evidence"], "note": "bad"},
            expected_status=404,
        )
        self.assert_error_envelope(bad_pin, "EVIDENCE_NOT_FOUND")

        good_pin = self.post_json(
            f"/api/training/sessions/{session_id}/evidence/pins",
            {"evidence_ids": ["fw-log-0182", "fw-log-0182", "directive-2026-071"], "note": "core"},
        )
        self.assert_success_envelope(good_pin)
        self.assertEqual(good_pin["data"]["pinned_evidence_ids"], ["fw-log-0182", "directive-2026-071"])

    def test_10_assessment_requires_real_discovered_evidence(self) -> None:
        session_id = self.start_session()
        self.discover_core_evidence(session_id)
        bad = self.put_json(
            f"/api/training/sessions/{session_id}/assessment",
            {
                "priority": "parallel_triage",
                "severity": "suspected_compromise",
                "response_efforts": ["quick_guidance"],
                "approval_required": False,
                "confidence": "low",
                "rationale": "no evidence",
                "evidence_ids": ["endpoint-posture-10243"],
            },
            expected_status=400,
        )
        self.assert_error_envelope(bad, "BAD_REQUEST")

        good = self.put_json(
            f"/api/training/sessions/{session_id}/assessment",
            {
                "priority": "parallel_triage",
                "severity": "suspected_compromise",
                "response_efforts": ["quick_guidance", "approval_required_action", "higher_report"],
                "approval_required": True,
                "confidence": "medium",
                "rationale": "FW 로그와 지시사항 gap, NAC 귀속 및 단말 posture를 근거로 병행 처리",
                "evidence_ids": ["fw-log-0182", "nac-node-10243", "endpoint-posture-10243", "directive-2026-071"],
            },
        )
        self.assert_success_envelope(good)
        self.assertEqual(good["data"]["assessment"]["severity"], "suspected_compromise")

    def test_11_evaluation_preview_reflects_current_evidence(self) -> None:
        session_id = self.start_session()
        self.discover_core_evidence(session_id)
        self.post_json(
            f"/api/training/sessions/{session_id}/evidence/pins",
            {"evidence_ids": ["fw-log-0182", "nac-node-10243", "directive-2026-071"], "note": "core"},
        )
        payload = self.post_json(
            f"/api/training/sessions/{session_id}/evaluation/preview",
            {"include_private_rubric_detail": False, "reason": "mission_desk_status_strip"},
        )
        self.assert_success_envelope(payload)
        self.assertEqual(payload["data"]["status"], "draft")
        self.assertIn("priority", payload["data"]["summary_strip"])
        self.assertIn("fw-log-0182", payload["data"]["evidence_citations"])
        self.assertTrue(payload["warnings"])

    def test_12_actions_validate_approval_and_evidence(self) -> None:
        session_id = self.start_session()
        self.discover_core_evidence(session_id)
        bad_approval = self.post_json(
            f"/api/training/sessions/{session_id}/actions",
            {
                "actions": [
                    {
                        "action_type": "policy_update_request",
                        "title": "bad",
                        "body": "should require approval",
                        "evidence_ids": ["fw-log-0182"],
                        "approval_required": False,
                    }
                ]
            },
            expected_status=400,
        )
        self.assert_error_envelope(bad_approval, "ACTION_REQUIRES_APPROVAL")

        bad_evidence = self.post_json(
            f"/api/training/sessions/{session_id}/actions",
            {
                "actions": [
                    {
                        "action_type": "report",
                        "title": "bad evidence",
                        "body": "missing evidence",
                        "evidence_ids": ["not-found"],
                        "approval_required": True,
                    }
                ]
            },
            expected_status=404,
        )
        self.assert_error_envelope(bad_evidence, "EVIDENCE_NOT_FOUND")

    def test_13_actions_submission_changes_session_status(self) -> None:
        session_id = self.start_session()
        self.discover_core_evidence(session_id)
        payload = self.post_json(
            f"/api/training/sessions/{session_id}/actions",
            {
                "actions": [
                    {
                        "action_type": "user_guidance",
                        "title": "사용자 단말 점검 안내",
                        "body": "백신 업데이트 후 업무용 홈페이지 접속을 재시도하도록 안내",
                        "evidence_ids": ["endpoint-posture-10243"],
                        "approval_required": False,
                    },
                    {
                        "action_type": "policy_update_request",
                        "title": "Directive 2026-071 blacklist 반영 요청",
                        "body": "203.0.113.45가 일부 scope에서 미반영되어 승인 요청",
                        "evidence_ids": ["fw-log-0182", "directive-2026-071"],
                        "approval_required": True,
                    },
                    {
                        "action_type": "report",
                        "title": "상위 조직 보고 초안",
                        "body": "민원, FW 로그, NAC 귀속, 단말 posture, 지시사항 gap을 근거로 보고",
                        "evidence_ids": ["fw-log-0182", "nac-node-10243", "endpoint-posture-10243", "directive-2026-071"],
                        "approval_required": True,
                    },
                ]
            },
        )
        self.assert_success_envelope(payload)
        self.assertEqual(payload["data"]["status"], "submitted")
        state = self.get_json(f"/api/training/sessions/{session_id}")
        self.assertEqual(state["data"]["status"], "submitted")

    def test_14_aar_create_and_get_are_citation_grounded(self) -> None:
        session_id = self.start_session()
        self.discover_core_evidence(session_id)
        self.put_json(
            f"/api/training/sessions/{session_id}/assessment",
            {
                "priority": "parallel_triage",
                "severity": "suspected_compromise",
                "response_efforts": ["quick_guidance", "approval_required_action"],
                "approval_required": True,
                "confidence": "medium",
                "rationale": "FW/NAC/Directive 기반",
                "evidence_ids": ["fw-log-0182", "nac-node-10243", "endpoint-posture-10243", "directive-2026-071"],
            },
        )
        self.post_json(
            f"/api/training/sessions/{session_id}/actions",
            {
                "actions": [
                    {
                        "action_type": "report",
                        "title": "보고",
                        "body": "근거 기반 보고",
                        "evidence_ids": ["fw-log-0182", "nac-node-10243", "directive-2026-071"],
                        "approval_required": True,
                    }
                ]
            },
        )
        create = self.post_json(
            f"/api/training/sessions/{session_id}/aar",
            {"include_dynamic_evaluation": True, "include_operations_reuse_hint": True},
        )
        self.assert_success_envelope(create)
        self.assertEqual(create["data"]["status"], "ready")
        self.assertGreaterEqual(create["data"]["score"], 70)
        self.assertIn("evidence_citations", create["data"]["dynamic_evaluation"])

        get = self.get_json(f"/api/training/sessions/{session_id}/aar")
        self.assert_success_envelope(get)
        self.assertEqual(get["data"]["aar_id"], create["data"]["aar_id"])
        self.assertIn("fw-log-0182", get["data"]["checked_evidence"])
        self.assertTrue(get["data"]["operations_reuse_available"])
        self.assert_public_safe(get)

    def test_15_aar_get_before_create_is_clear_error(self) -> None:
        session_id = self.start_session()
        payload = self.get_json(f"/api/training/sessions/{session_id}/aar", expected_status=404)
        self.assert_error_envelope(payload, "AAR_NOT_FOUND")

    def test_16_ops_reuse_uses_training_evidence_model(self) -> None:
        session_id = self.start_session()
        self.discover_core_evidence(session_id)
        payload = self.post_json(
            "/api/ops/cases/from-training-session",
            {
                "session_id": session_id,
                "reuse_evidence_ids": ["fw-log-0182", "nac-node-10243", "endpoint-posture-10243", "directive-2026-071"],
            },
        )
        self.assert_success_envelope(payload)
        self.assertEqual(payload["data"]["source_session_id"], session_id)
        self.assertEqual(payload["data"]["status"], "draft")
        self.assertIn("일일 보고 문단", payload["data"]["recommended_outputs"])
        self.assert_public_safe(payload)

    def test_17_ops_reuse_rejects_missing_evidence(self) -> None:
        session_id = self.start_session()
        payload = self.post_json(
            "/api/ops/cases/from-training-session",
            {"session_id": session_id, "reuse_evidence_ids": ["missing"]},
            expected_status=404,
        )
        self.assert_error_envelope(payload, "EVIDENCE_NOT_FOUND")

    def test_18_openapi_contains_all_demo_paths(self) -> None:
        schema = self.get_json("/openapi.json")
        paths = schema["paths"]
        required = [
            "/api/training/home",
            "/api/scenarios",
            "/api/training/sessions",
            "/api/training/sessions/{session_id}/equipment/query",
            "/api/training/sessions/{session_id}/evidence/pins",
            "/api/training/sessions/{session_id}/assessment",
            "/api/training/sessions/{session_id}/evaluation/preview",
            "/api/training/sessions/{session_id}/actions",
            "/api/training/sessions/{session_id}/aar",
            "/api/ops/cases/from-training-session",
        ]
        for path in required:
            self.assertIn(path, paths)

    def test_19_sqlite_storage_survives_server_restart(self) -> None:
        session_id = self.start_session()
        self.discover_core_evidence(session_id)
        self.post_json(
            f"/api/training/sessions/{session_id}/evidence/pins",
            {"evidence_ids": ["fw-log-0182", "directive-2026-071"], "note": "restart proof"},
        )

        self.restart_server()

        state = self.get_json(f"/api/training/sessions/{session_id}")
        self.assert_success_envelope(state)
        self.assertEqual(state["data"]["session_id"], session_id)
        self.assertIn("fw-log-0182", state["data"]["discovered_evidence_ids"])
        self.assertEqual(state["data"]["pinned_evidence_ids"], ["fw-log-0182", "directive-2026-071"])


if __name__ == "__main__":
    unittest.main()
