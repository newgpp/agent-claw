"""Helpers for simple fast-path subgoal completion."""

from __future__ import annotations

from collections.abc import Iterable

from clawcore.runtime.state import RuntimeState


def try_fast_path_completion(
    *,
    state: RuntimeState,
    tool_name: str,
    result_content: str,
) -> str | None:
    """Return an immediate subgoal handoff when one tool already satisfies the task."""
    task = (state.active_subgoal_task or "").strip()
    if not task:
        return None

    expected_tools = infer_expected_tools_for_task(task)
    if len(expected_tools) != 1 or tool_name not in expected_tools:
        return None

    if tool_name == "read_skill":
        return None

    subgoal_id = state.active_subgoal_id or "subgoal"
    return (
        f"Subgoal {subgoal_id} completed: "
        f"{build_fast_path_summary(tool_name=tool_name, result_content=result_content)}"
    )


def infer_expected_tools_for_task(task: str) -> set[str]:
    """Infer builtin tool names explicitly suggested by a subgoal sentence."""
    lower_task = task.lower()
    expected: set[str] = set()
    explicit_tool_aliases: dict[str, Iterable[str]] = {
        "curl": ("curl",),
        "read_skill": ("read_skill",),
        "read": ("read ", "read the", "read file"),
        "write": ("write ", "write it to a file", "write to a file", "save to a file"),
    }
    for tool_name, aliases in explicit_tool_aliases.items():
        if any(alias in lower_task for alias in aliases):
            expected.add(tool_name)
    return expected


def build_fast_path_summary(*, tool_name: str, result_content: str) -> str:
    """Build a concise summary for fast-path completion."""
    return _summarize_for_prompt(result_content)


def _summarize_for_prompt(value: str, *, limit: int = 280) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."
