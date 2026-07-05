"""Smoke tests for 이성진 B-01/B-02 API work."""

from __future__ import annotations

import json
import unittest

from fastapi.testclient import TestClient

from d4d.api.main import app


class ReadinessApiSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def assert_success_envelope(self, payload: dict) -> None:
        self.assertIn("request_id", payload)
        self.assertIn("data", payload)
        self.assertIn("warnings", payload)
        self.assertIn("meta", payload)
        self.assertEqual(payload["meta"]["mode"], "fixture")

    def test_health_endpoint_responds(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assert_success_envelope(payload)
        self.assertEqual(payload["data"]["status"], "ok")

    def test_adapter_status_fixture_is_available(self) -> None:
        response = self.client.get("/api/adapters/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assert_success_envelope(payload)
        ports = {item["port"]: item for item in payload["data"]["items"]}
        self.assertEqual(ports["utm_firewall"]["status"], "available")
        self.assertEqual(ports["nac"]["mode"], "fixture")
        self.assertIn("threat_intel", ports)

    def test_home_fixture_unblocks_frontend(self) -> None:
        response = self.client.get("/api/training/home")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assert_success_envelope(payload)
        self.assertEqual(payload["data"]["recommended_scenario"]["scenario_id"], "scen-main-outbound-001")
        self.assertGreaterEqual(len(payload["data"]["skill_summary"]), 4)

    def test_scenario_catalog_and_filters(self) -> None:
        response = self.client.get("/api/scenarios", params={"difficulty": "intermediate", "max_minutes": 15})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assert_success_envelope(payload)
        items = payload["data"]["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["scenario_id"], "scen-main-outbound-001")

    def test_scenario_briefing_hides_ground_truth(self) -> None:
        response = self.client.get("/api/scenarios/scen-main-outbound-001")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assert_success_envelope(payload)
        text = json.dumps(payload["data"], ensure_ascii=False)
        self.assertIn("briefing", payload["data"])
        self.assertIn("rubric_summary", payload["data"])
        self.assertNotIn("hidden_ground_truth", text)
        self.assertNotIn("do_not_expose", text)

    def test_missing_scenario_uses_error_envelope(self) -> None:
        response = self.client.get("/api/scenarios/missing")
        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertIn("request_id", payload)
        self.assertEqual(payload["error"]["code"], "SCENARIO_NOT_FOUND")
        self.assertEqual(payload["error"]["details"]["scenario_id"], "missing")


if __name__ == "__main__":
    unittest.main()
