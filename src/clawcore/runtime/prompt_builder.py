"""Helpers for building runtime system prompts."""

from __future__ import annotations

from dataclasses import dataclass

from clawcore.skilling.models import SkillDefinition


@dataclass(slots=True)
class SystemPromptBuilder:
    """Builds a minimal system prompt from skill and tool context."""

    def build(
        self,
        *,
        skills: list[SkillDefinition],
        tool_names: list[str],
        base_instructions: str = "",
    ) -> str:
        lines: list[str] = []
        if base_instructions.strip():
            lines.append(base_instructions.strip())
        if tool_names:
            lines.append(f"Available tools: {', '.join(sorted(tool_names))}")
        if skills:
            lines.append(f"Available skills: {', '.join(sorted(skill.name for skill in skills))}")
        return "\n".join(lines)
