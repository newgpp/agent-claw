import asyncio
import json
from pathlib import Path

from clawcore.skilling.install import install_github_skill
from clawcore.skilling.loader import load_skills


class FixtureDownloader:
    def __init__(self, fixture_dir: Path) -> None:
        self.fixture_dir = fixture_dir

    async def fetch(self, skill_ref, destination: Path) -> Path:  # type: ignore[no-untyped-def]
        source = self.fixture_dir / skill_ref.default_name
        target = destination / skill_ref.default_name
        for path in source.rglob("*"):
            relative = path.relative_to(source)
            output = target / relative
            if path.is_dir():
                output.mkdir(parents=True, exist_ok=True)
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(path.read_bytes())
        return target


def test_skill_install_pipeline_installs_and_loads_skill(tmp_path: Path) -> None:
    downloader = FixtureDownloader(Path("tests/fixtures/install/github_download"))

    installed = asyncio.run(
        install_github_skill(
            "https://github.com/anthropics/skills/tree/main/skills/xlsx",
            skills_root=tmp_path / "skills",
            downloader=downloader,
        )
    )

    loaded_skills = load_skills(tmp_path / "skills")
    manifest = json.loads(installed.manifest_path.read_text(encoding="utf-8"))

    assert installed.name == "xlsx"
    assert [skill.name for skill in loaded_skills] == ["xlsx"]
    assert loaded_skills[0].scripts == ["scripts/recalc.py"]
    assert manifest["source"]["repo"] == "anthropics/skills"
