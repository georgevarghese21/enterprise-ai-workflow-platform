"""Provider-dispatch and Ollama-provider tests.

These never talk to a real Ollama server: `OllamaLLMProvider.__init__` is
bypassed (constructing the client makes no network call, but there's no
need to even do that) and its HTTP client is replaced with a fake, so this
suite stays fast and deterministic without requiring Ollama to be running.
"""

import app.services.llm_provider as llm_provider_module
from app.core.config import Settings
from app.models.enums import RequestIntent
from app.services.llm_provider import (
    AnthropicLLMProvider,
    MockLLMProvider,
    OllamaLLMProvider,
    RequestClassification,
    get_llm_provider,
)


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


class _FakeHttpxClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, json: dict) -> _FakeResponse:
        self.calls.append((url, json))
        expected = RequestClassification(
            intent=RequestIntent.IT_EQUIPMENT,
            confidence=0.9,
            reasoning="Employee asked for a laptop.",
        )
        return _FakeResponse({"message": {"content": expected.model_dump_json()}})


def test_ollama_provider_parses_structured_response():
    provider = OllamaLLMProvider.__new__(OllamaLLMProvider)
    provider._base_url = "http://localhost:11434"
    provider._model = "llama3.2"
    fake_client = _FakeHttpxClient()
    provider._client = fake_client

    result = provider.classify("I need a new laptop")

    assert result.intent == RequestIntent.IT_EQUIPMENT
    assert result.confidence == 0.9

    url, payload = fake_client.calls[0]
    assert url == "http://localhost:11434/api/chat"
    assert payload["model"] == "llama3.2"
    assert payload["format"] == RequestClassification.model_json_schema()
    assert payload["messages"][-1] == {"role": "user", "content": "I need a new laptop"}


def test_get_llm_provider_dispatches_by_mode(monkeypatch):
    monkeypatch.setattr(llm_provider_module, "get_settings", lambda: Settings(llm_mode="mock"))
    assert isinstance(get_llm_provider(), MockLLMProvider)

    monkeypatch.setattr(llm_provider_module, "get_settings", lambda: Settings(llm_mode="ollama"))
    assert isinstance(get_llm_provider(), OllamaLLMProvider)

    # AnthropicLLMProvider's __init__ constructs a real anthropic.Anthropic()
    # client, which requires a credential to be present just to construct
    # (no network call happens here) - set a dummy key for that alone.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-for-construction-only")
    monkeypatch.setattr(
        llm_provider_module, "get_settings", lambda: Settings(llm_mode="anthropic")
    )
    assert isinstance(get_llm_provider(), AnthropicLLMProvider)


def test_get_llm_provider_rejects_unknown_mode(monkeypatch):
    import pytest

    monkeypatch.setattr(llm_provider_module, "get_settings", lambda: Settings(llm_mode="bogus"))
    with pytest.raises(NotImplementedError):
        get_llm_provider()
