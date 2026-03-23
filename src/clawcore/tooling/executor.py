"""Execution pipeline for runtime-owned tools."""

from __future__ import annotations

from dataclasses import dataclass, field

from clawcore.tooling.base import ToolExecutionContext
from clawcore.tooling.registry import ToolRegistry
from clawcore.tooling.result import ToolExecutionResult, ToolExecutionStatus
from common.observability import logger


@dataclass(slots=True)
class ToolAccess:
    """Simple allowlist/denylist checks for tool execution."""

    allow: set[str] = field(default_factory=set)
    deny: set[str] = field(default_factory=set)

    def is_allowed(self, tool_name: str) -> bool:
        normalized = tool_name.strip()
        if normalized in self.deny:
            return False
        if self.allow and normalized not in self.allow:
            return False
        return True


class ToolExecutor:
    """Executes tools through a registry and policy layer."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        allow: set[str] | None = None,
        deny: set[str] | None = None,
    ) -> None:
        self.registry = registry
        self.access = ToolAccess(allow=allow or set(), deny=deny or set())

    async def execute(
        self,
        tool_name: str,
        payload: dict[str, object],
        *,
        context: ToolExecutionContext | None = None,
    ) -> ToolExecutionResult:
        if not self.access.is_allowed(tool_name):
            logger.error("Tool execution blocked tool_name={} payload={}", tool_name, payload)
            return ToolExecutionResult(
                tool_name=tool_name,
                status=ToolExecutionStatus.BLOCKED,
                content=f"Tool '{tool_name}' is blocked by policy.",
            )

        try:
            content = await self.registry.run(tool_name, payload, context=context)
        except Exception as exc:
            logger.exception(
                "Tool execution failed tool_name={} payload={} error_type={} detail={}",
                tool_name,
                payload,
                type(exc).__name__,
                str(exc),
            )
            return ToolExecutionResult(
                tool_name=tool_name,
                status=ToolExecutionStatus.ERROR,
                content=str(exc),
            )

        return ToolExecutionResult(
            tool_name=tool_name,
            status=ToolExecutionStatus.SUCCESS,
            content=content,
        )
