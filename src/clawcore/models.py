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


@dataclass(slots=True)
class ReActStep:
    """One planner step in the ReAct loop."""

    thought: str
    action: ToolCall | None = None
    final_answer: str | None = None
