"""Load skill definitions from filesystem directories."""

from __future__ import annotations

import json
from pathlib import Path

from clawcore.skilling.models import SkillDefinition

SKILL_FILENAME = "SKILL.md"
SKILL_METADATA_FILENAME = "skill.json"


def load_skills(root_dir: str | Path) -> list[SkillDefinition]:
    """Load valid skills from a root directory."""
    root = Path(root_dir)
    if not root.exists() or not root.is_dir():
        return []

    direct_skill = _load_skill_from_directory(root)
    if direct_skill is not None:
        return [direct_skill]

    skills: list[SkillDefinition] = []
    for directory in sorted((entry for entry in root.iterdir() if entry.is_dir()), key=lambda p: p.name):
        skill = _load_skill_from_directory(directory)
        if skill is not None:
            skills.append(skill)
    return skills


def _load_skill_from_directory(directory: Path) -> SkillDefinition | None:
    skill_file = directory / SKILL_FILENAME
    if not skill_file.exists() or not skill_file.is_file():
        return None

    metadata = _load_metadata(directory / SKILL_METADATA_FILENAME)
    markdown_text = skill_file.read_text(encoding="utf-8").strip()
    if not markdown_text:
        return None

    frontmatter = _extract_frontmatter(markdown_text)
    name = str(metadata.get("name") or frontmatter.get("name") or directory.name).strip()
    description = str(
        metadata.get("description") or frontmatter.get("description") or _extract_description(markdown_text)
    ).strip()
    if not name or not description:
        return None

    tools = _normalize_string_list(metadata.get("tools"))
    scripts = _normalize_string_list(metadata.get("scripts"))
    tags = _normalize_string_list(metadata.get("tags"))
    return SkillDefinition(
        name=name,
        description=description,
        directory=directory,
        skill_file=skill_file,
        tools=tools,
        scripts=scripts,
        tags=tags,
    )


def _load_metadata(metadata_path: Path) -> dict[str, object]:
    if not metadata_path.exists() or not metadata_path.is_file():
        return {}

    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _extract_description(markdown_text: str) -> str:
    content = _strip_frontmatter(markdown_text)
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        return line
    return ""


def _extract_frontmatter(markdown_text: str) -> dict[str, str]:
    lines = markdown_text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}

    metadata: dict[str, str] = {}
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        normalized_key = key.strip()
        normalized_value = value.strip().strip('"').strip("'")
        if normalized_key and normalized_value:
            metadata[normalized_key] = normalized_value
    return metadata


def _strip_frontmatter(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return markdown_text

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :]).strip()
    return markdown_text


def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        trimmed = item.strip()
        if trimmed:
            normalized.append(trimmed)
    return normalized
