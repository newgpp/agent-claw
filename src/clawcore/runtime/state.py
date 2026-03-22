"""Structured state models for the async runtime."""

from __future__ import annotations

from dataclasses import dataclass, field

from clawcore.models import ExecutionPlan, PlanArtifact, RuntimeTokenUsage, ToolResult
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
    # Compact observations that are safe to feed back into the executor prompt.
    prompt_observations: list[str] = field(default_factory=list)
    # Short summaries of completed steps used as cross-step handoff context.
    step_summaries: list[str] = field(default_factory=list)
    # Structured results returned by executed tools.
    tool_results: list[ToolResult] = field(default_factory=list)
    # Structured execution plan for planned runs, if one exists.
    plan: ExecutionPlan | None = None
    # Active subgoal identifier for planned runs.
    active_subgoal_id: str | None = None
    # Active subgoal task text for planned runs.
    active_subgoal_task: str | None = None
    # Active subgoal execution notes for planned runs.
    active_subgoal_notes: str | None = None
    # Structured artifacts produced while working through a plan.
    artifacts: list[PlanArtifact] = field(default_factory=list)
    # Small file bodies cached from prior write calls for later subgoals.
    cached_files: dict[str, str] = field(default_factory=dict)
    # Number of times the runtime has replanned during this run.
    replanning_count: int = 0
    # Aggregate token usage across planner and executor LLM calls.
    token_usage: RuntimeTokenUsage = field(default_factory=RuntimeTokenUsage)
    # Compact state intentionally shaped for executor prompt construction.
    prompt_state: dict[str, object] = field(default_factory=dict)
    # Raw debug-oriented state kept for inspection and API debug responses.
    debug_state: dict[str, object] = field(default_factory=dict)
    # Lifecycle and tool events recorded for tracing, hooks, and debugging rather than model reasoning.
    events: list[RuntimeEvent] = field(default_factory=list)
    # Ordered trace collector for debugging and observability.
    trace: TraceCollector = field(default_factory=TraceCollector)

    def __post_init__(self) -> None:
        self.sync_views()

    def sync_views(self) -> None:
        """Refresh prompt-visible and debug-visible state snapshots."""
        self.prompt_state = {
            "user_input": self.user_input,
            "active_skill": self.active_skill.name if self.active_skill is not None else None,
            "loaded_skills": [skill.name for skill in self.loaded_skills],
            "step_summaries": list(self.step_summaries),
            "observations": list(self.prompt_observations),
            "plan": self._serialize_plan_for_prompt(),
            "active_subgoal_id": self.active_subgoal_id,
            "active_subgoal_task": self.active_subgoal_task,
            "active_subgoal_notes": self.active_subgoal_notes,
            "artifacts": [
                {"name": artifact.name, "kind": artifact.kind, "summary": self._summarize_text(artifact.content)}
                for artifact in self.artifacts
            ],
        }
        self.debug_state = {
            "scratchpad": list(self.scratchpad),
            "tool_results": [{"name": item.name, "content": item.content} for item in self.tool_results],
            "cached_files": {
                path: self._summarize_text(content, limit=800) for path, content in self.cached_files.items()
            },
            "events": [event.to_dict() for event in self.events],
            "trace": [entry.to_dict() for entry in self.trace.events],
        }

    def build_executor_context(self) -> dict[str, object]:
        """Build the compact context passed to the executor LLM."""
        context: dict[str, object] = {
            "user_request": {"raw_input": self.user_input},
            "runtime": {
                "active_skill": self.active_skill.name if self.active_skill is not None else None,
                "loaded_skills": [skill.name for skill in self.loaded_skills],
                "step_summaries": list(self.step_summaries),
                "observations": list(self.prompt_observations),
                "artifacts": [
                    {
                        "name": artifact.name,
                        "kind": artifact.kind,
                        "summary": self._summarize_text(artifact.content),
                    }
                    for artifact in self.artifacts
                ],
                "file_cache": [
                    {
                        "path": path,
                        "content": self._executor_file_content(content),
                    }
                    for path, content in self.cached_files.items()
                ],
            },
        }
        if self.plan is None:
            return context

        completed_subgoal_ids = [subgoal.id for subgoal in self.plan.subgoals if subgoal.status.value == "completed"]
        remaining_subgoal_ids = [
            subgoal.id
            for subgoal in self.plan.subgoals
            if subgoal.id != self.active_subgoal_id and subgoal.status.value != "completed"
        ]
        context["execution"] = {
            "active_subgoal": {
                "id": self.active_subgoal_id,
                "task": self.active_subgoal_task,
                "notes": self.active_subgoal_notes,
            },
            "rules": [
                "Only execute the active subgoal.",
                "Use the user request as background constraints, not as permission to expand scope.",
                "Do not start later subgoals, even if you can infer them.",
                "When the active subgoal is satisfied, return final_answer immediately.",
            ],
        }
        context["plan_summary"] = {
            "goal": self.plan.goal,
            "status": self.plan.status,
            "completed_subgoal_ids": completed_subgoal_ids,
            "remaining_subgoal_ids": remaining_subgoal_ids,
            "success_criteria": list(self.plan.success_criteria),
            "assumptions": list(self.plan.assumptions),
        }
        return context

    def _serialize_plan_for_prompt(self) -> dict[str, object] | None:
        if self.plan is None:
            return None
        return {
            "goal": self.plan.goal,
            "status": self.plan.status,
            "subgoals": [
                {
                    "id": subgoal.id,
                    "task": subgoal.task,
                    "status": subgoal.status,
                    "notes": subgoal.notes,
                }
                for subgoal in self.plan.subgoals
            ],
            "success_criteria": list(self.plan.success_criteria),
            "assumptions": list(self.plan.assumptions),
        }

    def _summarize_text(self, value: str, *, limit: int = 240) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 3] + "..."

    def _executor_file_content(self, value: str, *, limit: int = 1600) -> str:
        if len(value) <= limit:
            return value
        return value[: limit - 3] + "..."
