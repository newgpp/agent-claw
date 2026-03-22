import asyncio
from pathlib import Path

import pytest

from clawcore.llm.mock import MockLLM, MockPlanner
from clawcore.models import ExecutionPlan, PlanStatus, PlanSubgoal, ReActStep, ToolCall
from clawcore.runtime.session import AgentSession
from clawcore.runtime.react import ReActRuntime
from clawcore.skilling.models import SkillDefinition
from clawcore.tooling import ExecScriptTool, ReadTool, ToolExecutor, ToolPolicy, ToolRegistry, WriteTool
from clawcore.tooling.base import ToolExecutionContext
from common.observability import current_observability_context


def build_tool_executor() -> ToolExecutor:
    registry = ToolRegistry()
    registry.register(ReadTool())
    registry.register(WriteTool())
    registry.register(ExecScriptTool())
    return ToolExecutor(registry, policy=ToolPolicy())


def build_planned_runtime(step_fn, plan_fn) -> ReActRuntime:  # type: ignore[no-untyped-def]
    return ReActRuntime(
        llm=MockLLM(step_fn),
        planner=MockPlanner(plan_fn),
        tool_executor=build_tool_executor(),
    )


def test_runtime_completes_no_tool_turn() -> None:
    llm = MockLLM(lambda session: ReActStep(thought="done", final_answer="hello"))
    runtime = ReActRuntime(llm=llm, tool_executor=build_tool_executor())

    result = asyncio.run(runtime.run("hi"))

    assert result == "hello"


def test_runtime_completes_single_tool_turn(tmp_path: Path) -> None:
    async def step_fn(session: AgentSession) -> ReActStep:
        if not session.state.scratchpad:
            return ReActStep(
                thought="read file",
                action=ToolCall(name="read", payload={"path": "note.txt"}),
            )
        return ReActStep(thought="done", final_answer=session.state.scratchpad[-1])

    (tmp_path / "note.txt").write_text("runtime text", encoding="utf-8")

    runtime = ReActRuntime(llm=MockLLM(step_fn), tool_executor=build_tool_executor())
    result = asyncio.run(runtime.run("read it", workspace_dir=tmp_path))

    assert result == "read: runtime text"


def test_runtime_run_debug_returns_final_answer_and_state(tmp_path: Path) -> None:
    async def step_fn(session: AgentSession) -> ReActStep:
        if not session.state.scratchpad:
            return ReActStep(
                thought="read file",
                action=ToolCall(name="read", payload={"path": "note.txt"}),
            )
        return ReActStep(thought="done", final_answer=session.state.scratchpad[-1])

    (tmp_path / "note.txt").write_text("runtime text", encoding="utf-8")

    runtime = ReActRuntime(llm=MockLLM(step_fn), tool_executor=build_tool_executor())
    result = asyncio.run(runtime.run_debug("read it", workspace_dir=tmp_path))

    assert result.final_answer == "read: runtime text"
    assert result.state.scratchpad == ["read: runtime text"]
    assert result.state.tool_results[0].name == "read"
    assert result.state.events[-1].event_type == "run.finished"
    assert result.state.trace.events[-1].kind == "final_answer"


def test_runtime_binds_and_resets_observability_context() -> None:
    seen_contexts: list[dict[str, str]] = []

    async def step_fn(session: AgentSession) -> ReActStep:
        seen_contexts.append(current_observability_context())
        return ReActStep(thought="done", final_answer="hello")

    runtime = ReActRuntime(llm=MockLLM(step_fn), tool_executor=build_tool_executor())

    result = asyncio.run(runtime.run_debug("trace me"))

    assert result.final_answer == "hello"
    assert len(seen_contexts) == 1
    assert seen_contexts[0]["run_id"] == result.state.events[0].run_id
    assert seen_contexts[0]["session_id"] == result.state.events[0].session_id
    assert seen_contexts[0]["trace_id"] == result.state.events[0].trace_id
    assert current_observability_context() == {
        "run_id": "-",
        "session_id": "-",
        "trace_id": "-",
    }


def test_runtime_stops_on_max_steps() -> None:
    llm = MockLLM(lambda session: ReActStep(thought="loop", action=ToolCall(name="read", payload={})))
    runtime = ReActRuntime(llm=llm, tool_executor=build_tool_executor())

    with pytest.raises(RuntimeError):
        asyncio.run(runtime.run("loop", max_steps=1))


