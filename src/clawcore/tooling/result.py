"""Structured results for tool execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ToolExecutionStatus(StrEnum):
    """High-level result status for tool execution."""

    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"


@dataclass(slots=True)
class ToolExecutionResult:
    """Normalized outcome for any tool execution."""

    tool_name: str
    status: ToolExecutionStatus
    content: str
