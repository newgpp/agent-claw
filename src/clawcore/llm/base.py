"""Base protocol for runtime-facing LLM clients."""

from __future__ import annotations

from abc import ABC, abstractmethod

from clawcore.models import ReActStep
from clawcore.runtime.session import AgentSession


class BaseLLM(ABC):
    """Abstract async LLM interface used by the runtime."""

    @abstractmethod
    async def next_step(self, session: AgentSession) -> ReActStep:
        """Return the next runtime step for the current session."""
