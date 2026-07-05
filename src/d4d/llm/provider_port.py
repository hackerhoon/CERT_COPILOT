"""LLM provider port — OpenAI-compatible chat completions endpoint (B-12).

모든 LLM 런타임은 OpenAI 호환 `/v1/chat/completions` 계약 뒤에 둔다.
설정이 없거나 호출에 실패하면 helpdesk service가 규칙/검색 폴백으로 답한다.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from d4d.config import load_dotenv, project_root


@dataclass
class LlmResult:
    text: str
    model: str


class LlmProviderPort(Protocol):
    def available(self) -> bool: ...

    def complete(self, prompt: str, *, max_tokens: int = 400, temperature: float = 0.2) -> LlmResult: ...


class OpenAICompatibleLlmAdapter:
    """OpenAI-compatible `/v1/chat/completions` adapter.

    Primary env vars:
    - `D4D_LLM_BASE_URL`: base URL, e.g. `https://api.openai.com/v1`.
    - `D4D_LLM_API_KEY`: optional bearer token.
    - `D4D_LLM_MODEL`: chat completion model.

    `OPENAI_API_URL`/`OPENAI_BASE_URL` and `OPENAI_API_KEY` are accepted as
    common aliases.
    """

    def __init__(self, base_url: str | None = None, model: str | None = None, timeout: float = 4.0) -> None:
        env = load_dotenv(project_root() / ".env")
        self.model = model or _first_env(env, "D4D_LLM_MODEL", "OPENAI_MODEL") or "gpt-4o-mini"
        self.api_key = _first_env(env, "D4D_LLM_API_KEY", "OPENAI_API_KEY") or ""
        configured_base_url = base_url or _first_env(env, "D4D_LLM_BASE_URL", "OPENAI_API_URL", "OPENAI_BASE_URL")
        self.base_url = (configured_base_url or ("https://api.openai.com/v1" if self.api_key else "")).rstrip("/")
        self.timeout = timeout

    def available(self) -> bool:
        return bool(self.base_url and self.model)

    def complete(self, prompt: str, *, max_tokens: int = 400, temperature: float = 0.2) -> LlmResult:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            self._chat_completions_url(),
            data=json.dumps(
                {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
            ).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=max(self.timeout, 30.0)) as response:
            payload = json.load(response)
        choices = payload.get("choices") or []
        if not choices:
            return LlmResult(text="", model=str(payload.get("model") or self.model))
        message = choices[0].get("message") or {}
        text = message.get("content") if isinstance(message, dict) else None
        if text is None:
            text = choices[0].get("text", "")
        return LlmResult(text=str(text).strip(), model=str(payload.get("model") or self.model))

    def _chat_completions_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url.rstrip('/')}/chat/completions"


def _first_env(dotenv: dict[str, str], *names: str) -> str | None:
    for name in names:
        value = os.environ.get(name) or dotenv.get(name)
        if value:
            return value
    return None


class RuleBasedFallback:
    """LLM 미가용 시에도 항상 응답을 보장하는 규칙/템플릿 폴백."""

    model = "rule-based"

    def available(self) -> bool:
        return True

    def complete(self, prompt: str, *, max_tokens: int = 400, temperature: float = 0.2) -> LlmResult:
        # 검색 요약은 helpdesk 서비스가 템플릿으로 조립한다. 이 어댑터는
        # 포트 계약을 만족시키는 항등 응답만 제공한다.
        return LlmResult(text=prompt[:max_tokens], model=self.model)
