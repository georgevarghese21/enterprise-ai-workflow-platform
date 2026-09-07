"""LLM provider abstraction for structured request classification.

Mirrors the pattern used for embeddings (`app.rag.embeddings`): the default
`mock` mode needs no external API and no network access, so local dev,
tests, and CI never make a real LLM call. Setting `LLM_MODE=anthropic`
(with `ANTHROPIC_API_KEY` set) switches to a real Claude call using
structured outputs, so the response always validates against
`RequestClassification` the same way the mock provider's does.
"""

from typing import Protocol

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.models.enums import RequestIntent

ANTHROPIC_MODEL = "claude-opus-5"

_CLASSIFICATION_SYSTEM_PROMPT = (
    "You are the request classification step of NovaTech's internal AI workflow "
    "assistant. Read the employee's request and classify it into exactly one "
    "intent category, with a confidence score and a one-sentence reason."
)


class RequestClassification(BaseModel):
    intent: RequestIntent
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class LLMProvider(Protocol):
    def classify(self, raw_query: str) -> RequestClassification: ...


# Keyword sets for the deterministic mock classifier below. Not meant to be
# an accurate NLU model - just enough signal, with no external calls, to
# exercise the classification -> policy-retrieval -> tool pipeline in dev,
# tests, and CI the same way a real LLM response would.
_INTENT_KEYWORDS: dict[RequestIntent, tuple[str, ...]] = {
    RequestIntent.DATA_ACCESS: (
        "database", "repo", "repository", "access to", "aws", "cloud account",
        "production", "github", "credentials",
    ),
    RequestIntent.IT_EQUIPMENT: (
        "laptop", "monitor", "hardware", "device", "peripheral", "keyboard", "mouse",
    ),
    RequestIntent.IT_SOFTWARE: (
        "software", "license", "install", "application", "tool access",
    ),
    RequestIntent.TRAVEL_BOOKING: (
        "flight", "hotel", "travel", "trip", "book a", "conference",
    ),
    RequestIntent.EXPENSE_REIMBURSEMENT: (
        "expense", "reimburse", "receipt", "reimbursement",
    ),
    RequestIntent.TIME_OFF: (
        "pto", "time off", "vacation", "leave", "day off",
    ),
    RequestIntent.REMOTE_WORK: (
        "remote", "work from home", "wfh",
    ),
    RequestIntent.SECURITY_INCIDENT: (
        "phishing", "hacked", "incident", "lost my laptop", "stolen", "suspicious", "breach",
    ),
}


class MockLLMProvider:
    """Deterministic keyword-rule classifier; makes no external calls."""

    def classify(self, raw_query: str) -> RequestClassification:
        text = raw_query.lower()
        best_intent = RequestIntent.OTHER
        best_hits = 0
        for intent, keywords in _INTENT_KEYWORDS.items():
            hits = sum(1 for keyword in keywords if keyword in text)
            if hits > best_hits:
                best_intent = intent
                best_hits = hits

        if best_hits == 0:
            return RequestClassification(
                intent=RequestIntent.OTHER,
                confidence=0.3,
                reasoning="No keyword from any known intent category matched the request.",
            )

        confidence = min(0.5 + 0.15 * best_hits, 0.95)
        return RequestClassification(
            intent=best_intent,
            confidence=confidence,
            reasoning=f"Matched {best_hits} keyword(s) associated with {best_intent.value}.",
        )


class AnthropicLLMProvider:
    """Real classifier backed by the Claude API, using structured outputs."""

    def __init__(self) -> None:
        import anthropic

        self._client = anthropic.Anthropic()

    def classify(self, raw_query: str) -> RequestClassification:
        response = self._client.messages.parse(
            model=ANTHROPIC_MODEL,
            max_tokens=256,
            system=_CLASSIFICATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": raw_query}],
            output_format=RequestClassification,
        )
        return response.parsed_output


class OllamaLLMProvider:
    """Real classifier backed by a local Ollama server.

    Genuinely free: Ollama runs the model on your own machine, no API key
    or billing involved. Uses Ollama's structured-output support (the
    `format` field accepts a JSON schema) so the response always validates
    against `RequestClassification`, the same as the other providers.
    """

    def __init__(self) -> None:
        import httpx

        settings = get_settings()
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model
        self._client = httpx.Client(timeout=httpx.Timeout(60.0))

    def classify(self, raw_query: str) -> RequestClassification:
        response = self._client.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": _CLASSIFICATION_SYSTEM_PROMPT},
                    {"role": "user", "content": raw_query},
                ],
                "format": RequestClassification.model_json_schema(),
                "stream": False,
                "options": {"temperature": 0},
            },
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        return RequestClassification.model_validate_json(content)


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_mode == "mock":
        return MockLLMProvider()
    if settings.llm_mode == "anthropic":
        return AnthropicLLMProvider()
    if settings.llm_mode == "ollama":
        return OllamaLLMProvider()
    raise NotImplementedError(
        f"LLM mode {settings.llm_mode!r} is not implemented yet; "
        "use 'mock', 'anthropic', or 'ollama'."
    )
