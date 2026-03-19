import json
from pathlib import Path

from clawcore.skilling.github import GitHubSkillRef
from clawcore.skilling.manifest import build_skill_manifest, write_skill_manifest


def test_build_skill_manifest_is_stable() -> None:
    manifest = build_skill_manifest(
        skill_name="xlsx",
        source=GitHubSkillRef(
            repo="anthropics/skills",
            ref="main",
            path="skills/xlsx",
            url="https://github.com/anthropics/skills/tree/main/skills/xlsx",
        ),
        scripts=["scripts/recalc.py"],
    )

    assert manifest["name"] == "xlsx"
    assert manifest["scripts"] == ["scripts/recalc.py"]
    assert manifest["source"] == {
        "type": "github",
        "repo": "anthropics/skills",
        "ref": "main",
        "path": "skills/xlsx",
        "url": "https://github.com/anthropics/skills/tree/main/skills/xlsx",
    }


def test_write_skill_manifest_writes_skill_json(tmp_path: Path) -> None:
    manifest = {"name": "xlsx", "scripts": [], "tools": [], "tags": [], "source": {}}

    manifest_path = write_skill_manifest(tmp_path / "xlsx", manifest)

    assert manifest_path.name == "skill.json"
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
