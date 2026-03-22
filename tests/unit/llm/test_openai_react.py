import asyncio
from pathlib import Path

import pytest

from clawcore.llm import OpenAIReActConfig, OpenAIReActLLM
from clawcore.models import ExecutionPlan, PlanStatus, PlanSubgoal
from clawcore.runtime.session import AgentSession
from clawcore.runtime.state import RuntimeState
from clawcore.skilling.models import SkillDefinition
from common.observability import bind_trace_id, reset_trace_id


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
            "- read_skill: Load the full markdown content for one available skill. Payload: {skill:string}."
        ),
        available_skills=(skill,),
        loaded_skills=[skill],
        active_skill=skill,
    )
    state.scratchpad.append("read: note contents")
    return AgentSession(state=state)


def build_planned_session() -> AgentSession:
    skill = SkillDefinition(
        name="weather",
        description="Check the weather.",
        directory=Path("/virtual/skills/weather"),
        skill_file=Path("/virtual/skills/weather/SKILL.md"),
    )
    state = RuntimeState(
        user_input="Check Tangshan weather and write an email",
        system_prompt="Use the available tools carefully.",
        available_skills=(skill,),
        plan=ExecutionPlan(
            goal="Check weather and send an email",
            subgoals=[
                PlanSubgoal(
                    id="s1",
                    task="Fetch Tangshan weather",
                    status=PlanStatus.IN_PROGRESS,
                    notes="Use the weather skill and curl, not exec_script.",
                )
            ],
            success_criteria=["Weather fetched"],
            status=PlanStatus.IN_PROGRESS,
        ),
        active_subgoal_id="s1",
        active_subgoal_task="Fetch Tangshan weather",
        active_subgoal_notes="Use the weather skill and curl, not exec_script.",
    )
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
    assert (
        "- read_skill: Load the full markdown content for one available skill. Payload: {skill:string}."
        in request["messages"][0]["content"]
    )
    assert "If a skill seems relevant but you need its full procedure" in request["messages"][0]["content"]
    assert "Never pass shell commands like `curl ...` or `python ...` as the `script` value" in request["messages"][0]["content"]
    assert '"active_skill": "file-summary"' in request["messages"][1]["content"]
    assert '"loaded_skills": ["file-summary"]' in request["messages"][1]["content"]
    assert '"scratchpad_observations": ["read: note contents"]' in request["messages"][1]["content"]


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


def test_openai_react_llm_logs_request_and_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeOpenAIClient('{"thought":"I can answer now.","action":null,"final_answer":"done"}')
    llm = OpenAIReActLLM(
        OpenAIReActConfig(model="deepseek-chat", api_key="test-key"),
        client=client,  # type: ignore[arg-type]
    )
    records: list[tuple[str, tuple[object, ...]]] = []

    def fake_info(message: str, *args: object) -> None:
        records.append((message, args))

    monkeypatch.setattr("clawcore.llm.openai_react.logger.info", fake_info)
    trace_token = bind_trace_id("trace-llm")

    try:
        step = asyncio.run(llm.next_step(build_session()))
    finally:
        reset_trace_id(trace_token)

    assert step.final_answer == "done"
    assert len(records) == 2
    assert records[0][0] == "LLM request model={} payload={}"
    assert records[0][1][0] == "deepseek-chat"
    assert "Summarize note.txt" in str(records[0][1][1])
    assert records[1] == (
        "LLM response model={} content={}",
        ("deepseek-chat", '{"thought":"I can answer now.","action":null,"final_answer":"done"}'),
    )


def test_openai_react_llm_includes_active_subgoal_context() -> None:
    client = FakeOpenAIClient('{"thought":"Use curl.","action":null,"final_answer":"done"}')
    llm = OpenAIReActLLM(
        OpenAIReActConfig(model="deepseek-chat", api_key="test-key"),
        client=client,  # type: ignore[arg-type]
    )

    asyncio.run(llm.next_step(build_planned_session()))

    request = client.chat.completions.calls[0]
    assert '"active_subgoal_id": "s1"' in request["messages"][1]["content"]
    assert '"active_subgoal_task": "Fetch Tangshan weather"' in request["messages"][1]["content"]
    assert '"active_subgoal_notes": "Use the weather skill and curl, not exec_script."' in request["messages"][1]["content"]
