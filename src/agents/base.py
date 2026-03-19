"""Base abstractions for business agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AgentDescriptor:
    """Human-readable metadata describing an agent."""

    name: str
    description: str


class BaseAgent(ABC):
    """Common interface for app-level agents."""

    descriptor = AgentDescriptor(name="base-agent", description="Base agent.")

    @property
    def name(self) -> str:
        """Return the stable agent name."""
        return self.descriptor.name

    @property
    def description(self) -> str:
        """Return the human-readable agent description."""
        return self.descriptor.description

    @abstractmethod
    async def run(self, user_input: str, *, workspace_dir: Path | None = None) -> str:
        """Run the agent for a single user input."""
