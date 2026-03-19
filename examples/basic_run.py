"""Run a tiny agent-claw example locally."""

import asyncio

from agents.echo_agent import EchoAgent
from common.observability import setup_loguru


async def main() -> None:
    setup_loguru(service_name="agent-claw-demo")
    agent = EchoAgent()
    result = await agent.run("hello from agent-claw")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
