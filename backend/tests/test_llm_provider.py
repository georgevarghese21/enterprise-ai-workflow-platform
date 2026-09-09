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
    CascadeLLMProvider,
    GroqLLMProvider,
    MockLLMProvider,
    OllamaLLMProvider,
    RequestClassification,
    ToolPlan,
    get_llm_provider,
)


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

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


class _FakeGroqHttpxClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, json: dict) -> _FakeResponse:
        self.calls.append((url, json))
        expected = RequestClassification(
            intent=RequestIntent.IT_EQUIPMENT,
            confidence=0.9,
            reasoning="Employee asked for a laptop.",
        )
        return _FakeResponse(
            {"choices": [{"message": {"content": expected.model_dump_json()}}]}
        )


def test_groq_provider_parses_structured_response():
    provider = GroqLLMProvider.__new__(GroqLLMProvider)
    fake_client = _FakeGroqHttpxClient()
    provider._client = fake_client

    result = provider.classify("I need a new laptop")

    assert result.intent == RequestIntent.IT_EQUIPMENT
    assert result.confidence == 0.9

    url, payload = fake_client.calls[0]
    assert url == "/chat/completions"
    assert payload["model"] == llm_provider_module.GROQ_MODEL
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["messages"][-1] == {"role": "user", "content": "I need a new laptop"}


class _FakeRateLimitedGroqClient:
    """Returns 429 for the first `fail_times` calls, then succeeds."""

    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    def post(self, url: str, json: dict) -> _FakeResponse:
        self.calls += 1
        if self.calls <= self.fail_times:
            return _FakeResponse({}, status_code=429)
        expected = RequestClassification(
            intent=RequestIntent.OTHER, confidence=0.5, reasoning="test"
        )
        return _FakeResponse(
            {"choices": [{"message": {"content": expected.model_dump_json()}}]}
        )


def test_groq_provider_retries_on_rate_limit(monkeypatch):
    monkeypatch.setattr(llm_provider_module.time, "sleep", lambda _seconds: None)
    provider = GroqLLMProvider.__new__(GroqLLMProvider)
    fake_client = _FakeRateLimitedGroqClient(fail_times=2)
    provider._client = fake_client

    result = provider.classify("anything")

    assert result.intent == RequestIntent.OTHER
    assert fake_client.calls == 3


def test_groq_provider_raises_after_exhausting_retries(monkeypatch):
    import pytest

    monkeypatch.setattr(llm_provider_module.time, "sleep", lambda _seconds: None)
    provider = GroqLLMProvider.__new__(GroqLLMProvider)
    provider._client = _FakeRateLimitedGroqClient(fail_times=10)

    with pytest.raises(Exception):  # noqa: B017 - real code raises via raise_for_status
        provider.classify("anything")


def test_groq_provider_requires_api_key(monkeypatch):
    import pytest

    monkeypatch.setattr(
        llm_provider_module, "get_settings", lambda: Settings(llm_mode="groq", groq_api_key=None)
    )
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        GroqLLMProvider()


class _FakeFallbackProvider:
    provider_name = "fake-fallback"

    def __init__(self) -> None:
        self.classify_calls = 0
        self.plan_calls = 0

    def classify(self, raw_query: str) -> RequestClassification:
        self.classify_calls += 1
        return RequestClassification(
            intent=RequestIntent.SECURITY_INCIDENT, confidence=0.99, reasoning="fallback"
        )

    def plan(
        self, intent: RequestIntent, raw_query: str, known_resource_names: list[str]
    ) -> ToolPlan:
        self.plan_calls += 1
        return ToolPlan(tool_name=None, notes="fallback plan")


def test_cascade_uses_mock_when_confident():
    """A query with 2+ keyword hits (e.g. 'access to' + 'database') scores
    >= 0.8 from the mock - confident enough that cascade shouldn't bother
    calling the fallback provider at all.
    """
    fallback = _FakeFallbackProvider()
    provider = CascadeLLMProvider(fallback=fallback)

    result = provider.classify("I need access to the analytics-db database")

    assert result.intent == RequestIntent.DATA_ACCESS
    assert fallback.classify_calls == 0
    assert provider.provider_name == "mock"


def test_cascade_escalates_to_fallback_when_unconfident():
    """'I lost my laptop' is the known hard case: the mock scores it 0.65
    (a single keyword hit), below the cascade threshold - this should
    escalate to the fallback provider instead of trusting the mock's
    (wrong, in this specific case) guess.
    """
    fallback = _FakeFallbackProvider()
    provider = CascadeLLMProvider(fallback=fallback)

    result = provider.classify("I lost my laptop, what should I do?")
    assert provider.provider_name == "fake-fallback"

    assert result.intent == RequestIntent.SECURITY_INCIDENT
    assert fallback.classify_calls == 1


def test_cascade_plan_uses_whichever_provider_classified():
    fallback = _FakeFallbackProvider()
    provider = CascadeLLMProvider(fallback=fallback)

    provider.classify("I lost my laptop, what should I do?")  # escalates
    provider.plan(RequestIntent.SECURITY_INCIDENT, "I lost my laptop", [])
    assert fallback.plan_calls == 1

    provider.classify("I need access to the analytics-db database")  # stays on mock
    provider.plan(RequestIntent.DATA_ACCESS, "I need access to the analytics-db database", [])
    assert fallback.plan_calls == 1  # unchanged - this plan() went to the mock


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

    monkeypatch.setattr(
        llm_provider_module,
        "get_settings",
        lambda: Settings(llm_mode="groq", groq_api_key="test-key"),
    )
    assert isinstance(get_llm_provider(), GroqLLMProvider)

    monkeypatch.setattr(
        llm_provider_module,
        "get_settings",
        lambda: Settings(llm_mode="cascade", groq_api_key="test-key"),
    )
    assert isinstance(get_llm_provider(), CascadeLLMProvider)


def test_get_llm_provider_rejects_unknown_mode(monkeypatch):
    import pytest

    monkeypatch.setattr(llm_provider_module, "get_settings", lambda: Settings(llm_mode="bogus"))
    with pytest.raises(NotImplementedError):
        get_llm_provider()
