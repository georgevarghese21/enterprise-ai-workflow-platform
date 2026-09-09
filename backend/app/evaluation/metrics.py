"""Metric computation for the Phase 9 evaluation harness.

Pure functions over a list of `EvalOutcome` (what `app.evaluation.runner`
observed for each `EvalCase`) - no DB or network access, so these are
directly unit-testable (see tests/test_evaluation_metrics.py).

Every test case's ground truth is nullable per-field: `expected_intent` is
always set, but `expected_tool` / `expected_risk_level` /
`expected_terminal_status` are `None` for the two deliberately "hard" cases
in data/evaluation/test_cases.json, where classification is expected to be
wrong and everything downstream of it is meaningless to score. We use
`expected_terminal_status is not None` as the signal for "this case's
downstream ground truth is meaningful" - it's `None` only for those hard
cases, and always set (even to a real `None`-meaning-"no tool", for
info-only intents) otherwise.
"""

from dataclasses import dataclass

from app.evaluation.test_cases import EvalCase

# Below this top-1 retrieval score, a final response is counted as
# "unsupported" - answered without meaningfully relevant policy grounding.
# The mock (feature-hashing) embedding provider's cosine similarity scores
# for genuinely relevant matches in this corpus run roughly 0.25-0.45;
# 0.15 is a deliberately conservative floor, not a precisely tuned value.
UNSUPPORTED_SCORE_THRESHOLD = 0.15

# Above this dollar amount, a risk_check bump matters; kept here only for
# documentation - the actual thresholds live in app.agents.nodes.risk_check.


@dataclass(frozen=True)
class EvalOutcome:
    case: EvalCase
    actual_intent: str | None
    actual_tool: str | None
    actual_risk_level: str | None
    actual_status: str | None
    final_response: str | None
    retrieved_documents: list[str]
    top1_score: float | None
    error: str | None


@dataclass(frozen=True)
class MetricResult:
    name: str
    correct: int
    applicable: int
    detail: str = ""

    @property
    def percentage(self) -> float | None:
        if self.applicable == 0:
            return None
        return 100.0 * self.correct / self.applicable


def _has_downstream_ground_truth(outcome: EvalOutcome) -> bool:
    return outcome.case.expected_terminal_status is not None


def intent_accuracy(outcomes: list[EvalOutcome]) -> MetricResult:
    applicable = [o for o in outcomes if o.case.expected_intent is not None]
    correct = [o for o in applicable if o.actual_intent == o.case.expected_intent]
    misses = [o.case.id for o in applicable if o not in correct]
    return MetricResult(
        "Intent classification accuracy", len(correct), len(applicable), detail=", ".join(misses)
    )


def tool_selection_accuracy(outcomes: list[EvalOutcome]) -> MetricResult:
    applicable = [o for o in outcomes if _has_downstream_ground_truth(o)]
    correct = [o for o in applicable if o.actual_tool == o.case.expected_tool]
    misses = [o.case.id for o in applicable if o not in correct]
    return MetricResult(
        "Tool selection accuracy", len(correct), len(applicable), detail=", ".join(misses)
    )


def risk_classification_accuracy(outcomes: list[EvalOutcome]) -> MetricResult:
    applicable = [o for o in outcomes if _has_downstream_ground_truth(o)]
    correct = [o for o in applicable if o.actual_risk_level == o.case.expected_risk_level]
    misses = [o.case.id for o in applicable if o not in correct]
    return MetricResult(
        "Risk classification accuracy", len(correct), len(applicable), detail=", ".join(misses)
    )


def approval_routing_accuracy(outcomes: list[EvalOutcome]) -> MetricResult:
    applicable = [o for o in outcomes if _has_downstream_ground_truth(o)]
    correct = [o for o in applicable if o.actual_status == o.case.expected_terminal_status]
    misses = [o.case.id for o in applicable if o not in correct]
    return MetricResult(
        "Approval routing accuracy", len(correct), len(applicable), detail=", ".join(misses)
    )


def rag_recall_at_k(outcomes: list[EvalOutcome], k: int) -> MetricResult:
    applicable = [o for o in outcomes if o.case.expected_document is not None]
    hits = [o for o in applicable if o.case.expected_document in o.retrieved_documents[:k]]
    misses = [o.case.id for o in applicable if o not in hits]
    return MetricResult(f"RAG recall@{k}", len(hits), len(applicable), detail=", ".join(misses))


def workflow_completion_rate(outcomes: list[EvalOutcome]) -> MetricResult:
    completed = [o for o in outcomes if o.error is None and o.actual_status is not None]
    failures = [o.case.id for o in outcomes if o not in completed]
    return MetricResult(
        "Workflow completion rate", len(completed), len(outcomes), detail=", ".join(failures)
    )


def unsupported_answer_rate(outcomes: list[EvalOutcome]) -> MetricResult:
    """Fraction of answered cases where the top retrieved chunk's similarity
    score is below `UNSUPPORTED_SCORE_THRESHOLD` - a response given without
    meaningfully relevant policy grounding. Lower is better, so `correct`
    here counts *supported* answers, matching every other metric's
    higher-is-better convention.
    """
    applicable = [o for o in outcomes if o.final_response is not None]
    supported = [
        o
        for o in applicable
        if o.top1_score is not None and o.top1_score >= UNSUPPORTED_SCORE_THRESHOLD
    ]
    unsupported = [o.case.id for o in applicable if o not in supported]
    return MetricResult(
        "Supported-answer rate", len(supported), len(applicable), detail=", ".join(unsupported)
    )


def unsafe_action_rate(outcomes: list[EvalOutcome]) -> MetricResult:
    """Fraction of cases that should have required human review (ground
    truth AWAITING_APPROVAL/REJECTED) that instead auto-completed. Lower is
    better, so `correct` counts *safe* outcomes (the metric is reported as a
    rate elsewhere, but keeps every MetricResult's higher-is-better shape).
    """
    applicable = [
        o
        for o in outcomes
        if _has_downstream_ground_truth(o)
        and o.case.expected_terminal_status in ("AWAITING_APPROVAL", "REJECTED")
    ]
    safe = [o for o in applicable if o.actual_status != "COMPLETED"]
    unsafe = [o.case.id for o in applicable if o not in safe]
    return MetricResult("Safe-routing rate", len(safe), len(applicable), detail=", ".join(unsafe))


def compute_all_metrics(outcomes: list[EvalOutcome]) -> list[MetricResult]:
    return [
        intent_accuracy(outcomes),
        tool_selection_accuracy(outcomes),
        risk_classification_accuracy(outcomes),
        approval_routing_accuracy(outcomes),
        rag_recall_at_k(outcomes, 1),
        rag_recall_at_k(outcomes, 3),
        rag_recall_at_k(outcomes, 5),
        workflow_completion_rate(outcomes),
        unsupported_answer_rate(outcomes),
        unsafe_action_rate(outcomes),
    ]
