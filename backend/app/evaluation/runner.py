"""Phase 9 evaluation harness.

Runs the hand-written test set (`data/evaluation/test_cases.json`) through
the real workflow (`app.workflows.graph.run_request_workflow`) against a
real database, and reports the metrics defined in `app.evaluation.metrics`.

Run with `python -m app.evaluation.runner` against a seeded database (the
Compose dev database, or any `DATABASE_URL` with the standard seed data
loaded - see `app.db.seed`). Each case creates a real `Request` row and
goes through the exact same code path a live request submitted through the
API or web UI would - nothing here is a simulation, beyond whatever
`LLM_MODE=mock` already is.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.evaluation import report
from app.evaluation.metrics import EvalOutcome, compute_all_metrics
from app.evaluation.test_cases import EvalCase, load_test_cases
from app.models.employee import Employee
from app.models.request import Request
from app.rag.retrieve import search_policy_chunks
from app.workflows.graph import apply_run_result, run_request_workflow

logger = logging.getLogger(__name__)

# RAG recall is a retrieval-quality metric independent of what the live
# workflow happens to consume downstream (it hardcodes top_k=3), so it's
# measured with its own direct call at a higher top_k, decoupled from
# whatever the workflow's own retrieval step returns.
_RAG_EVAL_TOP_K = 5


def _run_case(db: Session, case: EvalCase) -> EvalOutcome:
    employee = db.scalar(select(Employee).where(Employee.email == case.employee_email))
    if employee is None:
        raise RuntimeError(
            f"Test case {case.id!r} references unknown employee {case.employee_email!r} - "
            "is the database seeded? (python -m app.db.seed)"
        )

    request = Request(employee_id=employee.id, raw_query=case.raw_query)
    db.add(request)
    db.commit()
    db.refresh(request)

    retrieved = search_policy_chunks(db, case.raw_query, top_k=_RAG_EVAL_TOP_K)
    retrieved_documents = [r.chunk.document_name for r in retrieved]
    top1_score = retrieved[0].score if retrieved else None

    try:
        final_state = run_request_workflow(db, request)
    except Exception as exc:  # noqa: BLE001 - any node failure is a real eval outcome to report
        return EvalOutcome(
            case=case,
            actual_intent=None,
            actual_tool=None,
            actual_risk_level=None,
            actual_status=None,
            final_response=None,
            retrieved_documents=retrieved_documents,
            top1_score=top1_score,
            error=str(exc),
        )

    apply_run_result(request, final_state)
    db.commit()

    intent = final_state.get("intent")
    risk_level = final_state.get("risk_level")
    return EvalOutcome(
        case=case,
        actual_intent=intent.value if intent else None,
        actual_tool=final_state.get("plan_tool_name"),
        actual_risk_level=risk_level.value if risk_level else None,
        actual_status=final_state["status"].value,
        final_response=final_state.get("final_response"),
        retrieved_documents=retrieved_documents,
        top1_score=top1_score,
        error=None,
    )


def run_evaluation() -> list[EvalOutcome]:
    cases = load_test_cases()
    with SessionLocal() as db:
        return [_run_case(db, case) for case in cases]


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    outcomes = run_evaluation()
    metrics = compute_all_metrics(outcomes)
    print(report.format_report(metrics))
    path = report.write_json_report(metrics)
    logger.info("Wrote results to %s", path)


if __name__ == "__main__":
    main()
