"""B-12 helpdesk answering, citation enforcement, and persistence tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from d4d.api.main import app
from d4d.api.envelope import ApiError
from d4d.llm import LlmResult, OpenAICompatibleLlmAdapter, RuleBasedFallback
from d4d.repositories.operations import SQLiteOperationsRepository
from d4d.services.helpdesk_service import HelpdeskService
from d4d.services.helpdesk_service import helpdesk_service as global_helpdesk_service
from d4d.services.knowledge_service import KnowledgeService
from d4d.services.operations_runtime import OperationsRuntimeService


class UnavailableLlm:
    def available(self) -> bool:
        return False

    def complete(self, prompt: str, *, max_tokens: int = 400, temperature: float = 0.2) -> LlmResult:
        raise AssertionError("미가용 LLM은 호출되면 안 된다")


class CannedOpenAICompatibleLlm:
    """LLM API가 있을 때의 경로를 검증하기 위한 고정 응답 어댑터."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.prompts: list[str] = []

    def available(self) -> bool:
        return True

    def complete(self, prompt: str, *, max_tokens: int = 400, temperature: float = 0.2) -> LlmResult:
        self.prompts.append(prompt)
        return LlmResult(text=self.text, model="canned-openai-compatible")


def build_stack(tmpdir: str, llm=None):
    repository = SQLiteOperationsRepository(Path(tmpdir) / "ops.sqlite3")
    OperationsRuntimeService(repository)  # unit seed
    knowledge = KnowledgeService(repository)
    helpdesk = HelpdeskService(repository, knowledge, llm=llm or UnavailableLlm())
    return repository, knowledge, helpdesk


