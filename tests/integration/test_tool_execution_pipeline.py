import asyncio
import json
from pathlib import Path

from clawcore.skilling.models import SkillDefinition
from clawcore.tooling import CurlTool, ReadTool, ToolExecutionContext, ToolExecutor, ToolRegistry, WriteTool
from clawcore.tooling.result import ToolExecutionStatus


def test_tool_execution_pipeline_matches_fixture_cases(tmp_path: Path) -> None:
    fixture_path = Path("tests/fixtures/tools/cases.json")
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))

    active_skill = SkillDefinition(
        name="release-checker",
        description="Check release readiness.",
        directory=tmp_path / "skills" / "release-checker",
        skill_file=tmp_path / "skills" / "release-checker" / "SKILL.md",
    )

    registry = ToolRegistry()
    registry.register(ReadTool())
    registry.register(WriteTool())
    registry.register(CurlTool())
    executor = ToolExecutor(registry, deny={"blocked_tool"})

    read_target = tmp_path / "input.txt"
    read_target.write_text("input text", encoding="utf-8")

    for case in cases:
        name = case["name"]
        tool_name = case["tool"]
        payload = dict(case["payload"])
        if payload.get("path") == "$TMP_READ_FILE":
            payload["path"] = str(read_target)
        context = ToolExecutionContext(workspace_dir=tmp_path, active_skill=active_skill)

        if tool_name == "blocked_tool":
            result = asyncio.run(executor.execute("read", payload, context=context))
        else:
            result = asyncio.run(executor.execute(tool_name, payload, context=context))

        if name == "read success":
            assert result.status == ToolExecutionStatus.SUCCESS
            assert result.content == "input text"
        elif name == "write success":
            assert result.status == ToolExecutionStatus.SUCCESS
            assert (tmp_path / "written.txt").read_text(encoding="utf-8") == "hello write"
        elif name == "invalid input":
            assert result.status == ToolExecutionStatus.ERROR
        elif name == "blocked tool":
            blocked_executor = ToolExecutor(registry, deny={"read"})
            blocked_result = asyncio.run(blocked_executor.execute("read", payload, context=context))
            assert blocked_result.status == ToolExecutionStatus.BLOCKED
