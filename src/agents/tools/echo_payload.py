"""Example agent-owned tool discovered by the JSON factory."""

from __future__ import annotations

from clawcore.tooling import BaseTool, ToolExecutionContext


class EchoPayloadTool(BaseTool):
    """Return a text payload unchanged."""

    name = "echo_payload"
    description = "Echo back a text payload."

    async def execute(self, payload: dict[str, object], context: ToolExecutionContext) -> str:
        return str(payload.get("text", ""))
