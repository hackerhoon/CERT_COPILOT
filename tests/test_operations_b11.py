"""B-11 knowledge accumulation, redaction, and persistence tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from d4d.api.main import app
from d4d.api.envelope import ApiError
from d4d.repositories.operations import SQLiteOperationsRepository
from d4d.services.knowledge_service import KnowledgeService
from d4d.services.operations_runtime import OperationsRuntimeService


def build_stack(tmpdir: str) -> tuple[OperationsRuntimeService, KnowledgeService]:
    repository = SQLiteOperationsRepository(Path(tmpdir) / "ops.sqlite3")
    operations = OperationsRuntimeService(repository)
    knowledge = KnowledgeService(repository)
    operations.knowledge_accumulator = knowledge.accumulate_from_incident
    return operations, knowledge


class KnowledgeAccumulationTest(unittest.TestCase):
    def test_seed_loaded_and_search_filters(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, knowledge = build_stack(tmpdir)

            everything = knowledge.search({})
            self.assertEqual(everything["total"], 5)
            self.assertGreaterEqual(len(everything["top_tags"]), 5)
            self.assertEqual(everything["by_source"]["aar"], 2)

            by_query = knowledge.search({"query": "크리덴셜"})
            self.assertEqual(len(by_query["items"]), 1)
            self.assertEqual(by_query["items"][0]["source_id"], "inc-20260702-004")

            by_tag = knowledge.search({"tags": "directive-gap"})
            self.assertEqual(len(by_tag["items"]), 2)

            by_unit = knowledge.search({"unit_id": "unit-bn-b"})
            self.assertEqual(len(by_unit["items"]), 2)

    def test_incident_close_accumulates_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            operations, knowledge = build_stack(tmpdir)
            incident = operations.create_incident(
                {"unit_id": "unit-bn-a", "title": "축적 검증 사건", "severity": "low", "note": "관측"}
            )
            incident_id = incident["incident_id"]
            for to_status in ("in_progress", "contained"):
                operations.transition_incident_status(
                    incident_id, {"actor_unit_id": "unit-bn-a", "to_status": to_status}
                )
            closed = operations.transition_incident_status(
                incident_id, {"actor_unit_id": "unit-bn-a", "to_status": "closed", "note": "종결 보고"}
            )

            knowledge_id = closed["accumulated_knowledge_id"]
            self.assertIsNotNone(knowledge_id)
            item = knowledge.get(knowledge_id)
            self.assertEqual(item["source_type"], "incident")
            self.assertEqual(item["source_id"], incident_id)
            self.assertIn("축적 검증 사건", item["title"])

            # dedup: 같은 원본을 다시 축적해도 새 지식이 생기지 않는다
            again = knowledge.accumulate_from_incident(operations.get_incident(incident_id))
            self.assertEqual(again["knowledge_id"], knowledge_id)
            self.assertEqual(knowledge.search({})["total"], 6)

    def test_aar_accumulation_hook_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, knowledge = build_stack(tmpdir)
            aar = {
                "aar_id": "aar-sct-test-01",
                "summary": "핵심 근거는 확인했으나 보고가 늦었다",
                "grade": "B",
                "score": 76,
                "dynamic_evaluation": {
                    "rubric_hits": ["FW 로그 우선 확인"],
                    "rubric_misses": ["단말 posture 보고 누락"],
                    "evidence_citations": ["fw-log-0182"],
                },
            }
            item = knowledge.accumulate_from_aar(aar)
            self.assertEqual(item["source_type"], "aar")
            self.assertEqual(item["source_id"], "aar-sct-test-01")
            self.assertIn("훈련AAR", item["tags"])
            # dedup: 같은 AAR 재생성 시 새 지식이 생기지 않는다
            self.assertEqual(knowledge.accumulate_from_aar(aar)["knowledge_id"], item["knowledge_id"])

    def test_redaction_blocks_secrets_and_masks_pii(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, knowledge = build_stack(tmpdir)

            with self.assertRaises(ApiError) as blocked:
                knowledge.create_manual(
                    {"title": "유출 계정", "summary": "password: hunter2secret 로 접속"}
                )
            self.assertEqual(blocked.exception.code, "REDACTION_BLOCKED")

            masked = knowledge.create_manual(
                {
                    "title": "외부 제보 대응",
                    "summary": "제보자 someone@example.com 이 8.8.8.8 통신 흔적을 보고함",
                }
            )
            self.assertNotIn("someone@example.com", masked["summary"])
            self.assertNotIn("8.8.8.8", masked["summary"])
            self.assertIn("***@***", masked["summary"])
            self.assertIn("8.8.***.***", masked["summary"])

    def test_unknown_evidence_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, knowledge = build_stack(tmpdir)
            with self.assertRaises(ApiError) as ctx:
                knowledge.create_manual(
                    {"title": "x", "summary": "y", "evidence_ids": ["not-a-real-evidence"]}
                )
            self.assertEqual(ctx.exception.code, "UNKNOWN_EVIDENCE")

    def test_knowledge_persists_across_repository_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ops.sqlite3"
            first = KnowledgeService(SQLiteOperationsRepository(db_path))
            created = first.create_manual(
                {"title": "인수인계 지식", "summary": "담당자 인수인계 후에도 유지되어야 한다", "tags": ["인수인계"]}
            )

            reopened = KnowledgeService(SQLiteOperationsRepository(db_path))
            survived = reopened.get(created["knowledge_id"])
            self.assertEqual(survived["title"], "인수인계 지식")
            # seed는 source dedup으로 다시 늘어나지 않는다
            self.assertEqual(reopened.search({})["total"], 6)

    def test_knowledge_api_endpoints(self) -> None:
        client = TestClient(app)

        listing = client.get("/api/knowledge")
        self.assertEqual(listing.status_code, 200)
        data = listing.json()["data"]
        self.assertGreaterEqual(data["total"], 5)
        self.assertTrue(all("knowledge_id" in item for item in data["items"]))

        first_id = data["items"][0]["knowledge_id"]
        detail = client.get(f"/api/knowledge/{first_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["data"]["knowledge_id"], first_id)

        missing = client.get("/api/knowledge/kb-none")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["error"]["code"], "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
