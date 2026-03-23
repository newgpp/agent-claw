"""Helpers for building runtime-facing summaries from skill documents."""

from __future__ import annotations

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
