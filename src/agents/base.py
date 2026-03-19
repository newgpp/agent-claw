"""Base abstractions for business agents."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """Common interface for app-level agents."""

    @abstractmethod
    async def run(self, user_input: str) -> str:
        """Run the agent for a single user input."""
