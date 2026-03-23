import asyncio
from pathlib import Path

from clawcore.llm.mock import MockLLM
from clawcore.models import ReActStep, ToolCall
from clawcore.runtime.react import ReActRuntime
from clawcore.runtime.session import AgentSession
from clawcore.skilling.loader import load_skills
from clawcore.tooling import ReadSkillTool, ToolExecutor, ToolRegistry
from clawcore.tooling.base import BaseTool, ToolExecutionContext


class FakeWeatherTool(BaseTool):
    name = "curl"
    description = "Return a mocked weather response for a wttr.in URL."

    async def execute(self, payload: dict[str, object], context: ToolExecutionContext) -> str:
        url = str(payload.get("url", "")).strip()
        if not url:
            raise ValueError("curl requires a non-empty 'url'.")
        if context.active_skill is None:
            raise ValueError("curl requires the active weather skill.")
        if context.active_skill.name != "weather":
            raise ValueError(f"Unexpected active skill: {context.active_skill.name}")
        if "Hong+Kong" not in url and "Hong Kong" not in url and "%E9%A6%99%E6%B8%AF" not in url:
            raise ValueError(f"Unexpected weather URL: {url}")
        return "Hong Kong: Sunny, 26C"


def build_runtime(step_fn) -> ReActRuntime:  # type: ignore[no-untyped-def]
    registry = ToolRegistry()
    registry.register(ReadSkillTool())
    registry.register(FakeWeatherTool())
    executor = ToolExecutor(registry)
    return ReActRuntime(llm=MockLLM(step_fn), tool_executor=executor)


def test_weather_skill_flow_loads_skill_and_queries_weather() -> None:
    skills = load_skills(Path("tests/fixtures/skills/weather"))
    assert [skill.name for skill in skills] == ["weather"]

    async def weather_flow(session: AgentSession) -> ReActStep:
        if not session.state.scratchpad:
            return ReActStep(
                thought="Load the weather skill instructions first.",
                action=ToolCall(name="read_skill", payload={"skill": "weather"}),
            )
        if len(session.state.scratchpad) == 1:
            return ReActStep(
                thought="Use the loaded weather skill to answer the request.",
                action=ToolCall(
                    name="curl",
                    payload={"url": "https://wttr.in/Hong+Kong?format=3"},
                ),
            )
        return ReActStep(thought="done", final_answer=session.state.scratchpad[-1])

    runtime = build_runtime(weather_flow)
    result = asyncio.run(runtime.run("What's the weather in Hong Kong?", skills=skills))

    assert "curl: Hong Kong: Sunny, 26C" == result
