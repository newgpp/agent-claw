"""Helpers for building runtime-facing summaries from skill documents."""

from __future__ import annotations

import re

from clawcore.skilling.models import SkillDefinition


def summarize_skill_content(
    content: str,
    skill: SkillDefinition | None,
    *,
    limit: int = 3,
) -> list[str]:
    """Extract short summary lines from a loaded skill document."""
    summaries: list[str] = []
    if skill is not None and skill.description.strip():
        summaries.append(skill.description.strip())

    for line in content.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned.startswith(("---", "#", "```", "- ", "* ", "✅", "❌")):
            continue
        if ":" in cleaned and len(cleaned.split()) <= 4:
            continue
        if cleaned.startswith(("name:", "description:", "homepage:", "metadata:")):
            continue
        if cleaned in summaries:
            continue
        summaries.append(cleaned)
        if len(summaries) >= limit:
            break

    return summaries[:limit]


def extract_skill_recommended_tools(
    content: str,
    skill: SkillDefinition | None,
) -> list[str]:
    """Infer recommended tools from skill metadata and examples."""
    tools: list[str] = []
    if skill is not None:
        for tool in skill.tools:
            if tool not in tools:
                tools.append(tool)

    for line in content.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned.startswith(("curl ", "curl\"", "curl \"", "curl '")) and "curl" not in tools:
            tools.append("curl")
        if cleaned.startswith(("python ", "python3 ", "./")) and "exec_script" not in tools:
            tools.append("exec_script")
    return tools


def extract_skill_command_examples(content: str, *, limit: int = 3) -> list[str]:
    """Extract command-like examples from a skill document."""
    commands: list[str] = []
    for raw_line in content.splitlines():
        cleaned = raw_line.strip()
        if not cleaned:
            continue
        if cleaned.startswith(("curl ", "curl\"", "curl \"", "curl '", "python ", "python3 ", "./")):
            commands.append(cleaned)
        if len(commands) >= limit:
            break
    return commands


def extract_skill_call_hint(content: str) -> str | None:
    """Extract one concise call hint from a skill document if present."""
    command_examples = extract_skill_command_examples(content, limit=1)
    if command_examples:
        return command_examples[0]

    for line in content.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned.startswith(("curl ", "curl\"", "curl \"", "curl '")):
            return cleaned
        if "wttr.in/" in cleaned or "https://" in cleaned:
            return cleaned

    match = re.search(r"`([^`]*(?:curl|https?://|wttr\.in/)[^`]*)`", content)
    if match is not None:
        return match.group(1).strip()
    return None
