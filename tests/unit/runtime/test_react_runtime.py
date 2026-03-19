import asyncio
from pathlib import Path

import pytest

from clawcore.llm.mock import MockLLM
from clawcore.models import ReActStep, ToolCall
from clawcore.runtime.session import AgentSession
from clawcore.runtime.react import ReActRuntime
from clawcore.skilling.models import SkillDefinition
from clawcore.tooling import ExecScriptTool, ReadTool, ToolExecutor, ToolPolicy, ToolRegistry, WriteTool


def build_tool_executor() -> ToolExecutor:
    registry = ToolRegistry()
    registry.register(ReadTool())
    registry.register(WriteTool())
    registry.register(ExecScriptTool())
    return ToolExecutor(registry, policy=ToolPolicy())


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
