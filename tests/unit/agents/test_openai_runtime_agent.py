import asyncio
from pathlib import Path

import pytest

from agents import AgentRunConfig, OpenAIRuntimeAgent, OpenAIRuntimeAgentOptions
from agents.openai_runtime_agent import load_openai_react_config_from_env
from clawcore.tooling import BaseTool


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [FakeChoice(content)]


class SequencedCompletions:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("No fake LLM responses left.")
        return FakeResponse(self.responses.pop(0))


class FakeChat:
    def __init__(self, responses: list[str]) -> None:
        self.completions = SequencedCompletions(responses)


class FakeOpenAIClient:
    def __init__(self, responses: list[str]) -> None:
        self.chat = FakeChat(responses)


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo back a text payload."

    async def execute(self, payload: dict[str, object], context) -> str:  # type: ignore[no-untyped-def]
        return str(payload.get("text", ""))


def test_load_openai_react_config_from_env_requires_model_and_api_key() -> None:
    with pytest.raises(ValueError, match="OPENAI_MODEL"):
        load_openai_react_config_from_env({"OPENAI_API_KEY": "test-key"})

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        load_openai_react_config_from_env({"OPENAI_MODEL": "gpt-test"})


def test_load_openai_react_config_from_env_parses_optional_fields() -> None:
    config = load_openai_react_config_from_env(
        {
            "OPENAI_MODEL": "gpt-test",
            "OPENAI_API_KEY": "test-key",
            "OPENAI_BASE_URL": "http://localhost:1234/v1",
            "OPENAI_TEMPERATURE": "0.7",
            "OPENAI_MAX_TOKENS": "256",
        }
    )

    assert config.model == "gpt-test"
    assert config.api_key == "test-key"
    assert config.base_url == "http://localhost:1234/v1"
    assert config.temperature == 0.7
    assert config.max_tokens == 256


def test_openai_runtime_agent_runs_with_openai_planner(tmp_path: Path) -> None:
    client = FakeOpenAIClient(
        responses=[
            '{"thought":"Use the echo tool first.","action":{"name":"echo","payload":{"text":"hello from llm"}},"final_answer":null}',
            '{"thought":"I have the tool result.","action":null,"final_answer":"done: hello from llm"}',
        ]
    )
    agent = OpenAIRuntimeAgent(
        tools=[EchoTool()],
        options=OpenAIRuntimeAgentOptions(
            run_config=AgentRunConfig(
                base_instructions="Use the echo tool before answering.",
                max_steps=3,
                workspace_dir=tmp_path,
            ),
            llm_config=load_openai_react_config_from_env(
                {
                    "OPENAI_MODEL": "gpt-test",
                    "OPENAI_API_KEY": "test-key",
                }
            ),
            include_read_skill=False,
        ),
        client=client,
    )

    result = asyncio.run(agent.run("Say hello"))

    assert result == "done: hello from llm"
    assert client.chat.completions.calls[0]["model"] == "gpt-test"
    assert "Use the echo tool before answering." in client.chat.completions.calls[0]["messages"][0]["content"]
