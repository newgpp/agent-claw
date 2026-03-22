from pathlib import Path

from agents.base import AgentDescriptor
from agents.runtime_agent import AgentRunConfig, PlanningConfig, PlanningMode, RuntimeAgent
from clawcore.runtime import ReActRuntime


class StubRuntime:
    def __init__(self, result: str = "ok") -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def run(self, user_input: str, **kwargs) -> str:  # type: ignore[no-untyped-def]
        self.calls.append({"user_input": user_input, **kwargs})
        return self.result

    async def run_debug(self, user_input: str, **kwargs) -> str:  # type: ignore[no-untyped-def]
        self.calls.append({"user_input": user_input, **kwargs})
        return self.result

    async def run_planner_first(self, user_input: str, **kwargs) -> str:  # type: ignore[no-untyped-def]
        self.calls.append({"mode": "planner_first", "user_input": user_input, **kwargs})
        return self.result

    async def run_debug_planner_first(self, user_input: str, **kwargs) -> str:  # type: ignore[no-untyped-def]
        self.calls.append({"mode": "planner_first", "user_input": user_input, **kwargs})
        return self.result


class DemoRuntimeAgent(RuntimeAgent):
    descriptor = AgentDescriptor(name="demo-agent", description="Demo runtime agent.")


async def _run_agent(agent: RuntimeAgent, user_input: str, *, workspace_dir: Path | None = None) -> str:
    return await agent.run(user_input, workspace_dir=workspace_dir)


def test_runtime_agent_forwards_defaults(tmp_path: Path) -> None:
    runtime = StubRuntime(result="done")
    config = AgentRunConfig(
        base_instructions="Follow the demo policy.",
        max_steps=7,
        workspace_dir=tmp_path,
    )
    agent = DemoRuntimeAgent(runtime, config=config)  # type: ignore[arg-type]

    import asyncio

    result = asyncio.run(_run_agent(agent, "hello"))

    assert result == "done"
    assert runtime.calls == [
        {
            "user_input": "hello",
            "skills": [],
            "active_skill": None,
            "max_steps": 7,
            "base_instructions": "Follow the demo policy.",
            "workspace_dir": tmp_path,
        }
    ]


def test_runtime_agent_allows_workspace_override(tmp_path: Path) -> None:
    runtime = StubRuntime()
    agent = DemoRuntimeAgent(runtime, config=AgentRunConfig(workspace_dir=tmp_path))  # type: ignore[arg-type]
    override_dir = tmp_path / "override"

    import asyncio

    asyncio.run(_run_agent(agent, "hello", workspace_dir=override_dir))

    assert runtime.calls[0]["workspace_dir"] == override_dir


def test_agent_run_config_defaults_do_not_mutate_shared_state() -> None:
    first = AgentRunConfig()
    second = AgentRunConfig()

    assert first.skills == ()
    assert second.skills == ()
    assert first.skills is not second.skills or first.skills == second.skills


def test_runtime_agent_exposes_descriptor() -> None:
    runtime = StubRuntime()
    agent = DemoRuntimeAgent(runtime)  # type: ignore[arg-type]

    assert agent.name == "demo-agent"
    assert agent.description == "Demo runtime agent."


def test_runtime_agent_forwards_debug_runs(tmp_path: Path) -> None:
    runtime = StubRuntime(result="done")
    agent = DemoRuntimeAgent(runtime, config=AgentRunConfig(workspace_dir=tmp_path))  # type: ignore[arg-type]

    import asyncio

    asyncio.run(agent.run_debug("hello"))

    assert runtime.calls[0]["workspace_dir"] == tmp_path


def test_runtime_agent_uses_direct_runner_when_planning_disabled(tmp_path: Path) -> None:
    runtime = StubRuntime(result="done")
    agent = DemoRuntimeAgent(
        runtime,
        config=AgentRunConfig(
            workspace_dir=tmp_path,
            planning=PlanningConfig(mode=PlanningMode.DISABLED),
        ),
    )  # type: ignore[arg-type]

    import asyncio

    asyncio.run(agent.run("hello"))

    assert "mode" not in runtime.calls[0]


def test_runtime_agent_uses_planned_runner_when_planning_always_enabled(tmp_path: Path) -> None:
    runtime = StubRuntime(result="done")
    agent = DemoRuntimeAgent(
        runtime,
        config=AgentRunConfig(
            workspace_dir=tmp_path,
            planning=PlanningConfig(mode=PlanningMode.ALWAYS),
        ),
    )  # type: ignore[arg-type]

    import asyncio

    asyncio.run(agent.run("hello"))

    assert runtime.calls[0]["mode"] == "planner_first"


def test_runtime_agent_uses_direct_runner_when_planning_disabled_in_debug_mode(tmp_path: Path) -> None:
    runtime = StubRuntime(result="done")
    agent = DemoRuntimeAgent(
        runtime,
        config=AgentRunConfig(
            workspace_dir=tmp_path,
            planning=PlanningConfig(mode=PlanningMode.DISABLED),
        ),
    )  # type: ignore[arg-type]

    import asyncio

    asyncio.run(agent.run_debug("hello"))

    assert "mode" not in runtime.calls[0]


def test_runtime_agent_uses_planner_first_runner_for_enabled_runs(tmp_path: Path) -> None:
    runtime = StubRuntime(result="done")
    agent = DemoRuntimeAgent(
        runtime,
        config=AgentRunConfig(
            workspace_dir=tmp_path,
            planning=PlanningConfig(mode=PlanningMode.ALWAYS),
        ),
    )  # type: ignore[arg-type]

    import asyncio

    asyncio.run(agent.run("hello"))

    assert runtime.calls[0]["mode"] == "planner_first"


def test_runtime_agent_raises_clear_error_when_planner_first_runner_is_missing(tmp_path: Path) -> None:
    class DirectOnlyRuntime(StubRuntime):
        run_planner_first = None  # type: ignore[assignment]

    runtime = DirectOnlyRuntime()
    agent = DemoRuntimeAgent(
        runtime,
        config=AgentRunConfig(
            workspace_dir=tmp_path,
            planning=PlanningConfig(mode=PlanningMode.ALWAYS),
        ),
    )  # type: ignore[arg-type]

    import asyncio

    try:
        asyncio.run(agent.run("hello"))
    except NotImplementedError as exc:
        assert "run_planner_first" in str(exc)
    else:
        raise AssertionError("Expected planning-enabled runtime to require run_planner_first().")
