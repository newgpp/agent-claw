"""Shared runtime context models."""

from __future__ import annotations

from dataclasses import dataclass, field

from common.events import RuntimeEvent
from common.observability import new_run_id, new_session_id, new_trace_id
from common.tracing import TraceCollector


@dataclass(slots=True)
class RunContext:
    """A lightweight execution context for one agent run."""

    user_input: str
    run_id: str = field(default_factory=new_run_id)
    session_id: str = field(default_factory=new_session_id)
    trace_id: str = field(default_factory=new_trace_id)
    metadata: dict[str, object] = field(default_factory=dict)
    trace: TraceCollector = field(default_factory=TraceCollector)
    events: list[RuntimeEvent] = field(default_factory=list)

    def emit(self, event: RuntimeEvent) -> None:
        """Record a runtime event inside the current run context."""
        self.events.append(event)
