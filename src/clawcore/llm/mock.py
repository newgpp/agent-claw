"""Mock LLM implementation for deterministic runtime tests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from inspect import isawaitable

from clawcore.llm.base import BaseLLM, BasePlanner
from clawcore.models import ExecutionPlan, ReActStep
from clawcore.runtime.session import AgentSession


class MockLLM(BaseLLM):
    """Mock LLM that delegates to a scripted step function."""

    def __init__(self, step_fn: Callable[[AgentSession], ReActStep | Awaitable[ReActStep]]) -> None:
        self.step_fn = step_fn

    async def next_step(self, session: AgentSession) -> ReActStep:
        step = self.step_fn(session)
        if isawaitable(step):
            step = await step
        return step


class MockPlanner(BasePlanner):
    """Mock planner that delegates to a scripted plan function."""

    def __init__(
        self,
        plan_fn: Callable[[AgentSession], ExecutionPlan | Awaitable[ExecutionPlan]],
    ) -> None:
        self.plan_fn = plan_fn

    async def create_plan(self, session: AgentSession) -> ExecutionPlan:
        plan = self.plan_fn(session)
        if isawaitable(plan):
            plan = await plan
        return plan
