"""B-09 Operations incident and notification tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from d4d.api.main import app
from d4d.repositories.operations import SQLiteOperationsRepository
from d4d.services.operations_runtime import OperationsRuntimeService


class OperationsIncidentNotificationTest(unittest.TestCase):
    def test_create_incident_notifies_unit_and_ancestor_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OperationsRuntimeService(SQLiteOperationsRepository(Path(tmpdir) / "ops.sqlite3"))

            incident = service.create_incident(
                {
                    "unit_id": "unit-bn-a",
                    "title": "의심 outbound 접수",
                    "severity": "high",
                    "note": "FW 로그와 NAC posture 근거 확인",
                    "evidence_ids": ["fw-log-0182", "nac-node-10243"],
                }
            )

            self.assertEqual(incident["status"], "received")
            self.assertEqual(incident["notified_unit_ids"], ["unit-bn-a", "unit-corps-cyber"])
            self.assertEqual(len(incident["notifications"]), 2)
            self.assertEqual(incident["timeline"][0]["to"], "received")

            feed = service.list_notifications({"unit_id": "unit-corps-cyber"})
            self.assertEqual(feed["unread_count"], 1)
            self.assertEqual(feed["items"][0]["incident_id"], incident["incident_id"])

    def test_sqlite_repository_persists_incidents_and_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ops.sqlite3"
            first = OperationsRuntimeService(SQLiteOperationsRepository(db_path))
            created = first.create_incident(
                {
                    "unit_id": "unit-bn-b",
                    "title": "NAC posture 미준수 급증",
                    "severity": "medium",
                    "note": "야간 점검 중 synthetic 패턴 관측",
                    "evidence_ids": [],
                }
            )

            second = OperationsRuntimeService(SQLiteOperationsRepository(db_path))
            incidents = second.list_incidents({"unit_id": "unit-corps-cyber"})
            notifications = second.list_notifications({"unit_id": "unit-corps-cyber"})

            self.assertEqual([item["incident_id"] for item in incidents["items"]], [created["incident_id"]])
            self.assertEqual(notifications["items"][0]["incident_id"], created["incident_id"])

    def test_create_incident_rejects_unknown_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OperationsRuntimeService(SQLiteOperationsRepository(Path(tmpdir) / "ops.sqlite3"))

            with self.assertRaises(Exception) as ctx:
                service.create_incident(
                    {
                        "unit_id": "unit-bn-a",
                        "title": "잘못된 근거",
                        "severity": "low",
                        "evidence_ids": ["real-secret-evidence"],
                    }
                )

            self.assertIn("UNKNOWN_EVIDENCE", str(getattr(ctx.exception, "code", "")))

    def test_ops_incident_api_contract(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/api/ops/incidents",
            json={
                "unit_id": "unit-bn-a",
                "title": "방화벽 지시 반영 누락 의심",
                "severity": "high",
                "note": "Directive-2026-071 대조 필요",
                "evidence_ids": ["directive-2026-071", "fw-log-0182"],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["meta"]["mode"], "fixture")
        data = payload["data"]
        self.assertEqual(data["unit_id"], "unit-bn-a")
        self.assertEqual(data["status"], "received")
        self.assertIn("unit-corps-cyber", data["notified_unit_ids"])
        self.assertEqual(len(data["notifications"]), 2)

        list_payload = client.get("/api/ops/incidents", params={"unit_id": "unit-bn-a"}).json()
        self.assertTrue(any(item["incident_id"] == data["incident_id"] for item in list_payload["data"]["items"]))

        feed_payload = client.get("/api/ops/notifications", params={"unit_id": "unit-corps-cyber"}).json()
        feed = [item for item in feed_payload["data"]["items"] if item["incident_id"] == data["incident_id"]]
        self.assertEqual(len(feed), 1)
        self.assertFalse(feed[0]["read"])

        ack_payload = client.post(f"/api/ops/notifications/{feed[0]['notification_id']}/ack", json={}).json()
        self.assertTrue(ack_payload["data"]["read"])


if __name__ == "__main__":
    unittest.main()
