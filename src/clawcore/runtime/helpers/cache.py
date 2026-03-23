"""Helpers for runtime cache and tool call deduplication."""

from __future__ import annotations

import json
from pathlib import Path

from clawcore.runtime.state import RuntimeState


def action_signature(tool_name: str, payload: dict[str, object]) -> str:
    """Build a stable signature for one tool action."""
    return f"{tool_name}:{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"


def resolve_workspace_path(raw_path: str, workspace_dir: Path | None) -> Path:
    """Resolve a path relative to the runtime workspace when needed."""
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    base_dir = workspace_dir or Path.cwd()
    return (base_dir / candidate).resolve()


def cache_written_file(
    *,
    state: RuntimeState,
    action_name: str,
    action_payload: dict[str, object],
    workspace_dir: Path | None,
) -> None:
    """Cache content written by the write tool for later prompt reuse."""
    if action_name != "write":
        return
    raw_path = str(action_payload.get("path", "")).strip()
    content = action_payload.get("content")
    if not raw_path or not isinstance(content, str):
        return
    resolved_path = resolve_workspace_path(raw_path, workspace_dir)
    state.cached_files[str(resolved_path)] = content
    state.sync_views()
