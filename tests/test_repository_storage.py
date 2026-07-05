"""Repository port tests for durable mission storage adapters."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from d4d.repositories import (
    InMemoryMissionSessionRepository,
    SQLiteMissionSessionRepository,
    create_mission_repository_from_env,
)


def sample_session(session_id: str = "sct-test-001") -> dict:
    return {
        "session_id": session_id,
        "scenario_id": "scen-main-outbound-001",
        "status": "running",
        "started_at": "2026-07-04T05:34:00Z",
        "elapsed_seconds": 0,
        "mode": "fixture",
        "visible_event_seq": 0,
        "pinned_evidence_ids": [],
        "discovered_evidence_ids": ["fw-log-0182"],
        "evidence": {"fw-log-0182": {"evidence_id": "fw-log-0182", "raw_available": False}},
        "current_assessment": None,
        "submitted_actions": [],
        "aar": None,
    }


class RepositoryStorageTest(unittest.TestCase):
    def test_sqlite_repository_persists_session_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "readiness.sqlite3"
            first = SQLiteMissionSessionRepository(db_path)
            first.save_session(sample_session())

            second = SQLiteMissionSessionRepository(db_path)
            loaded = second.get_session("sct-test-001")

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["scenario_id"], "scen-main-outbound-001")
            self.assertEqual(loaded["discovered_evidence_ids"], ["fw-log-0182"])

    def test_sqlite_sequence_is_durable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "readiness.sqlite3"
            first = SQLiteMissionSessionRepository(db_path)
            self.assertEqual(first.next_sequence("training_session"), 1)

            second = SQLiteMissionSessionRepository(db_path)
            self.assertEqual(second.next_sequence("training_session"), 2)

    def test_factory_uses_sqlite_env_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "env.sqlite3"
            old_backend = os.environ.get("D4D_STORAGE_BACKEND")
            old_path = os.environ.get("D4D_SQLITE_PATH")
            try:
                os.environ["D4D_STORAGE_BACKEND"] = "sqlite"
                os.environ["D4D_SQLITE_PATH"] = str(db_path)
                repo = create_mission_repository_from_env()
                self.assertIsInstance(repo, SQLiteMissionSessionRepository)
                repo.save_session(sample_session("sct-env-001"))
                self.assertTrue(db_path.exists())
            finally:
                _restore_env("D4D_STORAGE_BACKEND", old_backend)
                _restore_env("D4D_SQLITE_PATH", old_path)

    def test_memory_repository_is_explicitly_non_persistent(self) -> None:
        first = InMemoryMissionSessionRepository()
        first.save_session(sample_session("sct-memory-001"))
        second = InMemoryMissionSessionRepository()
        self.assertIsNone(second.get_session("sct-memory-001"))


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
