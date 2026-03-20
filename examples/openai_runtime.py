"""Run a minimal OpenAI-backed runtime agent."""

from __future__ import annotations

import asyncio

from agents import AgentRunConfig, OpenAIRuntimeAgent, OpenAIRuntimeAgentOptions
from clawcore.tooling import BaseTool
from common.observability import setup_loguru


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo back a text payload."

    async def execute(self, payload: dict[str, object], context) -> str:  # type: ignore[no-untyped-def]
        return str(payload.get("text", ""))


async def main() -> None:
    setup_loguru(service_name="agent-claw-openai-demo")
    agent = OpenAIRuntimeAgent(
        tools=[EchoTool()],
        options=OpenAIRuntimeAgentOptions(
            run_config=AgentRunConfig(
                base_instructions="Use the echo tool before answering.",
                max_steps=3,
            ),
            include_read_skill=False,
        ),
    )
    result = await agent.run("Say hello with the echo tool.")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
