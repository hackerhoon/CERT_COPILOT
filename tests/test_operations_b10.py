"""B-10 Operations status machine and status-board tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from d4d.api.main import app
from d4d.api.envelope import ApiError
from d4d.repositories.operations import SQLiteOperationsRepository
from d4d.services.operations_runtime import OperationsRuntimeService


def create_sample_incident(service: OperationsRuntimeService, unit_id: str = "unit-bn-a") -> dict:
    return service.create_incident(
        {
            "unit_id": unit_id,
            "title": "상태 전이 테스트",
            "severity": "high",
            "note": "초기 접수",
            "evidence_ids": ["fw-log-0182"],
        }
    )


class OperationsStatusMachineTest(unittest.TestCase):
    def test_status_transition_records_timeline_and_notifies_ancestors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OperationsRuntimeService(SQLiteOperationsRepository(Path(tmpdir) / "ops.sqlite3"))
            incident = create_sample_incident(service)

            result = service.transition_incident_status(
                incident["incident_id"],
                {
                    "actor_unit_id": "unit-bn-a",
                    "to_status": "in_progress",
                    "note": "조치 시작",
                    "evidence_ids": ["fw-log-0182"],
                },
            )

            self.assertEqual(result["status"], "in_progress")
            self.assertFalse(result["approval_required"])
            self.assertFalse(result["executed"])
            self.assertEqual(result["timeline_entry"]["from"], "received")
            self.assertEqual(result["timeline_entry"]["to"], "in_progress")
            self.assertEqual(result["notifications"][0]["kind"], "status_changed")
            self.assertEqual(result["notifications"][0]["to_unit_id"], "unit-corps-cyber")

            detail = service.get_incident(incident["incident_id"])
            self.assertEqual(detail["status"], "in_progress")
            self.assertEqual(len(detail["timeline"]), 2)

    def test_status_transition_rejects_higher_unit_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OperationsRuntimeService(SQLiteOperationsRepository(Path(tmpdir) / "ops.sqlite3"))
            incident = create_sample_incident(service)

            with self.assertRaises(ApiError) as ctx:
                service.transition_incident_status(
                    incident["incident_id"],
                    {"actor_unit_id": "unit-corps-cyber", "to_status": "in_progress"},
                )

            self.assertEqual(ctx.exception.code, "FORBIDDEN")

    def test_invalid_transition_returns_allowed_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OperationsRuntimeService(SQLiteOperationsRepository(Path(tmpdir) / "ops.sqlite3"))
            incident = create_sample_incident(service)

            with self.assertRaises(ApiError) as ctx:
                service.transition_incident_status(
                    incident["incident_id"],
                    {"actor_unit_id": "unit-bn-a", "to_status": "closed"},
                )

            self.assertEqual(ctx.exception.code, "INVALID_TRANSITION")
            self.assertEqual(ctx.exception.details["allowed"], ["in_progress", "needs_approval", "escalated"])

    def test_needs_approval_is_proposal_not_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OperationsRuntimeService(SQLiteOperationsRepository(Path(tmpdir) / "ops.sqlite3"))
            incident = create_sample_incident(service)

            result = service.transition_incident_status(
                incident["incident_id"],
                {"actor_unit_id": "unit-bn-a", "to_status": "needs_approval", "note": "차단 정책 반영 요청"},
            )

            self.assertEqual(result["status"], "needs_approval")
            self.assertTrue(result["approval_required"])
            self.assertFalse(result["executed"])
            self.assertEqual(result["allowed_transitions"], ["in_progress", "escalated"])

    def test_timeline_and_status_board_endpoints(self) -> None:
        client = TestClient(app)
        create_payload = client.post(
            "/api/ops/incidents",
            json={
                "unit_id": "unit-bn-a",
                "title": "상태판 API 테스트",
                "severity": "medium",
                "note": "접수",
                "evidence_ids": ["fw-log-0182"],
            },
        ).json()
        incident_id = create_payload["data"]["incident_id"]

        transition = client.post(
            f"/api/ops/incidents/{incident_id}/status",
            json={"actor_unit_id": "unit-bn-a", "to_status": "in_progress", "note": "조치 시작", "evidence_ids": ["fw-log-0182"]},
        )
        self.assertEqual(transition.status_code, 200)
        self.assertEqual(transition.json()["data"]["status"], "in_progress")

        timeline = client.get(f"/api/ops/incidents/{incident_id}/timeline")
        self.assertEqual(timeline.status_code, 200)
        self.assertEqual(timeline.json()["data"]["incident_id"], incident_id)
        self.assertEqual(len(timeline.json()["data"]["items"]), 2)

        board = client.get("/api/ops/status-board", params={"unit_id": "unit-corps-cyber"})
        self.assertEqual(board.status_code, 200)
        data = board.json()["data"]
        self.assertIn("unit-bn-a", data["subordinate_units"])
        item = next(item for item in data["incidents"] if item["incident_id"] == incident_id)
        self.assertEqual(item["status"], "in_progress")
        self.assertEqual(item["last_transition"], "received→in_progress")


if __name__ == "__main__":
    unittest.main()
