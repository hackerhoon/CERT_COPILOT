"""B-08 Operations foundation tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from d4d.api.main import app
from d4d.fixtures.operations import OPERATION_UNITS
from d4d.repositories.operations import SQLiteOperationsRepository
from d4d.services.operations_runtime import OperationsRuntimeService


class OperationsFoundationTest(unittest.TestCase):
    def test_sqlite_operations_repository_keeps_seed_units_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ops.sqlite3"
            first = SQLiteOperationsRepository(db_path)
            first.seed_units(OPERATION_UNITS)

            second = SQLiteOperationsRepository(db_path)
            second.seed_units(OPERATION_UNITS)
            units = second.list_units()

            self.assertEqual(len(units), 3)
            self.assertEqual(units[0]["unit_id"], "unit-corps-cyber")
            self.assertEqual(units[1]["parent_unit_id"], "unit-corps-cyber")

    def test_operations_service_computes_ancestor_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteOperationsRepository(Path(tmpdir) / "ops.sqlite3")
            service = OperationsRuntimeService(repo)

            self.assertEqual(service.ancestors("unit-bn-a"), ["unit-corps-cyber"])
            self.assertEqual(service.escalation_depth("low"), 1)
            self.assertGreaterEqual(service.escalation_depth("critical"), 2)

    def test_ops_units_endpoint_returns_synthetic_hierarchy(self) -> None:
        client = TestClient(app)
        response = client.get("/api/ops/units")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("request_id", payload)
        self.assertEqual(payload["meta"]["mode"], "fixture")
        unit_ids = {item["unit_id"] for item in payload["data"]["items"]}
        self.assertEqual(unit_ids, {"unit-corps-cyber", "unit-bn-a", "unit-bn-b"})
        bn_a = next(item for item in payload["data"]["items"] if item["unit_id"] == "unit-bn-a")
        self.assertEqual(bn_a["ancestor_unit_ids"], ["unit-corps-cyber"])
        self.assertEqual(payload["data"]["default_viewer_unit_id"], "unit-bn-a")
        self.assertEqual(payload["data"]["managed_node_count_total"], 10420)

    def test_ops_adapter_status_is_in_app_only(self) -> None:
        client = TestClient(app)
        response = client.get("/api/ops/adapters/status")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        ports = {item["port"]: item for item in payload["data"]["items"]}
        self.assertEqual(ports["notification"]["mode"], "fixture")
        self.assertIn("in_app_record_only", ports["notification"]["capabilities"])
        self.assertFalse(ports["notification"]["external_delivery"])


if __name__ == "__main__":
    unittest.main()
