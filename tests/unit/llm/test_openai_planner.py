import asyncio
from pathlib import Path

import pytest

from clawcore.llm import OpenAIPlanner, OpenAIReActConfig
from clawcore.models import PlanStatus
from clawcore.runtime.prompt_builder import PlanningPromptBuilder
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
        prompt_tokens: int = 13,
        completion_tokens: int = 9,
        total_tokens: int = 22,
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
        name="weather",
        description="Check current weather.",
        directory=Path("/virtual/skills/weather"),
        skill_file=Path("/virtual/skills/weather/SKILL.md"),
    )
    prompt = PlanningPromptBuilder().build(
        skills=[skill],
        tool_names=["curl", "send_email"],
        tool_descriptions={
            "curl": "Fetch HTTP resources.",
            "send_email": "Send an email to a recipient.",
        },
        base_instructions="Use the available tools carefully.",
    )
    state = RuntimeState(
        user_input="Write an email based on today's weather",
        system_prompt=prompt,
        available_skills=(skill,),
        loaded_skills=[skill],
        active_skill=skill,
    )
    state.scratchpad.append("weather report: Hong Kong 26C")
    return AgentSession(state=state)


def test_openai_planner_parses_plan_response() -> None:
    client = FakeOpenAIClient(
        '{"goal":"Write and send a weather email",'
        '"subgoals":['
        '{"id":"s1","task":"Fetch the weather","notes":"Use curl."},'
        '{"id":"s2","task":"Draft the email","notes":"Use the weather as context."}'
        '],'
        '"success_criteria":["The email draft is complete","The email is ready to send"],'
        '"assumptions":["The recipient address is known"]}'
    )
    planner = OpenAIPlanner(
        OpenAIReActConfig(model="deepseek-chat", api_key="test-key", base_url="http://localhost"),
        client=client,  # type: ignore[arg-type]
    )

    plan = asyncio.run(planner.create_plan(build_session()))

    assert plan.goal == "Write and send a weather email"
    assert [subgoal.id for subgoal in plan.subgoals] == ["s1", "s2"]
    assert plan.subgoals[0].status == PlanStatus.PENDING
    assert plan.success_criteria == ["The email draft is complete", "The email is ready to send"]
    assert plan.assumptions == ["The recipient address is known"]
    request = client.chat.completions.calls[0]
    assert request["model"] == "deepseek-chat"
    assert request["messages"][0]["role"] == "system"
    assert "Planning policy:" in request["messages"][0]["content"]
    assert "subgoals: []" in request["messages"][0]["content"]
    assert "exactly one subgoal" in request["messages"][0]["content"]
    assert "Preserve the user's language for user-facing deliverables" in request["messages"][0]["content"]
    assert '"active_skill": "weather"' in request["messages"][1]["content"]
    assert '"scratchpad_observations": ["weather report: Hong Kong 26C"]' in request["messages"][1]["content"]


def test_openai_planner_parses_direct_answer_plan() -> None:
    client = FakeOpenAIClient(
        '{"goal":"Hong Kong is 26C today.","subgoals":[],"success_criteria":["Answer the user directly"],"assumptions":[]}'
    )
    planner = OpenAIPlanner(
        OpenAIReActConfig(model="deepseek-chat", api_key="test-key", base_url="http://localhost"),
        client=client,  # type: ignore[arg-type]
    )

    plan = asyncio.run(planner.create_plan(build_session()))

    assert plan.goal == "Hong Kong is 26C today."
    assert plan.subgoals == []
    assert plan.is_direct_answer
    assert not plan.is_single_step


def test_openai_planner_parses_single_subgoal_plan() -> None:
    client = FakeOpenAIClient(
        '{"goal":"Fetch the current weather.","subgoals":[{"id":"s1","task":"Read the local weather file","notes":"Use the read tool."}],"success_criteria":["Weather data is available"],"assumptions":[]}'
    )
    planner = OpenAIPlanner(
        OpenAIReActConfig(model="deepseek-chat", api_key="test-key", base_url="http://localhost"),
        client=client,  # type: ignore[arg-type]
    )

    plan = asyncio.run(planner.create_plan(build_session()))

    assert plan.goal == "Fetch the current weather."
    assert [subgoal.id for subgoal in plan.subgoals] == ["s1"]
    assert not plan.is_direct_answer
    assert plan.is_single_step


def test_openai_planner_rejects_invalid_json() -> None:
    client = FakeOpenAIClient("not-json")
    planner = OpenAIPlanner(
        OpenAIReActConfig(model="deepseek-chat", api_key="test-key"),
        client=client,  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="valid JSON"):
        asyncio.run(planner.create_plan(build_session()))


def test_openai_planner_rejects_missing_goal() -> None:
    client = FakeOpenAIClient('{"subgoals":[],"success_criteria":[],"assumptions":[]}')
    planner = OpenAIPlanner(
        OpenAIReActConfig(model="deepseek-chat", api_key="test-key"),
        client=client,  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="non-empty 'goal'"):
        asyncio.run(planner.create_plan(build_session()))


def test_openai_planner_logs_request_and_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeOpenAIClient(
        '{"goal":"Write and send a weather email","subgoals":[],"success_criteria":[],"assumptions":[]}'
    )
    planner = OpenAIPlanner(
        OpenAIReActConfig(model="deepseek-chat", api_key="test-key"),
        client=client,  # type: ignore[arg-type]
    )
    records: list[tuple[str, tuple[object, ...]]] = []

    def fake_info(message: str, *args: object) -> None:
        records.append((message, args))

    monkeypatch.setattr("clawcore.llm.openai_planner.logger.info", fake_info)
    trace_token = bind_trace_id("trace-planner")

    try:
        plan = asyncio.run(planner.create_plan(build_session()))
    finally:
        reset_trace_id(trace_token)

    assert plan.goal == "Write and send a weather email"
    assert len(records) == 2
    assert records[0][0] == "Planner request model={} payload={}"
    assert records[0][1][0] == "deepseek-chat"
    assert "Write an email based on today's weather" in str(records[0][1][1])
    assert records[1] == (
        "Planner response model={} usage={} content={}",
        (
            "deepseek-chat",
            '{"completion_tokens": 9, "prompt_tokens": 13, "total_tokens": 22}',
            '{"goal":"Write and send a weather email","subgoals":[],"success_criteria":[],"assumptions":[]}',
        ),
    )


def test_openai_planner_accumulates_token_usage_in_state() -> None:
    client = FakeOpenAIClient(
        '{"goal":"Write and send a weather email","subgoals":[],"success_criteria":[],"assumptions":[]}'
    )
    planner = OpenAIPlanner(
        OpenAIReActConfig(model="deepseek-chat", api_key="test-key"),
        client=client,  # type: ignore[arg-type]
    )
    session = build_session()

    asyncio.run(planner.create_plan(session))

    assert session.state.token_usage.planner.prompt_tokens == 13
    assert session.state.token_usage.planner.completion_tokens == 9
    assert session.state.token_usage.planner.total_tokens == 22
