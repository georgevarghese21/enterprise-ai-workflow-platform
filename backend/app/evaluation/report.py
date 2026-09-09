"""Formats Phase 9 evaluation results for a human (stdout) and for a saved
JSON artifact other tooling (or a future dashboard) could read.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from app.evaluation.metrics import MetricResult

# Same path convention as app.evaluation.test_cases / app.core.config.
_DEFAULT_RESULTS_PATH = Path(__file__).resolve().parents[3] / "data" / "evaluation" / "results.json"


def format_report(metrics: list[MetricResult]) -> str:
    lines = ["Evaluation results", "=" * 60]
    for m in metrics:
        pct = f"{m.percentage:.0f}%" if m.percentage is not None else "n/a"
        lines.append(f"{m.name:<32} {m.correct:>3}/{m.applicable:<3} ({pct})")
        if m.detail:
            lines.append(f"{'':<32} misses: {m.detail}")
    return "\n".join(lines)


def write_json_report(metrics: list[MetricResult], path: Path | None = None) -> Path:
    target = path or _DEFAULT_RESULTS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "metrics": [
            {
                "name": m.name,
                "correct": m.correct,
                "applicable": m.applicable,
                "percentage": m.percentage,
                "misses": m.detail.split(", ") if m.detail else [],
            }
            for m in metrics
        ],
    }
    target.write_text(json.dumps(payload, indent=2) + "\n")
    return target
