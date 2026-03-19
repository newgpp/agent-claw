import asyncio

import pytest

from clawcore.tooling.base import BaseTool, ToolExecutionContext
from clawcore.tooling.registry import ToolRegistry


class EchoTool(BaseTool):
    name = "echo"

    async def execute(self, payload: dict[str, object], context: ToolExecutionContext) -> str:
        return str(payload.get("text", ""))


def test_registry_can_register_and_run_tool() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())

    assert asyncio.run(registry.run("echo", {"text": "hello"})) == "hello"
    assert registry.names() == ["echo"]


def test_registry_rejects_duplicate_tool_names() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())

    with pytest.raises(ValueError, match="already registered"):
        registry.register(EchoTool())
