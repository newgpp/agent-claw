"""Manifest generation for installed skills."""

from __future__ import annotations

import json
from pathlib import Path

from clawcore.skilling.github import GitHubSkillRef


def build_skill_manifest(
    *,
    skill_name: str,
    source: GitHubSkillRef,
    scripts: list[str],
) -> dict[str, object]:
    """Build a stable manifest for an installed skill."""
    return {
        "name": skill_name,
        "source": {
            "type": "github",
            "repo": source.repo,
            "ref": source.ref,
            "path": source.path,
            "url": source.url,
        },
        "tools": [],
        "scripts": scripts,
        "tags": [],
    }


def write_skill_manifest(skill_dir: str | Path, manifest: dict[str, object]) -> Path:
    """Write a manifest to `skill.json` using stable formatting."""
    directory = Path(skill_dir)
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "skill.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return manifest_path
