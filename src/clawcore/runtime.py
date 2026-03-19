"""Minimal ReAct runtime for planning and tool execution."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from inspect import isawaitable

from clawcore.models import ReActStep
from clawcore.registry import SkillRegistry, ToolRegistry
from clawcore.tooling.base import ToolExecutionContext
from common.observability import logger
from common.tracing import TraceCollector


@dataclass(slots=True)
class RuntimeContext:
    """Shared runtime state for a single agent invocation."""

    user_input: str
    trace: TraceCollector = field(default_factory=TraceCollector)
    scratchpad: list[str] = field(default_factory=list)


class ReActRuntime:
    """Executes a planner loop until a final answer is produced."""

    def __init__(
        self,
        planner,
        *,
        tools: ToolRegistry | None = None,
        skills: SkillRegistry | None = None,
    ) -> None:
        self.planner = planner
        self.tools = tools or ToolRegistry()
        self.skills = skills or SkillRegistry()

    async def run(self, user_input: str, *, max_steps: int = 5) -> str:
        context = RuntimeContext(user_input=user_input)
        context.trace.record("input", user_input)

        for step_index in range(1, max_steps + 1):
            step = self.planner(context)
            if isawaitable(step):
                step = await step
            self._record_step(context, step_index, step)

            if step.final_answer is not None:
                logger.info("Finished ReAct loop in {} step(s)", step_index)
                return step.final_answer

            if step.action is None:
                raise RuntimeError("Planner returned neither an action nor a final answer.")

            tool_output = await self.tools.run(
                step.action.name,
                step.action.payload,
                context=ToolExecutionContext(),
            )
            observation = f"{step.action.name}: {tool_output}"
            context.scratchpad.append(observation)
            context.trace.record("observation", observation)

        raise RuntimeError("ReAct loop exceeded max_steps without a final answer.")

    def _record_step(self, context: RuntimeContext, step_index: int, step: ReActStep) -> None:
        context.trace.record("thought", f"step={step_index} {step.thought}")
        logger.debug("Step {} thought: {}", step_index, step.thought)

        if step.action is not None:
            context.trace.record("action", f"{step.action.name} -> {step.action.payload}")
