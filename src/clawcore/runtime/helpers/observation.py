"""Helpers for runtime observations recorded after tool execution."""

from __future__ import annotations

import importlib.util
import json
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Protocol

from clawcore.skilling.models import SkillDefinition
from clawcore.skilling.runtime_summary import summarize_skill_content


class PromptObservationSummarizer(Protocol):
    def __call__(
        self,
        *,
        tool_name: str,
        action_payload: dict[str, object],
        result_content: str,
    ) -> str | None: ...


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
    active_skill: SkillDefinition | None,
    resolve_skill_from_payload,
) -> str:
    """Build the compact prompt-facing observation fed back to the executor."""
    summarized = _summarize_prompt_observation(
        tool_name=tool_name,
        result_content=result_content,
        action_payload=action_payload,
        skills=skills,
        active_skill=active_skill,
    )
    if summarized is not None:
        return summarized

    return build_observation(
        tool_name=tool_name,
        result_content=result_content,
        action_payload=action_payload,
        skills=skills,
        resolve_skill_from_payload=resolve_skill_from_payload,
    )


def _summarize_prompt_observation(
    *,
    tool_name: str,
    result_content: str,
    action_payload: dict[str, object],
    skills: tuple[SkillDefinition, ...],
    active_skill: SkillDefinition | None,
) -> str | None:
    for skill in _candidate_skills(skills=skills, active_skill=active_skill):
        summarizer = _load_prompt_observation_summarizer(skill)
        if summarizer is None:
            continue
        summarized = summarizer(
            tool_name=tool_name,
            action_payload=action_payload,
            result_content=result_content,
        )
        if isinstance(summarized, str):
            normalized = summarized.strip()
            if normalized:
                return normalized
    return None


def _candidate_skills(
    *,
    skills: tuple[SkillDefinition, ...],
    active_skill: SkillDefinition | None,
) -> list[SkillDefinition]:
    ordered: list[SkillDefinition] = []
    if active_skill is not None:
        ordered.append(active_skill)
    for skill in skills:
        if active_skill is not None and skill.name == active_skill.name:
            continue
        ordered.append(skill)
    return ordered


def _load_prompt_observation_summarizer(
    skill: SkillDefinition,
) -> PromptObservationSummarizer | None:
    module = _load_prompt_observation_module(skill.directory / "prompt_observation.py")
    if module is None:
        return None
    candidate = getattr(module, "summarize_tool_result", None)
    if callable(candidate):
        return candidate
    return None


@lru_cache(maxsize=128)
def _load_prompt_observation_module(module_path: Path) -> ModuleType | None:
    if not module_path.exists() or not module_path.is_file():
        return None

    spec = importlib.util.spec_from_file_location(
        f"skill_prompt_observation_{abs(hash(str(module_path.resolve())))}",
        module_path,
    )
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
