"""Built-in file reading tool."""

from __future__ import annotations

import asyncio
from pathlib import Path

from clawcore.tooling.base import BaseTool, ToolExecutionContext


class ReadTool(BaseTool):
    """Read text files from the workspace."""

    name = "read"
    description = "Read file contents from the workspace."
    risk_level = "low"

    async def execute(self, payload: dict[str, object], context: ToolExecutionContext) -> str:
        raw_path = str(payload.get("path", "")).strip()
        if not raw_path:
            raise ValueError("read requires a non-empty 'path'.")
        path = _resolve_workspace_path(context.workspace_dir, raw_path)
        return await asyncio.to_thread(path.read_text, encoding="utf-8")


def _resolve_workspace_path(workspace_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = workspace_dir / path
    return path.resolve()
