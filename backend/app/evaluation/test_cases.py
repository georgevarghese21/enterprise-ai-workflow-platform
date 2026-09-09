"""Loads the hand-written evaluation test set.

Mirrors `app.core.config._DEFAULT_POLICIES_DIR`'s path trick: resolved from
this file's location (not cwd), `parents[3]` is the directory containing
`data/` whether running from the repo root, from `backend/`, or inside
Docker (where docker-compose mounts the repo's `data/` dir at container
path `/data`, which lands here too).
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DEFAULT_TEST_CASES_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "evaluation" / "test_cases.json"
)


@dataclass(frozen=True)
class EvalCase:
    """One hand-written test case with ground truth.

    Every `expected_*` field is nullable. `expected_intent` is always set;
    the rest are `None` either because they're genuinely inapplicable (e.g.
    `expected_tool` for an info-only intent with no matching mock tool) or,
    for the two deliberately "hard" cases, because classification itself is
    expected to be wrong and scoring anything downstream of it would be
    meaningless - see the module docstring in `app.evaluation.metrics`.
    """

    id: str
    employee_email: str
    raw_query: str
    expected_intent: str | None
    expected_tool: str | None
    expected_risk_level: str | None
    expected_terminal_status: str | None
    expected_document: str | None
    notes: str = ""


def load_test_cases(path: Path | None = None) -> list[EvalCase]:
    target = path or _DEFAULT_TEST_CASES_PATH
    raw: list[dict[str, Any]] = json.loads(target.read_text())
    return [EvalCase(**item) for item in raw]
