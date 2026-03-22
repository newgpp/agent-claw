"""Structured state models for the async runtime."""

from __future__ import annotations

from dataclasses import dataclass, field

from clawcore.models import ExecutionPlan, PlanArtifact, ToolResult
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
    # Skills exposed to the runtime as candidates for on-demand loading.
    available_skills: tuple[SkillDefinition, ...] = ()
    # Skills that have already been loaded during this run.
    loaded_skills: list[SkillDefinition] = field(default_factory=list)
    # Skill currently selected for this run, if any.
    active_skill: SkillDefinition | None = None
    # Rolling text observations that are fed back into the ReAct loop for later reasoning.
    scratchpad: list[str] = field(default_factory=list)
    # Structured results returned by executed tools.
    tool_results: list[ToolResult] = field(default_factory=list)
    # Structured execution plan for planned runs, if one exists.
    plan: ExecutionPlan | None = None
    # Active subgoal identifier for planned runs.
    active_subgoal_id: str | None = None
    # Structured artifacts produced while working through a plan.
    artifacts: list[PlanArtifact] = field(default_factory=list)
    # Number of times the runtime has replanned during this run.
    replanning_count: int = 0
    # Lifecycle and tool events recorded for tracing, hooks, and debugging rather than model reasoning.
    events: list[RuntimeEvent] = field(default_factory=list)
    # Ordered trace collector for debugging and observability.
    trace: TraceCollector = field(default_factory=TraceCollector)
