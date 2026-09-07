from dataclasses import dataclass, field
from typing import Any

from app.models.enums import ToolExecutionStatus


@dataclass(frozen=True)
class ToolResult:
    """The outcome of a single mock tool call, before it's persisted.

    Kept separate from the `ToolExecution` DB model so the tool functions
    stay pure (no DB session needed) and are trivial to unit test.
    """

    status: ToolExecutionStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)
