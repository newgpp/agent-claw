"""A small example agent built with the core runtime."""

from __future__ import annotations

from agents.base import BaseAgent
from clawcore.models import ReActStep, ToolCall
from clawcore.registry import ToolRegistry
from clawcore.runtime import ReActRuntime, RuntimeContext


def _echo_planner(context: RuntimeContext) -> ReActStep:
    if not context.scratchpad:
        return ReActStep(
            thought="I should call a simple tool to transform the user's message.",
            action=ToolCall(name="echo", payload={"text": context.user_input}),
        )

    return ReActStep(
        thought="I have the tool observation and can answer the user.",
        final_answer=context.scratchpad[-1],
    )


class EchoAgent(BaseAgent):
    """Example business agent showing how agents compose the core runtime."""

    def __init__(self) -> None:
        tools = ToolRegistry()
        tools.register("echo", lambda payload: str(payload.get("text", "")))
        self.runtime = ReActRuntime(planner=_echo_planner, tools=tools)

    def run(self, user_input: str) -> str:
        return self.runtime.run(user_input)
