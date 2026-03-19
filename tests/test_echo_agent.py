import asyncio

from agents.echo_agent import EchoAgent


def test_echo_agent_returns_tool_observation() -> None:
    agent = EchoAgent()

    result = asyncio.run(agent.run("hello"))

    assert result == "echo: hello"
