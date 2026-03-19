"""Core models for thoughts, actions, and runtime state."""

from __future__ import annotations

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
class ReActStep:
    """One planner step in the ReAct loop."""

    thought: str
    action: ToolCall | None = None
    final_answer: str | None = None
