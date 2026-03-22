"""Execution pipeline for runtime-owned tools."""

from __future__ import annotations

from clawcore.tooling.base import ToolExecutionContext
from clawcore.tooling.policy import ToolPolicy
from clawcore.tooling.registry import ToolRegistry
from clawcore.tooling.result import ToolExecutionResult, ToolExecutionStatus
from common.observability import logger


class ToolExecutor:
    """Executes tools through a registry and policy layer."""

    def __init__(self, registry: ToolRegistry, policy: ToolPolicy | None = None) -> None:
        self.registry = registry
        self.policy = policy or ToolPolicy()

    async def execute(
        self,
        tool_name: str,
        payload: dict[str, object],
        *,
        context: ToolExecutionContext | None = None,
    ) -> ToolExecutionResult:
        if not self.policy.is_allowed(tool_name):
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
