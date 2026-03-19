"""Prompt rendering helpers for available skills."""

from __future__ import annotations

from clawcore.skilling.models import SkillDefinition


def build_skills_prompt(skills: list[SkillDefinition]) -> str:
    """Render skills into a deterministic prompt block."""
    if not skills:
        return ""

    ordered_skills = sorted(skills, key=lambda skill: skill.name.lower())
    lines = ["<available_skills>"]
    for skill in ordered_skills:
        tools_line = f"    <tools>{', '.join(skill.tools)}</tools>" if skill.tools else ""
        scripts_line = f"    <scripts>{', '.join(skill.scripts)}</scripts>" if skill.scripts else ""
        lines.extend(
            [
                "  <skill>",
                f"    <name>{skill.name}</name>",
                f"    <description>{skill.description}</description>",
                f"    <location>{skill.location}</location>",
                *([tools_line] if tools_line else []),
                *([scripts_line] if scripts_line else []),
                "  </skill>",
            ]
        )
    lines.append("</available_skills>")
    return "\n".join(lines)
