"""Runtime event models shared across the system."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class RuntimeEvent:
    """Base event emitted by the runtime."""

    event_type: str
    run_id: str
    session_id: str
    trace_id: str
    payload: dict[str, object] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        """Serialize the event into a predictable dictionary."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass(slots=True)
class RunStarted(RuntimeEvent):
    """Event emitted when a run begins."""

    event_type: str = field(init=False, default="run.started")


@dataclass(slots=True)
class ToolCalled(RuntimeEvent):
    """Event emitted before a tool is executed."""

    event_type: str = field(init=False, default="tool.called")


@dataclass(slots=True)
class ToolReturned(RuntimeEvent):
    """Event emitted after a tool returns."""

    event_type: str = field(init=False, default="tool.returned")


@dataclass(slots=True)
class RunFinished(RuntimeEvent):
    """Event emitted when a run completes."""

    event_type: str = field(init=False, default="run.finished")
