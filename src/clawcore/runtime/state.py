"""Structured state models for the async runtime."""

from __future__ import annotations

from dataclasses import dataclass, field

from clawcore.models import ToolResult
from clawcore.skilling.models import SkillDefinition
from common.events import RuntimeEvent
from common.tracing import TraceCollector


@dataclass(slots=True)
class RuntimeState:
    """In-memory state for a single agent run."""

    # Original user request for the current run.
    user_input: str
    # Fully rendered system prompt assembled before the loop starts.
    system_prompt: str = ""
    # Skill currently selected for this run, if any.
    active_skill: SkillDefinition | None = None
    # Rolling text observations that are fed back into the ReAct loop for later reasoning.
    scratchpad: list[str] = field(default_factory=list)
    # Structured results returned by executed tools.
    tool_results: list[ToolResult] = field(default_factory=list)
    # Lifecycle and tool events recorded for tracing, hooks, and debugging rather than model reasoning.
    events: list[RuntimeEvent] = field(default_factory=list)
    # Ordered trace collector for debugging and observability.
    trace: TraceCollector = field(default_factory=TraceCollector)
