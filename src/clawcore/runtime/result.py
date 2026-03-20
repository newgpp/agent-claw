"""Structured runtime results returned by debug execution paths."""

from __future__ import annotations

from dataclasses import dataclass

from clawcore.runtime.state import RuntimeState


@dataclass(slots=True)
class RuntimeRunResult:
    """Final answer plus captured runtime state for one completed run."""

    final_answer: str
    state: RuntimeState
