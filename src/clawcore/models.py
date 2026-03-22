"""Core models for thoughts, actions, and runtime state."""

from __future__ import annotations

from enum import StrEnum
from dataclasses import dataclass, field


@dataclass(slots=True)
class ToolCall:
    """A normalized tool invocation emitted by the planner."""

    name: str
    payload: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ToolResult:
    """Structured tool output returned to the runtime."""

    name: str
    content: str


@dataclass(slots=True)
class TokenUsage:
    """Token usage for one or more LLM calls."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: "TokenUsage") -> None:
        """Accumulate another usage record into this instance."""
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens


@dataclass(slots=True)
class RuntimeTokenUsage:
    """Aggregate token usage across planner and executor calls."""

    planner: TokenUsage = field(default_factory=TokenUsage)
    executor: TokenUsage = field(default_factory=TokenUsage)

    @property
    def total(self) -> TokenUsage:
        return TokenUsage(
            prompt_tokens=self.planner.prompt_tokens + self.executor.prompt_tokens,
            completion_tokens=self.planner.completion_tokens + self.executor.completion_tokens,
            total_tokens=self.planner.total_tokens + self.executor.total_tokens,
        )


class PlanStatus(StrEnum):
    """Lifecycle status for a task plan."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(slots=True)
class PlanSubgoal:
    """A structured subgoal inside a task plan."""

    id: str
    task: str
    status: PlanStatus = PlanStatus.PENDING
    notes: str = ""


@dataclass(slots=True)
class PlanArtifact:
    """A named artifact produced while executing a plan."""

    name: str
    content: str
    kind: str = "text"


@dataclass(slots=True)
class ExecutionPlan:
    """Structured plan for planned execution."""

    goal: str
    subgoals: list[PlanSubgoal] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    status: PlanStatus = PlanStatus.PENDING

    @property
    def is_direct_answer(self) -> bool:
        """Return True when the planner can answer without entering the execution loop."""
        return not self.subgoals

    @property
    def is_single_step(self) -> bool:
        """Return True when the plan contains exactly one executable subgoal."""
        return len(self.subgoals) == 1


@dataclass(slots=True)
class ReActStep:
    """One planner step in the ReAct loop."""

    thought: str
    action: ToolCall | None = None
    final_answer: str | None = None
