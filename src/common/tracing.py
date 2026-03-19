"""Simple trace event collection for agent execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class TraceEvent:
    """A lightweight runtime event."""

    kind: str
    message: str
    data: dict[str, object] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        """Serialize the event into a predictable dictionary."""
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


@dataclass(slots=True)
class TraceCollector:
    """In-memory event collector used by the runtime."""

    events: list[TraceEvent] = field(default_factory=list)

    def record(self, kind: str, message: str, **data: object) -> None:
        self.events.append(TraceEvent(kind=kind, message=message, data=data))
