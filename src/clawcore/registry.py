"""Registries for reusable skills and tools."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from inspect import isawaitable

from clawcore.tooling.base import BaseTool, ToolExecutionContext
from clawcore.tooling.registry import CallableTool, ToolRegistry as RuntimeToolRegistry

ToolHandler = Callable[[dict[str, object]], str | Awaitable[str]]
SkillHandler = Callable[[str], str | Awaitable[str]]


class ToolRegistry(RuntimeToolRegistry):
    """Stores named tool handlers."""

    def __init__(self) -> None:
        super().__init__()

    def register(self, name: str | BaseTool, handler: ToolHandler | None = None) -> None:  # type: ignore[override]
        if isinstance(name, BaseTool):
            return super().register(name)
        if handler is None:
            raise ValueError("Handler is required when registering a callable tool.")

        return super().register(CallableTool(name, handler))


class SkillRegistry:
    """Stores named skill handlers."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillHandler] = {}

    def register(self, name: str, handler: SkillHandler) -> None:
        self._skills[name] = handler

    async def run(self, name: str, prompt: str) -> str:
        if name not in self._skills:
            raise KeyError(f"Skill '{name}' is not registered.")
        result = self._skills[name](prompt)
        if isawaitable(result):
            result = await result
        return str(result)

    def names(self) -> list[str]:
        return sorted(self._skills)
