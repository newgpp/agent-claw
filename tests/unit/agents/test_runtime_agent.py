from pathlib import Path

from agents.base import AgentDescriptor
from agents.planning_routing import PlanningRoutingPolicy, StructuralPlanningRoutingPolicy
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

    async def run_planned(self, user_input: str, **kwargs) -> str:  # type: ignore[no-untyped-def]
        self.calls.append({"mode": "planned", "user_input": user_input, **kwargs})
        return self.result

    async def run_debug_planned(self, user_input: str, **kwargs) -> str:  # type: ignore[no-untyped-def]
        self.calls.append({"mode": "planned", "user_input": user_input, **kwargs})
        return self.result


class DemoRuntimeAgent(RuntimeAgent):
    descriptor = AgentDescriptor(name="demo-agent", description="Demo runtime agent.")


class StubPlanningRoutingPolicy(PlanningRoutingPolicy):
    def __init__(self, should_plan_result: bool) -> None:
        self.should_plan_result = should_plan_result
        self.calls: list[str] = []

    def should_plan(self, user_input: str) -> bool:
        self.calls.append(user_input)
        return self.should_plan_result


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

    assert runtime.calls[0]["mode"] == "planned"


def test_runtime_agent_uses_direct_runner_for_simple_auto_mode_requests(tmp_path: Path) -> None:
    runtime = StubRuntime(result="done")
    agent = DemoRuntimeAgent(
        runtime,
        config=AgentRunConfig(
            workspace_dir=tmp_path,
            planning=PlanningConfig(mode=PlanningMode.AUTO),
        ),
    )  # type: ignore[arg-type]

    import asyncio

    asyncio.run(agent.run("唐山今天天气怎么样"))

    assert "mode" not in runtime.calls[0]


def test_runtime_agent_uses_planned_runner_for_multi_step_auto_mode_requests(tmp_path: Path) -> None:
    runtime = StubRuntime(result="done")
    agent = DemoRuntimeAgent(
        runtime,
        config=AgentRunConfig(
            workspace_dir=tmp_path,
            planning=PlanningConfig(mode=PlanningMode.AUTO),
        ),
    )  # type: ignore[arg-type]

    import asyncio

    asyncio.run(agent.run("先查唐山天气，然后整理成一段说明。"))

    assert runtime.calls[0]["mode"] == "planned"


def test_runtime_agent_keeps_authoring_only_requests_direct_in_auto_mode(tmp_path: Path) -> None:
    runtime = StubRuntime(result="done")
    agent = DemoRuntimeAgent(
        runtime,
        config=AgentRunConfig(
            workspace_dir=tmp_path,
            planning=PlanningConfig(mode=PlanningMode.AUTO),
        ),
    )  # type: ignore[arg-type]

    import asyncio

    asyncio.run(agent.run("写一段关于春天的短文"))

    assert "mode" not in runtime.calls[0]


def test_runtime_agent_uses_injected_planning_routing_policy(tmp_path: Path) -> None:
    runtime = StubRuntime(result="done")
    policy = StubPlanningRoutingPolicy(should_plan_result=True)
    agent = DemoRuntimeAgent(
        runtime,
        config=AgentRunConfig(
            workspace_dir=tmp_path,
            planning=PlanningConfig(mode=PlanningMode.AUTO),
        ),
        planning_routing_policy=policy,
    )  # type: ignore[arg-type]

    import asyncio

    asyncio.run(agent.run("hello"))

    assert policy.calls == ["hello"]
    assert runtime.calls[0]["mode"] == "planned"


def test_runtime_agent_raises_clear_error_when_auto_planned_runner_is_missing(tmp_path: Path) -> None:
    class DirectOnlyRuntime(StubRuntime):
        run_planned = None  # type: ignore[assignment]

    runtime = DirectOnlyRuntime()
    agent = DemoRuntimeAgent(
        runtime,
        config=AgentRunConfig(
            workspace_dir=tmp_path,
            planning=PlanningConfig(mode=PlanningMode.AUTO),
        ),
    )  # type: ignore[arg-type]

    import asyncio

    try:
        asyncio.run(agent.run("先查天气，然后发给我"))
    except NotImplementedError as exc:
        assert "run_planned" in str(exc)
    else:
        raise AssertionError("Expected planning-enabled runtime to require run_planned().")


def test_structural_planning_routing_policy_detects_ordered_steps() -> None:
    policy = StructuralPlanningRoutingPolicy()

    assert policy.should_plan("First gather the weather, then summarize the result.")


def test_structural_planning_routing_policy_detects_bullet_lists() -> None:
    policy = StructuralPlanningRoutingPolicy()

    assert policy.should_plan("- collect sources\n- summarize findings")


def test_structural_planning_routing_policy_keeps_simple_single_request_direct() -> None:
    policy = StructuralPlanningRoutingPolicy()

    assert not policy.should_plan("写一段关于春天的短文")
