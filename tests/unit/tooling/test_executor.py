import asyncio

from clawcore.tooling.base import BaseTool, ToolExecutionContext
from clawcore.tooling.executor import ToolExecutor
from clawcore.tooling.registry import ToolRegistry
from clawcore.tooling.result import ToolExecutionStatus


class EchoTool(BaseTool):
    name = "echo"

    async def execute(self, payload: dict[str, object], context: ToolExecutionContext) -> str:
        return str(payload.get("text", ""))


class FailingTool(BaseTool):
    name = "fail"

    async def execute(self, payload: dict[str, object], context: ToolExecutionContext) -> str:
        raise RuntimeError("boom")


def test_executor_returns_success_result() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    executor = ToolExecutor(registry)

    result = asyncio.run(executor.execute("echo", {"text": "hello"}))

    assert result.status == ToolExecutionStatus.SUCCESS
    assert result.content == "hello"


def test_executor_returns_blocked_result() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    executor = ToolExecutor(registry, deny={"echo"})

    result = asyncio.run(executor.execute("echo", {"text": "hello"}))

    assert result.status == ToolExecutionStatus.BLOCKED


def test_executor_returns_error_result() -> None:
    registry = ToolRegistry()
    registry.register(FailingTool())
    executor = ToolExecutor(registry)

    result = asyncio.run(executor.execute("fail", {}))

    assert result.status == ToolExecutionStatus.ERROR
    assert result.content == "boom"
