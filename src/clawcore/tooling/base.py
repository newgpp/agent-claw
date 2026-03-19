"""Base abstractions for runtime-owned tools."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from inspect import isawaitable
from pathlib import Path

from clawcore.skilling.models import SkillDefinition


@dataclass(slots=True)
class ToolExecutionContext:
    """Context available to tool executions."""

    workspace_dir: Path = field(default_factory=lambda: Path.cwd())
    active_skill: SkillDefinition | None = None
    available_skills: tuple[SkillDefinition, ...] = ()


class BaseTool:
    """Base class for built-in runtime tools."""

    name: str = ""
    description: str = ""
    risk_level: str = "low"

    async def execute(self, payload: dict[str, object], context: ToolExecutionContext) -> str:
        """Execute the tool with the provided payload and context."""
        raise NotImplementedError


ToolHandler = Callable[[dict[str, object]], str | Awaitable[str]]


async def resolve_awaitable(value: object) -> object:
    """Await the value if it is awaitable, otherwise return it as-is."""
    if isawaitable(value):
        return await value
    return value
