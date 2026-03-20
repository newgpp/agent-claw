"""Built-in skill loading tool."""

from __future__ import annotations

import asyncio

from clawcore.skilling.models import SkillDefinition
from clawcore.tooling.base import BaseTool, ToolExecutionContext


def _find_skill(skills: tuple[SkillDefinition, ...], skill_name: str) -> SkillDefinition | None:
    normalized = skill_name.strip().lower()
    for skill in skills:
        if skill.name.lower() == normalized:
            return skill
    return None


class ReadSkillTool(BaseTool):
    """Read the full document for an available skill."""

    name = "read_skill"
    description = (
        "Load the full markdown content for one available skill. "
        "Payload: {skill:string}."
    )
    risk_level = "low"

    async def execute(self, payload: dict[str, object], context: ToolExecutionContext) -> str:
        raw_skill = str(payload.get("skill", payload.get("skill_name", ""))).strip()
        if not raw_skill:
            raise ValueError("read_skill requires a non-empty 'skill'.")

        skill = _find_skill(context.available_skills, raw_skill)
        if skill is None:
            raise KeyError(f"Skill '{raw_skill}' is not available.")

        content = await asyncio.to_thread(skill.skill_file.read_text, encoding="utf-8")
        return content.strip()
