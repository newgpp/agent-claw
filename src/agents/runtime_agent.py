"""Reusable runtime-backed agent base classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
import re

from agents.base import AgentDescriptor, BaseAgent
from clawcore.runtime import ReActRuntime, RuntimeRunResult
from clawcore.skilling.models import SkillDefinition


class PlanningMode(StrEnum):
    """Planning strategy for a runtime-backed agent."""

    DISABLED = "disabled"
    AUTO = "auto"
    ALWAYS = "always"


@dataclass(frozen=True, slots=True)
class PlanningConfig:
    """Configuration for direct vs planned execution."""

    mode: PlanningMode = PlanningMode.DISABLED


@dataclass(frozen=True, slots=True)
class AgentRunConfig:
    """Default runtime configuration owned by an agent."""

    base_instructions: str = ""
    skills: tuple[SkillDefinition, ...] = field(default_factory=tuple)
    active_skill: SkillDefinition | None = None
    max_steps: int = 5
    workspace_dir: Path | None = None
    planning: PlanningConfig = field(default_factory=PlanningConfig)


class RuntimeAgent(BaseAgent):
    """Base class for business agents backed by the async runtime."""

    descriptor = AgentDescriptor(name="runtime-agent", description="Runtime-backed agent.")

    def __init__(self, runtime: ReActRuntime, *, config: AgentRunConfig | None = None) -> None:
        self.runtime = runtime
        self.config = config or AgentRunConfig()

    async def run(self, user_input: str, *, workspace_dir: Path | None = None) -> str:
        resolved_workspace = workspace_dir or self.config.workspace_dir
        runner = self._resolve_runner("run", user_input)
        return await runner(
            user_input,
            skills=list(self.config.skills),
            active_skill=self.config.active_skill,
            max_steps=self.config.max_steps,
            base_instructions=self.config.base_instructions,
            workspace_dir=resolved_workspace,
        )

    async def run_debug(
        self, user_input: str, *, workspace_dir: Path | None = None
    ) -> RuntimeRunResult:
        resolved_workspace = workspace_dir or self.config.workspace_dir
        runner = self._resolve_runner("run_debug", user_input)
        return await runner(
            user_input,
            skills=list(self.config.skills),
            active_skill=self.config.active_skill,
            max_steps=self.config.max_steps,
            base_instructions=self.config.base_instructions,
            workspace_dir=resolved_workspace,
        )

    def _resolve_runner(self, method_name: str, user_input: str):
        if self.config.planning.mode == PlanningMode.DISABLED:
            return getattr(self.runtime, method_name)
        if self.config.planning.mode == PlanningMode.AUTO and not self._should_plan(user_input):
            return getattr(self.runtime, method_name)

        planned_method_name = f"{method_name}_planned"
        planned_runner = getattr(self.runtime, planned_method_name, None)
        if planned_runner is None:
            raise NotImplementedError(
                f"Planning mode '{self.config.planning.mode}' requires runtime method "
                f"'{planned_method_name}()'."
            )
        return planned_runner

    def _should_plan(self, user_input: str) -> bool:
        text = user_input.strip().lower()
        if not text:
            return False

        delivery_markers = (
            "发送",
            "发到",
            "发给",
            "邮件",
            "email",
            "mail",
            "send",
        )
        if any(marker in text for marker in delivery_markers):
            return True

        authoring_markers = (
            "写一篇",
            "写封",
            "撰写",
            "write",
            "draft",
        )
        research_markers = (
            "整理",
            "汇总",
            "分析",
            "研究",
            "对比",
            "总结",
            "report",
            "summarize",
            "analyse",
            "analyze",
            "research",
        )
        has_authoring = any(marker in text for marker in authoring_markers)
        has_research = any(marker in text for marker in research_markers)

        if has_authoring and has_research:
            return True

        multi_step_patterns = (
            r"(并|然后|再|之后).*(发送|发给|邮件|写|总结|分析)",
            r"(and then|then|and)\s+(send|email|write|draft|summarize|analyze)",
        )
        if any(re.search(pattern, text) for pattern in multi_step_patterns):
            return True

        return False
