"""Registries for runtime-owned tools."""

from __future__ import annotations

from clawcore.tooling.base import BaseTool, ToolExecutionContext, ToolHandler, resolve_awaitable


class ToolRegistry:
    """Stores named tool implementations."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        normalized = tool.name.strip()
        if not normalized:
            raise ValueError("Tool name must not be empty.")
        if normalized in self._tools:
            raise ValueError(f"Tool '{normalized}' is already registered.")
        self._tools[normalized] = tool

    def resolve(self, name: str) -> BaseTool:
        normalized = name.strip()
        if normalized not in self._tools:
            raise KeyError(f"Tool '{normalized}' is not registered.")
        return self._tools[normalized]

    async def run(
        self,
        name: str,
        payload: dict[str, object],
        context: ToolExecutionContext | None = None,
    ) -> str:
        tool = self.resolve(name)
        result = await tool.execute(payload, context or ToolExecutionContext())
        return str(result)

    def names(self) -> list[str]:
        return sorted(self._tools)


class CallableTool(BaseTool):
    """Adapter that exposes a Python callable as a runtime tool."""

    def __init__(self, tool_name: str, tool_handler: ToolHandler) -> None:
        self.name = tool_name
        self._handler = tool_handler

    async def execute(self, payload: dict[str, object], context: ToolExecutionContext) -> str:
        result = await resolve_awaitable(self._handler(payload))
        return str(result)
