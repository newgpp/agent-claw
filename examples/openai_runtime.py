"""Run an OpenAI-backed runtime agent from a JSON config."""

from __future__ import annotations

import asyncio
from pathlib import Path

from agents import get_agent
from common.observability import setup_loguru


async def main() -> None:
    setup_loguru(service_name="agent-claw-openai-demo")
    config_path = Path(__file__).resolve().parents[1] / "configs" / "agents" / "openai_runtime.json"
    agent = get_agent(str(config_path))
    result = await agent.run("Say hello with the echo_payload tool.")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
