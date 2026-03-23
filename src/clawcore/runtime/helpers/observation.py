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
    if tool_name == "tavily":
        return summarize_tavily_observation(result_content)
    return build_observation(
        tool_name=tool_name,
        result_content=result_content,
        action_payload=action_payload,
        skills=skills,
        resolve_skill_from_payload=resolve_skill_from_payload,
    )


def summarize_tavily_observation(result_content: str) -> str:
    """Compress a Tavily response into a short prompt-friendly summary."""
    try:
        payload = json.loads(result_content)
    except json.JSONDecodeError:
        return f"tavily: {_summarize_for_prompt(result_content)}"

    if not isinstance(payload, dict):
        return f"tavily: {_summarize_for_prompt(result_content)}"

    query = str(payload.get("query", "")).strip()
    results = payload.get("results", [])
    total_results = len(results) if isinstance(results, list) else 0
    highlights: list[str] = []
    if isinstance(results, list):
        for item in results[:3]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            url = str(item.get("url", "")).strip()
            if title and url:
                highlights.append(f"{title} ({url})")
            elif title:
                highlights.append(title)
            elif url:
                highlights.append(url)
    summary = {
        "query": query,
        "result_count": total_results,
        "top_results": highlights,
    }
    return "tavily_summary: " + json.dumps(summary, ensure_ascii=False, sort_keys=True)


def _summarize_for_prompt(value: str, *, limit: int = 280) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."
