"""A small example agent built with the core runtime."""

from __future__ import annotations

import asyncio

from agents.base import BaseAgent
from clawcore.llm.mock import MockLLM
from clawcore.models import ReActStep, ToolCall
from clawcore.registry import ToolRegistry
from clawcore.runtime import ReActRuntime
from clawcore.tooling import ToolExecutor


async def _echo_step(session) -> ReActStep:  # type: ignore[no-untyped-def]
    if not session.state.scratchpad:
        return ReActStep(
            thought="I should call a simple tool to transform the user's message.",
            action=ToolCall(name="echo", payload={"text": session.state.user_input}),
        )

    return ReActStep(
        thought="I have the tool observation and can answer the user.",
        final_answer=session.state.scratchpad[-1],
    )


class EchoAgent(BaseAgent):
    """Example business agent showing how agents compose the core runtime."""

    def __init__(self) -> None:
        tools = ToolRegistry()

        async def echo_handler(payload: dict[str, object]) -> str:
            await asyncio.sleep(0)
            return str(payload.get("text", ""))

        tools.register("echo", echo_handler)
        self.runtime = ReActRuntime(
            llm=MockLLM(_echo_step),
            tool_executor=ToolExecutor(tools),
        )

    async def run(self, user_input: str) -> str:
        return await self.runtime.run(user_input)
