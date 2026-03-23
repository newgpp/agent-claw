import asyncio
import json
from pathlib import Path

from clawcore.llm.mock import MockLLM, MockPlanner
from clawcore.models import ExecutionPlan, PlanSubgoal, ReActStep, ToolCall
from clawcore.runtime.session import AgentSession
from clawcore.runtime.react import ReActRuntime
from clawcore.tooling import CurlTool, ReadTool, ToolExecutor, ToolRegistry, WriteTool


def build_runtime(step_fn) -> ReActRuntime:  # type: ignore[no-untyped-def]
    registry = ToolRegistry()
    registry.register(ReadTool())
    registry.register(WriteTool())
    registry.register(CurlTool())
    executor = ToolExecutor(registry)
    return ReActRuntime(llm=MockLLM(step_fn), tool_executor=executor)


def build_planned_runtime(step_fn, plan_fn) -> ReActRuntime:  # type: ignore[no-untyped-def]
    registry = ToolRegistry()
    registry.register(ReadTool())
    registry.register(WriteTool())
    registry.register(CurlTool())
    executor = ToolExecutor(registry)
    return ReActRuntime(
        llm=MockLLM(step_fn),
        planner=MockPlanner(plan_fn),
        tool_executor=executor,
    )


def test_runtime_react_loop_matches_fixture_cases(tmp_path: Path) -> None:
    fixture_cases = json.loads(Path("tests/fixtures/runtime/react_cases.json").read_text(encoding="utf-8"))
    (tmp_path / "note.txt").write_text("fixture note", encoding="utf-8")
    for case in fixture_cases:
        mode = case["mode"]
        if mode == "direct":
            runtime = build_runtime(lambda session: ReActStep(thought="done", final_answer="direct answer"))
            assert asyncio.run(runtime.run("hi")) == "direct answer"
        elif mode == "read_once":
            async def read_once(session: AgentSession) -> ReActStep:
                if not session.state.scratchpad:
                    return ReActStep(thought="read", action=ToolCall(name="read", payload={"path": "note.txt"}))
                return ReActStep(thought="done", final_answer=session.state.scratchpad[-1])

            runtime = build_runtime(read_once)
            assert asyncio.run(runtime.run("read it", workspace_dir=tmp_path)) == "read: fixture note"
        elif mode == "planned":
            async def step_fn(session: AgentSession) -> ReActStep:
                if session.state.active_subgoal_id == "s1":
                    if not session.state.scratchpad:
                        return ReActStep(
                            thought="read weather",
                            action=ToolCall(name="read", payload={"path": "note.txt"}),
                        )
                    return ReActStep(thought="done weather", final_answer="weather ready")
                return ReActStep(thought="done draft", final_answer="email draft ready")

            def plan_fn(session: AgentSession) -> ExecutionPlan:
                return ExecutionPlan(
                    goal="Write a weather email",
                    subgoals=[
                        PlanSubgoal(id="s1", task="Fetch weather"),
                        PlanSubgoal(id="s2", task="Draft email"),
                    ],
                    success_criteria=["Weather fetched", "Email drafted"],
                )

            runtime = build_planned_runtime(step_fn, plan_fn)
            assert asyncio.run(runtime.run_planned("plan it", workspace_dir=tmp_path, max_steps=2)) == (
                "email draft ready"
            )


def test_runtime_planner_first_handles_empty_and_single_step_plans(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("fixture note", encoding="utf-8")

    direct_runtime = build_planned_runtime(
        lambda session: ReActStep(thought="unexpected", final_answer="unexpected"),
        lambda session: ExecutionPlan(goal="direct answer", subgoals=[]),
    )
    assert asyncio.run(direct_runtime.run_planner_first("hi", workspace_dir=tmp_path)) == "direct answer"

    async def single_step(session: AgentSession) -> ReActStep:
        if not session.state.scratchpad:
            return ReActStep(thought="read", action=ToolCall(name="read", payload={"path": "note.txt"}))
        return ReActStep(thought="done", final_answer="single-step answer")

    single_step_runtime = build_planned_runtime(
        single_step,
        lambda session: ExecutionPlan(
            goal="Read the note",
            subgoals=[PlanSubgoal(id="s1", task="Read the note file")],
        ),
    )
    assert (
        asyncio.run(single_step_runtime.run_planner_first("read it", workspace_dir=tmp_path, max_steps=2))
        == "single-step answer"
    )
