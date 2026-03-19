"""Session wrapper for runtime state and history."""

from __future__ import annotations

from dataclasses import dataclass, field

from clawcore.runtime.state import RuntimeState


@dataclass(slots=True)
class AgentSession:
    """A lightweight session storing runtime state and text history."""

    state: RuntimeState
    history: list[str] = field(default_factory=list)

    def append_observation(self, observation: str) -> None:
        self.history.append(observation)
        self.state.scratchpad.append(observation)