def test_runtime_enforces_active_skill_for_exec_script(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "release-checker"
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "release_check.py").write_text("print('ok')\n", encoding="utf-8")
    active_skill = SkillDefinition(
        name="release-checker",
        description="Check release steps.",
        directory=skill_dir,
        skill_file=skill_dir / "SKILL.md",
        scripts=["scripts/release_check.py"],
    )
    def step_fn(session: AgentSession) -> ReActStep:
        if not session.state.scratchpad:
            return ReActStep(
                thought="run script",
                action=ToolCall(name="exec_script", payload={"script": "scripts/release_check.py"}),
            )
        return ReActStep(thought="done", final_answer=session.state.scratchpad[-1])

    llm = MockLLM(step_fn)
    runtime = ReActRuntime(llm=llm, tool_executor=build_tool_executor())

    result = asyncio.run(runtime.run("run", active_skill=active_skill, workspace_dir=tmp_path))

    assert result == "exec_script: ok"


def test_runtime_blocks_undeclared_script_execution(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "release-checker"
    skill_dir.mkdir(parents=True)
    (skill_dir / "scripts").mkdir()
    active_skill = SkillDefinition(
        name="release-checker",
        description="Check release steps.",
        directory=skill_dir,
        skill_file=skill_dir / "SKILL.md",
        scripts=[],
    )
    llm = MockLLM(
        lambda session: ReActStep(
            thought="run undeclared script",
            action=ToolCall(name="exec_script", payload={"script": "scripts/release_check.py"}),
        )
    )
    runtime = ReActRuntime(llm=llm, tool_executor=build_tool_executor())

    with pytest.raises(RuntimeError, match="not declared"):
        asyncio.run(runtime.run("run", active_skill=active_skill, workspace_dir=tmp_path, max_steps=1))


def test_runtime_promotes_active_skill_after_read_skill(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "file-summary"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("# File Summary\n\nSummarize a workspace file.\n", encoding="utf-8")
    skill = SkillDefinition(
        name="file-summary",
        description="Summarize files.",
        directory=skill_dir,
        skill_file=skill_file,
    )
    registry = ToolRegistry()
    from clawcore.tooling import ReadSkillTool

    registry.register(ReadSkillTool())
    executor = ToolExecutor(registry, policy=ToolPolicy())

    def step_fn(session: AgentSession) -> ReActStep:
        if session.state.active_skill is None:
            return ReActStep(
                thought="Load the skill first.",
                action=ToolCall(name="read_skill", payload={"skill": "file-summary"}),
            )
        return ReActStep(thought="done", final_answer=session.state.active_skill.name)

    runtime = ReActRuntime(llm=MockLLM(step_fn), tool_executor=executor)

    result = asyncio.run(runtime.run("summarize", skills=[skill], workspace_dir=tmp_path))

    assert result == "file-summary"


def test_runtime_summarizes_read_skill_observation(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "weather"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "---\n"
        'name: weather\n'
        'description: "Get current weather and forecasts for a location."\n'
        "---\n\n"
        "# Weather Skill\n\n"
        "Use this skill when the user asks about current weather or a forecast for a city.\n\n"
        "Always include a location in the weather query.\n\n"
        "```bash\n"
        'curl "wttr.in/Hong+Kong?format=3"\n'
        "```\n",
        encoding="utf-8",
    )
    skill = SkillDefinition(
        name="weather",
        description="Get current weather and forecasts for a location.",
        directory=skill_dir,
        skill_file=skill_file,
    )
    registry = ToolRegistry()
    from clawcore.tooling import ReadSkillTool

    registry.register(ReadSkillTool())
    executor = ToolExecutor(registry, policy=ToolPolicy())

    def step_fn(session: AgentSession) -> ReActStep:
        if not session.state.scratchpad:
            return ReActStep(
                thought="Load the weather skill first.",
                action=ToolCall(name="read_skill", payload={"skill": "weather"}),
            )
        return ReActStep(thought="done", final_answer=session.state.scratchpad[-1])

    runtime = ReActRuntime(llm=MockLLM(step_fn), tool_executor=executor)

    result = asyncio.run(runtime.run("weather", skills=[skill], workspace_dir=tmp_path))

    assert "read_skill_summary:" in result
    assert '"skill_name": "weather"' in result
    assert '"summary": ["Get current weather and forecasts for a location."' in result
    assert '"recommended_tools": ["curl"]' in result
    assert '"command_examples": ["curl \\"wttr.in/Hong+Kong?format=3\\""' in result
    assert '"call_hint": "curl \\"wttr.in/Hong+Kong?format=3\\""' in result
    assert "# Weather Skill" not in result
    assert "Always include a location in the weather query." in result


def test_runtime_promotes_active_skill_after_read_skill_name_alias(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "file-summary"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("# File Summary\n\nSummarize a workspace file.\n", encoding="utf-8")
    skill = SkillDefinition(
        name="file-summary",
        description="Summarize files.",
        directory=skill_dir,
        skill_file=skill_file,
    )
    registry = ToolRegistry()
    from clawcore.tooling import ReadSkillTool

    registry.register(ReadSkillTool())
    executor = ToolExecutor(registry, policy=ToolPolicy())

    def step_fn(session: AgentSession) -> ReActStep:
        if session.state.active_skill is None:
            return ReActStep(
                thought="Load the skill first.",
                action=ToolCall(name="read_skill", payload={"skill_name": "file-summary"}),
            )
        return ReActStep(thought="done", final_answer=session.state.active_skill.name)

    runtime = ReActRuntime(llm=MockLLM(step_fn), tool_executor=executor)

    result = asyncio.run(runtime.run("summarize", skills=[skill], workspace_dir=tmp_path))

    assert result == "file-summary"


def test_runtime_can_load_multiple_skills_in_one_run(tmp_path: Path) -> None:
    first_dir = tmp_path / "skills" / "file-summary"
    first_dir.mkdir(parents=True)
    first_file = first_dir / "SKILL.md"
    first_file.write_text("# File Summary\n\nSummarize a workspace file.\n", encoding="utf-8")
    first_skill = SkillDefinition(
        name="file-summary",
        description="Summarize files.",
        directory=first_dir,
        skill_file=first_file,
    )
    second_dir = tmp_path / "skills" / "release-checker"
    second_dir.mkdir(parents=True)
    second_file = second_dir / "SKILL.md"
    second_file.write_text("# Release Checker\n\nValidate release readiness.\n", encoding="utf-8")
    second_skill = SkillDefinition(
        name="release-checker",
        description="Validate release steps.",
        directory=second_dir,
        skill_file=second_file,
    )
    loaded_names: list[str] = []
    registry = ToolRegistry()
    from clawcore.tooling import ReadSkillTool

    registry.register(ReadSkillTool())
    executor = ToolExecutor(registry, policy=ToolPolicy())

    def step_fn(session: AgentSession) -> ReActStep:
        loaded_names[:] = [skill.name for skill in session.state.loaded_skills]
        if not session.state.loaded_skills:
            return ReActStep(
                thought="Load the first skill.",
                action=ToolCall(name="read_skill", payload={"skill": "file-summary"}),
            )
        if len(session.state.loaded_skills) == 1:
            return ReActStep(
                thought="Load the second skill as well.",
                action=ToolCall(name="read_skill", payload={"skill": "release-checker"}),
            )
        return ReActStep(
            thought="I have both skills loaded.",
            final_answer=",".join(skill.name for skill in session.state.loaded_skills),
        )

    runtime = ReActRuntime(llm=MockLLM(step_fn), tool_executor=executor)

    result = asyncio.run(
        runtime.run("load both", skills=[first_skill, second_skill], workspace_dir=tmp_path, max_steps=4)
    )

    assert loaded_names == ["file-summary", "release-checker"]
    assert result == "file-summary,release-checker"


def test_runtime_avoids_duplicate_tool_calls(tmp_path: Path) -> None:
    class CountingReadTool(ReadTool):
        calls = 0

        async def execute(self, payload: dict[str, object], context: ToolExecutionContext) -> str:
            type(self).calls += 1
            return await super().execute(payload, context)

    registry = ToolRegistry()
    registry.register(CountingReadTool())
    executor = ToolExecutor(registry, policy=ToolPolicy())
    (tmp_path / "note.txt").write_text("runtime text", encoding="utf-8")

    def step_fn(session: AgentSession) -> ReActStep:
        if len(session.state.scratchpad) < 2:
            return ReActStep(
                thought="read file",
                action=ToolCall(name="read", payload={"path": "note.txt"}),
            )
        return ReActStep(thought="done", final_answer=session.state.scratchpad[-1])

    runtime = ReActRuntime(llm=MockLLM(step_fn), tool_executor=executor)
    result = asyncio.run(runtime.run("read it", workspace_dir=tmp_path, max_steps=3))

    assert CountingReadTool.calls == 1
    assert "Duplicate tool call avoided" in result


def test_runtime_executes_planned_subgoals_in_order(tmp_path: Path) -> None:
    (tmp_path / "weather.txt").write_text("Hong Kong 26C", encoding="utf-8")

    def plan_fn(session: AgentSession) -> ExecutionPlan:
        return ExecutionPlan(
            goal="Write and send a weather update",
            subgoals=[
                PlanSubgoal(id="s1", task="Fetch the weather"),
                PlanSubgoal(id="s2", task="Draft the message"),
            ],
            success_criteria=["Weather is fetched", "Draft is written"],
        )

    def step_fn(session: AgentSession) -> ReActStep:
        if session.state.active_subgoal_id == "s1":
            if not session.state.scratchpad:
                return ReActStep(
                    thought="Read the weather file.",
                    action=ToolCall(name="read", payload={"path": "weather.txt"}),
                )
            return ReActStep(thought="Weather captured.", final_answer="weather summary ready")
        if session.state.active_subgoal_id == "s2":
            return ReActStep(
                thought="Draft from the weather artifact.",
                final_answer="email draft: bring an umbrella",
            )
        return ReActStep(thought="fallback", final_answer="done")

    runtime = build_planned_runtime(step_fn, plan_fn)

    result = asyncio.run(runtime.run_planned("prepare update", workspace_dir=tmp_path, max_steps=2))

    assert result == "email draft: bring an umbrella"


def test_runtime_run_debug_planned_returns_plan_and_artifacts(tmp_path: Path) -> None:
    (tmp_path / "weather.txt").write_text("Hong Kong 26C", encoding="utf-8")

    def plan_fn(session: AgentSession) -> ExecutionPlan:
        return ExecutionPlan(
            goal="Write and send a weather update",
            subgoals=[
                PlanSubgoal(id="s1", task="Fetch the weather"),
                PlanSubgoal(id="s2", task="Draft the message"),
            ],
            success_criteria=["Weather is fetched", "Draft is written"],
        )

    def step_fn(session: AgentSession) -> ReActStep:
        if session.state.active_subgoal_id == "s1":
            if not session.state.scratchpad:
                return ReActStep(
                    thought="Read the weather file.",
                    action=ToolCall(name="read", payload={"path": "weather.txt"}),
                )
            return ReActStep(thought="Weather captured.", final_answer="weather summary ready")
        return ReActStep(thought="Draft from artifact.", final_answer="email draft: bring an umbrella")

    runtime = build_planned_runtime(step_fn, plan_fn)

    result = asyncio.run(runtime.run_debug_planned("prepare update", workspace_dir=tmp_path, max_steps=2))

    assert result.final_answer == "email draft: bring an umbrella"
    assert result.state.plan is not None
    assert result.state.plan.goal == "Write and send a weather update"
    assert result.state.plan.status == PlanStatus.COMPLETED
    assert [subgoal.status for subgoal in result.state.plan.subgoals] == [
        PlanStatus.COMPLETED,
        PlanStatus.COMPLETED,
    ]
    assert [artifact.name for artifact in result.state.artifacts] == ["s1", "s2"]
    assert result.state.trace.events[1].kind == "plan"


def test_runtime_planned_mode_requires_planner() -> None:
    runtime = ReActRuntime(llm=MockLLM(lambda session: ReActStep(thought="done", final_answer="hello")), tool_executor=build_tool_executor())

    with pytest.raises(NotImplementedError, match="configured planner"):
        asyncio.run(runtime.run_planned("hello"))
