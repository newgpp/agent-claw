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
                "- First check whether the user request clearly matches exactly one available skill.",
                "- When the request clearly matches a skill, prefer that skill instead of going straight to raw tool use.",
                "- Start from the available skill summaries before assuming no skill applies.",
                "- Call `read_skill` when a skill appears to match and you need its full instructions before downstream tools.",
                "- Do not bypass an obviously matching skill unless the current context already fully answers the user.",
                "- If repeated tool calls are not producing materially new information, stop searching and answer with the best grounded summary plus clear limitations.",
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


@dataclass(slots=True)
class PlanningPromptBuilder:
    """Builds prompts for structured plan generation."""

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
                "Planning policy:",
                "- Decide whether the task needs multiple dependent steps.",
                "- Prefer a short plan with concrete subgoals over verbose reasoning.",
                "- First determine whether the request clearly matches exactly one available skill.",
                "- If one skill clearly matches, plan around using that skill before considering ad hoc tool use.",
                "- Do not treat skill summaries as weak hints only; use them as the default routing signal when the match is clear.",
                "- When search-style work yields little or no new information after a few attempts, prefer a bounded answer with limitations over more retries.",
                "- Include success criteria that let the runtime know when the task is done.",
                "- Add assumptions only when missing information could affect execution.",
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
