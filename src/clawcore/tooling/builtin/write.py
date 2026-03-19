"""Built-in file writing tool."""

from __future__ import annotations

import asyncio
from pathlib import Path

from clawcore.tooling.base import BaseTool, ToolExecutionContext


class WriteTool(BaseTool):
    """Write text files into the workspace."""

    name = "write"
    description = "Write file contents into the workspace."
    risk_level = "medium"

    async def execute(self, payload: dict[str, object], context: ToolExecutionContext) -> str:
        raw_path = str(payload.get("path", "")).strip()
        if not raw_path:
            raise ValueError("write requires a non-empty 'path'.")
        if "content" not in payload:
            raise ValueError("write requires 'content'.")
        content = str(payload["content"])
        path = _resolve_workspace_path(context.workspace_dir, raw_path)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_text, content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"


def _resolve_workspace_path(workspace_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = workspace_dir / path
    return path.resolve()
