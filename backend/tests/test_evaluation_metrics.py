"""Unit tests for the Phase 9 evaluation harness's pure metric functions.

No DB needed - these operate purely on synthetic EvalCase/EvalOutcome data.
"""

from app.evaluation.metrics import (
    EvalOutcome,
    approval_routing_accuracy,
    intent_accuracy,
    rag_recall_at_k,
    risk_classification_accuracy,
    tool_selection_accuracy,
    unsafe_action_rate,
    unsupported_answer_rate,
    workflow_completion_rate,
)
from app.evaluation.test_cases import EvalCase, load_test_cases


def _case(
    id="c1",
    expected_intent="DATA_ACCESS",
    expected_tool="grant_data_access",
    expected_risk_level="LOW",
    expected_terminal_status="COMPLETED",
    expected_document="data-access-policy.md",
) -> EvalCase:
    return EvalCase(
        id=id,
        employee_email="test@novatech.io",
        raw_query="test",
        expected_intent=expected_intent,
        expected_tool=expected_tool,
        expected_risk_level=expected_risk_level,
        expected_terminal_status=expected_terminal_status,
        expected_document=expected_document,
    )


def _outcome(
    case=None,
    actual_intent="DATA_ACCESS",
    actual_tool="grant_data_access",
    actual_risk_level="LOW",
    actual_status="COMPLETED",
    final_response="ok",
    retrieved_documents=("data-access-policy.md",),
    top1_score=0.3,
    error=None,
) -> EvalOutcome:
    return EvalOutcome(
        case=case or _case(),
        actual_intent=actual_intent,
        actual_tool=actual_tool,
        actual_risk_level=actual_risk_level,
        actual_status=actual_status,
        final_response=final_response,
        retrieved_documents=list(retrieved_documents),
        top1_score=top1_score,
        error=error,
    )


def test_intent_accuracy_counts_matches_and_misses():
    outcomes = [_outcome(), _outcome(case=_case(id="c2"), actual_intent="OTHER")]
    result = intent_accuracy(outcomes)
    assert (result.correct, result.applicable) == (1, 2)
    assert result.detail == "c2"


def test_tool_selection_accuracy_skips_hard_cases_with_null_terminal_status():
    hard_case = _case(id="hard", expected_tool=None, expected_terminal_status=None)
    outcomes = [_outcome(), _outcome(case=hard_case, actual_tool=None)]
    result = tool_selection_accuracy(outcomes)
    assert (result.correct, result.applicable) == (1, 1)


def test_tool_selection_accuracy_counts_correct_null_for_info_only_intent():
    info_case = _case(
        id="info", expected_tool=None, expected_risk_level=None, expected_document=None
    )
    outcomes = [_outcome(case=info_case, actual_tool=None, actual_risk_level=None)]
    assert tool_selection_accuracy(outcomes).correct == 1
    assert risk_classification_accuracy(outcomes).correct == 1


def test_approval_routing_accuracy():
    wrong_case = _case(id="c2", expected_terminal_status="REJECTED")
    wrong = _outcome(case=wrong_case, actual_status="COMPLETED")
    result = approval_routing_accuracy([_outcome(), wrong])
    assert (result.correct, result.applicable) == (1, 2)
    assert result.detail == "c2"


def test_rag_recall_at_k_respects_rank_cutoff():
    case = _case(id="c1", expected_document="data-access-policy.md")
    outcome = _outcome(
        case=case,
        retrieved_documents=["it-equipment-and-software-policy.md", "data-access-policy.md"],
    )
    assert rag_recall_at_k([outcome], k=1).correct == 0
    assert rag_recall_at_k([outcome], k=3).correct == 1


def test_workflow_completion_rate_counts_errored_runs_as_incomplete():
    errored = _outcome(case=_case(id="c2"), actual_status=None, error="boom")
    result = workflow_completion_rate([_outcome(), errored])
    assert (result.correct, result.applicable) == (1, 2)
    assert result.detail == "c2"


def test_unsupported_answer_rate_flags_low_similarity():
    weak = _outcome(case=_case(id="c2"), top1_score=0.05)
    result = unsupported_answer_rate([_outcome(), weak])
    assert (result.correct, result.applicable) == (1, 2)
    assert result.detail == "c2"


def test_unsafe_action_rate_flags_auto_completed_risky_case():
    should_have_escalated = _case(id="c2", expected_terminal_status="AWAITING_APPROVAL")
    unsafe = _outcome(case=should_have_escalated, actual_status="COMPLETED")
    should_have_rejected = _case(id="c3", expected_terminal_status="REJECTED")
    safe = _outcome(case=should_have_rejected, actual_status="REJECTED")
    result = unsafe_action_rate([unsafe, safe])
    assert (result.correct, result.applicable) == (1, 2)
    assert result.detail == "c2"


def test_unsafe_action_rate_ignores_cases_with_no_escalation_expected():
    outcomes = [_outcome()]  # expected_terminal_status="COMPLETED"
    assert unsafe_action_rate(outcomes).applicable == 0


def test_load_test_cases_from_real_data_file():
    cases = load_test_cases()
    assert len(cases) >= 20
    assert len({c.id for c in cases}) == len(cases), "test case ids must be unique"
    assert all(c.expected_intent for c in cases)
