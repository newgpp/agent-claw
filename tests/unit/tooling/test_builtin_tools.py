import asyncio
from pathlib import Path

import pytest

from clawcore.skilling.models import SkillDefinition
from clawcore.tooling.base import ToolExecutionContext
from clawcore.tooling.builtin.curl import CurlTool
from clawcore.tooling.builtin.read import ReadTool
from clawcore.tooling.builtin.read_skill import ReadSkillTool
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


def test_read_skill_tool_reads_declared_skill_markdown(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("# Demo Skill\n\nUse this skill for testing.\n", encoding="utf-8")
    skill = SkillDefinition(
        name="demo",
        description="Demo skill",
        directory=skill_dir,
        skill_file=skill_file,
    )
    tool = ReadSkillTool()

    result = asyncio.run(
        tool.execute(
            {"skill": "demo"},
            ToolExecutionContext(workspace_dir=tmp_path, available_skills=(skill,)),
        )
    )

    assert "Use this skill for testing." in result


def test_curl_tool_rejects_missing_url(tmp_path: Path) -> None:
    tool = CurlTool()

    with pytest.raises(ValueError, match="non-empty 'url'"):
        asyncio.run(tool.execute({}, ToolExecutionContext(workspace_dir=tmp_path)))


def test_curl_tool_rejects_invalid_max_time(tmp_path: Path) -> None:
    tool = CurlTool()

    with pytest.raises(ValueError, match="positive integer"):
        asyncio.run(
            tool.execute(
                {"url": "https://example.com", "max_time": 0},
                ToolExecutionContext(workspace_dir=tmp_path),
            )
        )


def test_curl_tool_runs_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tool = CurlTool()

    class FakeProcess:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return (b"ok", b"")

    recorded: dict[str, object] = {}

    async def fake_create_subprocess_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
        recorded["args"] = args
        recorded["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr("clawcore.tooling.builtin.curl.asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    result = asyncio.run(
        tool.execute(
            {
                "url": "example.com",
                "method": "post",
                "headers": {"X-Test": "1"},
                "data": "hello",
                "max_time": 5,
            },
            ToolExecutionContext(workspace_dir=tmp_path),
        )
    )

    assert result == "ok"
    assert recorded["args"] == (
        "curl",
        "-s",
        "-L",
        "-X",
        "POST",
        "-H",
        "X-Test: 1",
        "--data",
        "hello",
        "--max-time",
        "5",
        "https://example.com",
    )
