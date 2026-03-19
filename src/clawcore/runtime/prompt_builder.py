"""Helpers for building runtime system prompts."""

from __future__ import annotations

from dataclasses import dataclass

from clawcore.skilling.models import SkillDefinition
from clawcore.skilling.prompt import build_skills_prompt


@dataclass(slots=True)
class SystemPromptBuilder:
    """Builds a minimal system prompt from skill and tool context."""

    def build(
        self,
        *,
        skills: list[SkillDefinition],
        tool_names: list[str],
        tool_descriptions: dict[str, str] | None = None,
        base_instructions: str = "",
    ) -> str:
        lines: list[str] = []
        if base_instructions.strip():
            lines.append(base_instructions.strip())
        lines.extend(
            [
                "Skill loading policy:",
                "- Start from the available skill summaries instead of assuming a skill must be loaded.",
                "- Call `read_skill` only when a skill summary looks relevant and you need the full instructions.",
                "- After loading a skill, use its instructions to guide later tool calls.",
            ]
        )
        if tool_names:
            lines.append("Available tools:")
            for tool_name in sorted(tool_names):
                description = (tool_descriptions or {}).get(tool_name, "").strip()
                if description:
                    lines.append(f"- {tool_name}: {description}")
                else:
                    lines.append(f"- {tool_name}")
        if skills:
            lines.append("Available skills:")
            lines.append(build_skills_prompt(skills))
        return "\n".join(lines)
