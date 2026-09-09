"""LLM provider abstraction for structured request classification.

Mirrors the pattern used for embeddings (`app.rag.embeddings`): the default
`mock` mode needs no external API and no network access, so local dev,
tests, and CI never make a real LLM call. Setting `LLM_MODE=anthropic`
(with `ANTHROPIC_API_KEY` set) switches to a real Claude call using
structured outputs, so the response always validates against
`RequestClassification` the same way the mock provider's does.
"""

import re
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.models.enums import RequestIntent
from app.tools.it_ticket import ITTicketCategory

ANTHROPIC_MODEL = "claude-opus-5"

_CLASSIFICATION_SYSTEM_PROMPT = (
    "You are the request classification step of NovaTech's internal AI workflow "
    "assistant. Read the employee's request and classify it into exactly one "
    "intent category, with a confidence score and a one-sentence reason."
)

_PLANNING_SYSTEM_PROMPT = (
    "You are the tool-argument planning step of NovaTech's internal AI workflow "
    "assistant. Given an employee's request and its classified intent, extract the "
    "arguments needed to call the matching internal tool. Only include an argument "
    "if it is stated or clearly implied in the request; omit anything you're not "
    "confident about rather than guessing, since an incomplete plan is routed to a "
    "human instead of being silently wrong."
)

# Maps a tool-having RequestIntent to the mock tool it plans a call for
# (app.tools.*), and the argument shape that tool expects (see app/schemas/tool.py
# for the full request schemas - employee_id/request_id are filled in by the
# workflow, not extracted from text).
_INTENT_TOOL_NAME: dict[RequestIntent, str] = {
    RequestIntent.DATA_ACCESS: "grant_data_access",
    RequestIntent.IT_EQUIPMENT: "create_it_ticket",
    RequestIntent.IT_SOFTWARE: "create_it_ticket",
    RequestIntent.TRAVEL_BOOKING: "book_travel",
    RequestIntent.EXPENSE_REIMBURSEMENT: "submit_expense",
}
_TOOL_ARG_SCHEMAS: dict[RequestIntent, str] = {
    RequestIntent.DATA_ACCESS: (
        "resource_name (must exactly match one of the known resource names given "
        "below), duration_days (integer, optional)"
    ),
    RequestIntent.IT_EQUIPMENT: (
        "category ('EQUIPMENT_STANDARD' or 'EQUIPMENT_NON_STANDARD'), description "
        "(string), equipment_cost_usd (number, optional)"
    ),
    RequestIntent.IT_SOFTWARE: (
        "category ('SOFTWARE_PREAPPROVED' or 'SOFTWARE_NEW'), description (string)"
    ),
    RequestIntent.TRAVEL_BOOKING: (
        "destination (string), is_international (boolean), total_cost_usd (number)"
    ),
    RequestIntent.EXPENSE_REIMBURSEMENT: "amount_usd (number), description (string)",
}


class RequestClassification(BaseModel):
    intent: RequestIntent
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class ToolPlan(BaseModel):
    """A proposed tool call extracted from free text, before validation.

    `tool_name` is `None` for intents with no automatable tool (e.g. TIME_OFF).
    `arguments` is a raw dict rather than a typed schema because it must cover
    four different tool argument shapes; the workflow's `plan` node is
    responsible for validating it against the target tool's actual schema
    and treating anything incomplete as a case for human review rather than
    a hard failure.
    """

    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


class LLMProvider(Protocol):
    def classify(self, raw_query: str) -> RequestClassification: ...
    def plan(
        self, intent: RequestIntent, raw_query: str, known_resource_names: list[str]
    ) -> ToolPlan: ...


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


_STANDARD_EQUIPMENT_KEYWORDS = (
    "laptop", "monitor", "keyboard", "mouse", "headset", "dock", "webcam",
)
_PREAPPROVED_SOFTWARE_KEYWORDS = (
    "slack", "zoom", "figma", "notion", "github copilot", "vs code",
    "visual studio code", "jira", "confluence",
)
# Only a `$`-prefixed amount counts, so a bare number (like a duration or a
# ticket ID) is never mistaken for a dollar figure.
_AMOUNT_RE = re.compile(r"\$\s?([\d,]+(?:\.\d{1,2})?)")
_DURATION_RE = re.compile(r"(\d+)\s*days?\b")
_DESTINATION_RE = re.compile(r"\bto\s+([A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)*)")


