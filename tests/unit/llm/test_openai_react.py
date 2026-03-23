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
    def __init__(
        self,
        content: str,
        *,
        prompt_tokens: int = 11,
        completion_tokens: int = 7,
        total_tokens: int = 18,
    ) -> None:
        self.choices = [FakeChoice(content)]
        self.usage = type(
            "FakeUsage",
            (),
            {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
        )()


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
    state.prompt_observations.append("read: note contents")
    state.sync_views()
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
                    notes="Use the weather skill and curl.",
                ),
                PlanSubgoal(
                    id="s2",
                    task="Draft the email",
                    status=PlanStatus.PENDING,
                    notes="Use the weather result as context for the email.",
                ),
            ],
            success_criteria=["Weather fetched"],
            status=PlanStatus.IN_PROGRESS,
        ),
        active_subgoal_id="s1",
        active_subgoal_task="Fetch Tangshan weather",
        active_subgoal_notes="Use the weather skill and curl.",
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
    assert "Do not call `read` for a file path unless the user provided that path" in request["messages"][0]["content"]
    assert "Do not insert unnecessary backslashes before markdown punctuation" in request["messages"][0]["content"]
    assert '"active_skill": "file-summary"' in request["messages"][1]["content"]
    assert '"loaded_skills": ["file-summary"]' in request["messages"][1]["content"]
    assert '"observations": ["read: note contents"]' in request["messages"][1]["content"]
    assert '"step_summaries": []' in request["messages"][1]["content"]


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


def test_openai_react_llm_repairs_common_invalid_json_escapes() -> None:
    client = FakeOpenAIClient(
        '{"thought":"Send the email.","action":{"name":"send_email","payload":{"to":"newgpp@hotmail.com","subject":"北京出行指南","body":"第一行\\n第二行\\-第三行"}},"final_answer":null}'
    )
    llm = OpenAIReActLLM(
        OpenAIReActConfig(model="deepseek-chat", api_key="test-key"),
        client=client,  # type: ignore[arg-type]
    )

    step = asyncio.run(llm.next_step(build_session()))

    assert step.action is not None
    assert step.action.name == "send_email"
    assert step.action.payload["subject"] == "北京出行指南"
    assert step.action.payload["body"] == "第一行\n第二行\\-第三行"


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
        "LLM response model={} usage={} content={}",
        (
            "deepseek-chat",
            '{"completion_tokens": 7, "prompt_tokens": 11, "total_tokens": 18}',
            '{"thought":"I can answer now.","action":null,"final_answer":"done"}',
        ),
    )


def test_openai_react_llm_accumulates_token_usage_in_state() -> None:
    client = FakeOpenAIClient('{"thought":"I can answer now.","action":null,"final_answer":"done"}')
    llm = OpenAIReActLLM(
        OpenAIReActConfig(model="deepseek-chat", api_key="test-key"),
        client=client,  # type: ignore[arg-type]
    )
    session = build_session()

    asyncio.run(llm.next_step(session))

    assert session.state.token_usage.executor.prompt_tokens == 11
    assert session.state.token_usage.executor.completion_tokens == 7
    assert session.state.token_usage.executor.total_tokens == 18


def test_openai_react_llm_includes_active_subgoal_context() -> None:
    client = FakeOpenAIClient('{"thought":"Use curl.","action":null,"final_answer":"done"}')
    llm = OpenAIReActLLM(
        OpenAIReActConfig(model="deepseek-chat", api_key="test-key"),
        client=client,  # type: ignore[arg-type]
    )

    asyncio.run(llm.next_step(build_planned_session()))

    request = client.chat.completions.calls[0]
    system_message = request["messages"][0]["content"]
    runtime_context = request["messages"][1]["content"]

    assert "When `execution.active_subgoal` is present, it is the only executable scope" in system_message
    assert "As soon as the active subgoal is satisfied, return `final_answer` immediately" in system_message
    assert "runtime.file_cache" in system_message
    assert '"user_request": {"raw_input": "Check Tangshan weather and write an email"}' in runtime_context
    assert '"active_subgoal": {"id": "s1", "notes": "Use the weather skill and curl.", "task": "Fetch Tangshan weather"}' in runtime_context
    assert '"remaining_subgoal_ids": ["s2"]' in runtime_context
    assert '"task": "Draft the email"' not in runtime_context
