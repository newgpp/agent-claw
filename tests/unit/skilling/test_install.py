import asyncio
from pathlib import Path

import pytest

from clawcore.skilling.github import GitHubSkillRef
from clawcore.skilling.install import install_github_skill


class FakeDownloader:
    def __init__(self, fixture_dir: Path) -> None:
        self.fixture_dir = fixture_dir

    async def fetch(self, skill_ref: GitHubSkillRef, destination: Path) -> Path:
        target = destination / skill_ref.default_name
        target.mkdir(parents=True, exist_ok=True)
        source = self.fixture_dir / skill_ref.default_name
        for path in source.rglob("*"):
            relative = path.relative_to(source)
            output = target / relative
            if path.is_dir():
                output.mkdir(parents=True, exist_ok=True)
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(path.read_bytes())
        return target


def test_install_github_skill_installs_valid_skill(tmp_path: Path) -> None:
    downloader = FakeDownloader(Path("tests/fixtures/install/github_download"))

    installed = asyncio.run(
        install_github_skill(
            "https://github.com/anthropics/skills/tree/main/skills/xlsx",
            skills_root=tmp_path / "skills",
            downloader=downloader,
        )
    )

    assert installed.name == "xlsx"
    assert installed.install_dir.joinpath("SKILL.md").exists()
    assert installed.manifest_path.exists()
    assert installed.scripts == ["scripts/recalc.py"]


def test_install_github_skill_rejects_missing_skill_md(tmp_path: Path) -> None:
    downloader = FakeDownloader(Path("tests/fixtures/install/github_download"))

    with pytest.raises(ValueError, match="must contain SKILL.md"):
        asyncio.run(
            install_github_skill(
                "https://github.com/anthropics/skills/tree/main/skills/broken-skill",
                skills_root=tmp_path / "skills",
                downloader=downloader,
            )
        )
