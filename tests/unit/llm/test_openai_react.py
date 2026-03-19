import asyncio
from pathlib import Path

import pytest

from clawcore.llm import OpenAIReActConfig, OpenAIReActLLM
from clawcore.runtime.session import AgentSession
from clawcore.runtime.state import RuntimeState
from clawcore.skilling.models import SkillDefinition


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, response_content: str) -> None:
        self.response_content = response_content
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        return FakeResponse(self.response_content)


class FakeChat:
    def __init__(self, response_content: str) -> None:
        self.completions = FakeCompletions(response_content)


class FakeOpenAIClient:
    def __init__(self, response_content: str) -> None:
        self.chat = FakeChat(response_content)


def build_session() -> AgentSession:
    skill = SkillDefinition(
        name="file-summary",
        description="Summarize a file.",
        directory=Path("/virtual/skills/file-summary"),
        skill_file=Path("/virtual/skills/file-summary/SKILL.md"),
    )
    state = RuntimeState(
        user_input="Summarize note.txt",
        system_prompt=(
            "Skill loading policy:\n"
            "- Call `read_skill` only when a skill summary looks relevant and you need the full instructions.\n"
            "Available tools:\n"
            "- read: Read file contents from the workspace.\n"
            "- read_skill: Load the full markdown content for one available skill."
        ),
        available_skills=(skill,),
        loaded_skills=[skill],
        active_skill=skill,
    )
    state.scratchpad.append("read: note contents")
    return AgentSession(state=state)


def test_openai_react_llm_parses_action_response() -> None:
    client = FakeOpenAIClient(
        '{"thought":"Load the skill.","action":{"name":"read_skill","payload":{"skill":"file-summary"}},"final_answer":null}'
    )
    llm = OpenAIReActLLM(
        OpenAIReActConfig(model="deepseek-chat", api_key="test-key", base_url="http://localhost"),
        client=client,  # type: ignore[arg-type]
    )

    step = asyncio.run(llm.next_step(build_session()))

    assert step.thought == "Load the skill."
    assert step.action is not None
    assert step.action.name == "read_skill"
    assert step.action.payload == {"skill": "file-summary"}
    request = client.chat.completions.calls[0]
    assert request["model"] == "deepseek-chat"
    assert request["messages"][0]["role"] == "system"
    assert "Call `read_skill` only when a skill summary looks relevant" in request["messages"][0]["content"]
    assert "- read_skill: Load the full markdown content for one available skill." in request["messages"][0]["content"]
    assert "If a skill seems relevant but you need its full procedure" in request["messages"][0]["content"]
    assert "Loaded skills: file-summary" in request["messages"][1]["content"]


def test_openai_react_llm_parses_final_answer_response() -> None:
    client = FakeOpenAIClient('{"thought":"I can answer now.","action":null,"final_answer":"done"}')
    llm = OpenAIReActLLM(
        OpenAIReActConfig(model="deepseek-chat", api_key="test-key"),
        client=client,  # type: ignore[arg-type]
    )

    step = asyncio.run(llm.next_step(build_session()))

    assert step.final_answer == "done"
    assert step.action is None


def test_openai_react_llm_rejects_invalid_json() -> None:
    client = FakeOpenAIClient("not-json")
    llm = OpenAIReActLLM(
        OpenAIReActConfig(model="deepseek-chat", api_key="test-key"),
        client=client,  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="valid JSON"):
        asyncio.run(llm.next_step(build_session()))
