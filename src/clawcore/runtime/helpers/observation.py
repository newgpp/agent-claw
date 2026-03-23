"""Helpers for runtime observations recorded after tool execution."""

from __future__ import annotations

import json

from clawcore.skilling.models import SkillDefinition
from clawcore.skilling.runtime_summary import summarize_skill_content


def build_observation(
    *,
    tool_name: str,
    result_content: str,
    action_payload: dict[str, object],
    skills: tuple[SkillDefinition, ...],
    resolve_skill_from_payload,
) -> str:
    """Build the full observation recorded in scratchpad history."""
    if tool_name != "read_skill":
        return f"{tool_name}: {result_content}"

    selected_skill = resolve_skill_from_payload(action_payload, skills)
    payload = {
        "skill_name": selected_skill.name if selected_skill is not None else str(
            action_payload.get("skill", action_payload.get("skill_name", ""))
        ).strip(),
        "summary": summarize_skill_content(result_content, selected_skill),
        "full_doc_available": True,
    }
    return "read_skill_summary: " + json.dumps(payload, ensure_ascii=False, sort_keys=True)


def build_prompt_observation(
    *,
    tool_name: str,
    result_content: str,
    action_payload: dict[str, object],
    skills: tuple[SkillDefinition, ...],
    resolve_skill_from_payload,
) -> str:
    """Build the compact prompt-facing observation fed back to the executor."""
    return build_observation(
        tool_name=tool_name,
        result_content=result_content,
        action_payload=action_payload,
        skills=skills,
        resolve_skill_from_payload=resolve_skill_from_payload,
    )
