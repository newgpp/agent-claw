"""Registries for reusable skills and tools."""

from __future__ import annotations

from collections.abc import Callable

ToolHandler = Callable[[dict[str, object]], str]
SkillHandler = Callable[[str], str]


class ToolRegistry:
    """Stores named tool handlers."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolHandler] = {}

    def register(self, name: str, handler: ToolHandler) -> None:
        self._tools[name] = handler

    def run(self, name: str, payload: dict[str, object]) -> str:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered.")
        return self._tools[name](payload)

    def names(self) -> list[str]:
        return sorted(self._tools)


class SkillRegistry:
    """Stores named skill handlers."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillHandler] = {}

    def register(self, name: str, handler: SkillHandler) -> None:
        self._skills[name] = handler

    def run(self, name: str, prompt: str) -> str:
        if name not in self._skills:
            raise KeyError(f"Skill '{name}' is not registered.")
        return self._skills[name](prompt)

    def names(self) -> list[str]:
        return sorted(self._skills)
