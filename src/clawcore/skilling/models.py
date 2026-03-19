"""Data models for skill definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class SkillDefinition:
    """A runtime-ready skill definition loaded from disk."""

    name: str
    description: str
    directory: Path
    skill_file: Path
    tools: list[str] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @property
    def location(self) -> str:
        """Return the canonical prompt-facing skill file path."""
        return str(self.skill_file)