class MockLLMProvider:
    """Deterministic keyword-rule classifier/planner; makes no external calls."""

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

    def plan(
        self, intent: RequestIntent, raw_query: str, known_resource_names: list[str]
    ) -> ToolPlan:
        text = raw_query.lower()

        if intent == RequestIntent.DATA_ACCESS:
            resource_name = next(
                (name for name in known_resource_names if name.lower() in text), None
            )
            arguments: dict[str, Any] = {}
            if resource_name:
                arguments["resource_name"] = resource_name
            duration_match = _DURATION_RE.search(text)
            if duration_match:
                arguments["duration_days"] = int(duration_match.group(1))
            notes = (
                "matched a known resource name by substring"
                if resource_name
                else "no known resource name found in the request text"
            )
            return ToolPlan(
                tool_name=_INTENT_TOOL_NAME[intent], arguments=arguments, notes=notes
            )

        if intent in (RequestIntent.IT_EQUIPMENT, RequestIntent.IT_SOFTWARE):
            arguments = {"description": raw_query.strip()}
            cost_match = _AMOUNT_RE.search(raw_query)
            if cost_match:
                arguments["equipment_cost_usd"] = float(cost_match.group(1).replace(",", ""))
            if intent == RequestIntent.IT_EQUIPMENT:
                category = (
                    ITTicketCategory.EQUIPMENT_STANDARD
                    if any(k in text for k in _STANDARD_EQUIPMENT_KEYWORDS)
                    else ITTicketCategory.EQUIPMENT_NON_STANDARD
                )
            else:
                category = (
                    ITTicketCategory.SOFTWARE_PREAPPROVED
                    if any(k in text for k in _PREAPPROVED_SOFTWARE_KEYWORDS)
                    else ITTicketCategory.SOFTWARE_NEW
                )
            arguments["category"] = category.value
            return ToolPlan(tool_name=_INTENT_TOOL_NAME[intent], arguments=arguments)

        if intent == RequestIntent.TRAVEL_BOOKING:
            arguments = {"is_international": "international" in text}
            cost_match = _AMOUNT_RE.search(raw_query)
            if cost_match:
                arguments["total_cost_usd"] = float(cost_match.group(1).replace(",", ""))
            destination_match = _DESTINATION_RE.search(raw_query)
            if destination_match:
                arguments["destination"] = destination_match.group(1)
            return ToolPlan(tool_name=_INTENT_TOOL_NAME[intent], arguments=arguments)

        if intent == RequestIntent.EXPENSE_REIMBURSEMENT:
            arguments = {"description": raw_query.strip()}
            cost_match = _AMOUNT_RE.search(raw_query)
            if cost_match:
                arguments["amount_usd"] = float(cost_match.group(1).replace(",", ""))
            return ToolPlan(tool_name=_INTENT_TOOL_NAME[intent], arguments=arguments)

        return ToolPlan(
            tool_name=None,
            notes=f"No automatable tool exists for intent {intent.value}.",
        )


def _build_planning_prompt(
    intent: RequestIntent, raw_query: str, known_resource_names: list[str]
) -> str:
    schema_hint = _TOOL_ARG_SCHEMAS[intent]
    resource_hint = (
        f" Known resource names: {', '.join(known_resource_names)}."
        if known_resource_names
        else ""
    )
    return (
        f"Extract the arguments needed to call the '{_INTENT_TOOL_NAME[intent]}' tool from "
        f"this employee request. Required argument shape: {schema_hint}.{resource_hint}\n\n"
        f"Request: {raw_query}"
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
        if response.parsed_output is None:
            raise RuntimeError("Anthropic response did not include a parsed structured output")
        return response.parsed_output

    def plan(
        self, intent: RequestIntent, raw_query: str, known_resource_names: list[str]
    ) -> ToolPlan:
        if intent not in _INTENT_TOOL_NAME:
            return ToolPlan(
                tool_name=None, notes=f"No automatable tool exists for intent {intent.value}."
            )

        prompt = _build_planning_prompt(intent, raw_query, known_resource_names)
        response = self._client.messages.parse(
            model=ANTHROPIC_MODEL,
            max_tokens=512,
            system=_PLANNING_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            output_format=ToolPlan,
        )
        plan = response.parsed_output
        if plan is None:
            raise RuntimeError("Anthropic response did not include a parsed structured output")
        plan.tool_name = _INTENT_TOOL_NAME[intent]
        return plan


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

    def plan(
        self, intent: RequestIntent, raw_query: str, known_resource_names: list[str]
    ) -> ToolPlan:
        if intent not in _INTENT_TOOL_NAME:
            return ToolPlan(
                tool_name=None, notes=f"No automatable tool exists for intent {intent.value}."
            )

        prompt = _build_planning_prompt(intent, raw_query, known_resource_names)
        response = self._client.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": _PLANNING_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "format": ToolPlan.model_json_schema(),
                "stream": False,
                "options": {"temperature": 0},
            },
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        plan = ToolPlan.model_validate_json(content)
        plan.tool_name = _INTENT_TOOL_NAME[intent]
        return plan


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
