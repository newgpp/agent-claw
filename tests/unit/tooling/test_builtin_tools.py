import asyncio
from pathlib import Path

import pytest

from clawcore.skilling.models import SkillDefinition
from clawcore.tooling.base import ToolExecutionContext
from clawcore.tooling.builtin.exec_script import ExecScriptTool
from clawcore.tooling.builtin.read import ReadTool
from clawcore.tooling.builtin.write import WriteTool


def test_read_tool_reads_file_content(tmp_path: Path) -> None:
    file_path = tmp_path / "note.txt"
    file_path.write_text("hello", encoding="utf-8")

    tool = ReadTool()
    result = asyncio.run(
        tool.execute({"path": "note.txt"}, ToolExecutionContext(workspace_dir=tmp_path))
    )

    assert result == "hello"


def test_write_tool_writes_file_content(tmp_path: Path) -> None:
    tool = WriteTool()

    result = asyncio.run(
        tool.execute(
            {"path": "output.txt", "content": "written"},
            ToolExecutionContext(workspace_dir=tmp_path),
        )
    )

    assert "Wrote" in result
    assert (tmp_path / "output.txt").read_text(encoding="utf-8") == "written"


def test_exec_script_tool_blocks_undeclared_scripts(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    active_skill = SkillDefinition(
        name="demo",
        description="Demo skill",
        directory=skill_dir,
        skill_file=skill_dir / "SKILL.md",
        scripts=["scripts/allowed.py"],
    )
    tool = ExecScriptTool()

    with pytest.raises(PermissionError, match="not declared by active skill"):
        asyncio.run(
            tool.execute(
                {"script": "scripts/other.py"},
                ToolExecutionContext(workspace_dir=tmp_path, active_skill=active_skill),
            )
        )


def test_exec_script_tool_runs_declared_script(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "demo"
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    script_path = scripts_dir / "hello.py"
    script_path.write_text("print('hello from script')\n", encoding="utf-8")
    active_skill = SkillDefinition(
        name="demo",
        description="Demo skill",
        directory=skill_dir,
        skill_file=skill_dir / "SKILL.md",
        scripts=["scripts/hello.py"],
    )
    tool = ExecScriptTool()

    result = asyncio.run(
        tool.execute(
            {"script": "scripts/hello.py"},
            ToolExecutionContext(workspace_dir=tmp_path, active_skill=active_skill),
        )
    )

    assert result == "hello from script"