class HelpdeskAnswerTest(unittest.TestCase):
    def test_grounded_answer_with_citations_rule_engine(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, _, helpdesk = build_stack(tmpdir)
            inquiry = helpdesk.create_inquiry(
                {"unit_id": "unit-bn-a", "question": "유해 IP 지시 반영이 일부 누락됐을 때 절차는?"}
            )

            self.assertTrue(inquiry["grounded"])
            self.assertEqual(inquiry["status"], "answered")
            self.assertEqual(inquiry["engine"], "rule")
            self.assertGreaterEqual(len(inquiry["citations"]["knowledge_ids"]), 1)
            self.assertGreaterEqual(len(inquiry["citations"]["evidence_ids"]), 1)
            self.assertIn("승인 절차", inquiry["answer"])

    def test_unrelated_question_returns_no_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, _, helpdesk = build_stack(tmpdir)
            inquiry = helpdesk.create_inquiry(
                {"unit_id": "unit-bn-b", "question": "우주 정거장 도킹 절차 알려줘"}
            )

            self.assertFalse(inquiry["grounded"])
            self.assertEqual(inquiry["status"], "needs_review")
            self.assertIn("근거 부족", inquiry["answer"])
            self.assertEqual(inquiry["citations"]["knowledge_ids"], [])
            self.assertEqual(inquiry["citations"]["evidence_ids"], [])

    def test_llm_api_path_stays_grounded_and_cited(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            llm = CannedOpenAICompatibleLlm("지시 대비 미반영 IP를 대조해 승인 요청으로 상신하세요.")
            _, _, helpdesk = build_stack(tmpdir, llm=llm)
            inquiry = helpdesk.create_inquiry(
                {"unit_id": "unit-bn-a", "question": "유해 IP 지시 반영 누락 절차 문의"}
            )

            self.assertEqual(inquiry["engine"], "llm")
            self.assertFalse(inquiry["fallback_used"])
            self.assertGreaterEqual(len(inquiry["citations"]["knowledge_ids"]), 1)
            # 프롬프트는 검색 컨텍스트 범위 제한을 명시한다 (환각 방지 계약)
            self.assertIn("범위 안에서만", llm.prompts[0])
            self.assertIn("절대 만들지 마세요", llm.prompts[0])

    def test_llm_failure_falls_back_to_rule(self) -> None:
        class BrokenLlm:
            def available(self) -> bool:
                return True

            def complete(self, prompt: str, *, max_tokens: int = 400, temperature: float = 0.2) -> LlmResult:
                raise RuntimeError("llm endpoint crashed")

        with tempfile.TemporaryDirectory() as tmpdir:
            _, _, helpdesk = build_stack(tmpdir, llm=BrokenLlm())
            inquiry = helpdesk.create_inquiry({"question": "NAC 미준수 단말 격리 기준 문의"})
            self.assertEqual(inquiry["engine"], "rule")
            self.assertTrue(inquiry["grounded"])

    def test_resolve_accumulates_faq_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, knowledge, helpdesk = build_stack(tmpdir)
            inquiry = helpdesk.create_inquiry(
                {"unit_id": "unit-bn-a", "question": "지시사항 반영 확인은 어떻게 회신하나요?"}
            )
            resolved = helpdesk.resolve_inquiry(inquiry["inquiry_id"])

            self.assertEqual(resolved["status"], "resolved")
            faq = knowledge.get(resolved["accumulated_knowledge_id"])
            self.assertEqual(faq["source_type"], "inquiry")
            self.assertIn("FAQ", faq["tags"])

            with self.assertRaises(ApiError) as ctx:
                helpdesk.resolve_inquiry(inquiry["inquiry_id"])
            self.assertEqual(ctx.exception.code, "BAD_REQUEST")

    def test_inquiries_persist_across_repository_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ops.sqlite3"
            repository = SQLiteOperationsRepository(db_path)
            OperationsRuntimeService(repository)
            knowledge = KnowledgeService(repository)
            helpdesk = HelpdeskService(repository, knowledge, llm=UnavailableLlm())
            inquiry = helpdesk.create_inquiry({"question": "outbound 우선순위 판단 문의"})

            reopened_repo = SQLiteOperationsRepository(db_path)
            reopened = HelpdeskService(reopened_repo, KnowledgeService(reopened_repo), llm=UnavailableLlm())
            survivors = reopened.list_inquiries({})["items"]
            self.assertTrue(any(item["inquiry_id"] == inquiry["inquiry_id"] for item in survivors))

    def test_rule_fallback_port_contract(self) -> None:
        fallback = RuleBasedFallback()
        self.assertTrue(fallback.available())
        self.assertEqual(fallback.complete("요약 텍스트").model, "rule-based")

    def test_openai_compatible_adapter_uses_chat_completions(self) -> None:
        captured = {}

        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {"model": "demo-model", "choices": [{"message": {"content": "응답"}}]}
                ).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        with mock.patch.dict("os.environ", {"D4D_LLM_API_KEY": "test-key"}):
            adapter = OpenAICompatibleLlmAdapter(
                base_url="https://llm-gateway.example/v1",
                model="demo-model",
            )
        with mock.patch("urllib.request.urlopen", fake_urlopen):
            result = adapter.complete("근거 안에서 답변", max_tokens=123, temperature=0.1)

        self.assertEqual(result.text, "응답")
        self.assertEqual(captured["url"], "https://llm-gateway.example/v1/chat/completions")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(captured["body"]["messages"][0]["content"], "근거 안에서 답변")
        self.assertEqual(captured["body"]["max_tokens"], 123)

    def test_helpdesk_api_endpoints(self) -> None:
        old_llm = global_helpdesk_service.llm
        global_helpdesk_service.llm = UnavailableLlm()
        client = TestClient(app)

        try:
            created = client.post(
                "/api/helpdesk/inquiries",
                json={"unit_id": "unit-bn-a", "question": "유해 IP 차단 지시 미반영 절차 문의 (API)"},
            )
            self.assertEqual(created.status_code, 200)
            data = created.json()["data"]
            self.assertTrue(data["grounded"])
            self.assertGreaterEqual(len(data["citations"]["knowledge_ids"]), 1)

            listing = client.get("/api/helpdesk/inquiries", params={"unit_id": "unit-bn-a"})
            self.assertEqual(listing.status_code, 200)
            self.assertTrue(any(item["inquiry_id"] == data["inquiry_id"] for item in listing.json()["data"]["items"]))

            resolved = client.post(f"/api/helpdesk/inquiries/{data['inquiry_id']}/resolve")
            self.assertEqual(resolved.status_code, 200)
            self.assertTrue(resolved.json()["data"]["accumulated_knowledge_id"].startswith("kb-"))

            empty = client.post("/api/helpdesk/inquiries", json={"question": "  "})
            self.assertEqual(empty.status_code, 400)
        finally:
            global_helpdesk_service.llm = old_llm


if __name__ == "__main__":
    unittest.main()
