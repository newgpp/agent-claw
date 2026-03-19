"""Reusable runtime-backed agent base classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agents.base import AgentDescriptor, BaseAgent
from clawcore.runtime import ReActRuntime
from clawcore.skilling.models import SkillDefinition


@dataclass(frozen=True, slots=True)
class AgentRunConfig:
    """Default runtime configuration owned by an agent."""

    base_instructions: str = ""
    skills: tuple[SkillDefinition, ...] = field(default_factory=tuple)
    active_skill: SkillDefinition | None = None
    max_steps: int = 5
    workspace_dir: Path | None = None


class RuntimeAgent(BaseAgent):
    """Base class for business agents backed by the async runtime."""

    descriptor = AgentDescriptor(name="runtime-agent", description="Runtime-backed agent.")

    def __init__(self, runtime: ReActRuntime, *, config: AgentRunConfig | None = None) -> None:
        self.runtime = runtime
        self.config = config or AgentRunConfig()

    async def run(self, user_input: str, *, workspace_dir: Path | None = None) -> str:
        resolved_workspace = workspace_dir or self.config.workspace_dir
        return await self.runtime.run(
            user_input,
            skills=list(self.config.skills),
            active_skill=self.config.active_skill,
            max_steps=self.config.max_steps,
            base_instructions=self.config.base_instructions,
            workspace_dir=resolved_workspace,
        )
