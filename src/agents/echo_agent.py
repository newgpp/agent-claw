"""A small example agent built with the core runtime."""

from __future__ import annotations

import asyncio

from agents.base import AgentDescriptor
from agents.runtime_agent import AgentRunConfig, RuntimeAgent
from clawcore.llm.mock import MockLLM
from clawcore.models import ReActStep, ToolCall
from clawcore.registry import ToolRegistry
from clawcore.runtime import ReActRuntime
from clawcore.runtime.session import AgentSession
from clawcore.tooling import ToolExecutor


async def _echo_step(session: AgentSession) -> ReActStep:
    if not session.state.scratchpad:
        return ReActStep(
            thought="I should call a simple tool to transform the user's message.",
            action=ToolCall(name="echo", payload={"text": session.state.user_input}),
        )

    return ReActStep(
        thought="I have the tool observation and can answer the user.",
        final_answer=session.state.scratchpad[-1],
    )


class EchoAgent(RuntimeAgent):
    """Example business agent showing how agents compose the core runtime."""

    descriptor = AgentDescriptor(
        name="echo-agent",
        description="A tiny agent that echoes user input through the runtime tool loop.",
    )

    def __init__(self) -> None:
        tools = ToolRegistry()

        async def echo_handler(payload: dict[str, object]) -> str:
            await asyncio.sleep(0)
            return str(payload.get("text", ""))

        tools.register("echo", echo_handler)
        super().__init__(
            ReActRuntime(
                llm=MockLLM(_echo_step),
                tool_executor=ToolExecutor(tools),
            ),
            config=AgentRunConfig(
                base_instructions="Use the echo tool before answering the user.",
                max_steps=3,
            ),
        )
