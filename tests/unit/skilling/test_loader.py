from pathlib import Path

from clawcore.skilling.loader import load_skills


def test_load_skills_reads_valid_fixture_skills() -> None:
    fixture_root = Path("tests/fixtures/skills/basic")

    skills = load_skills(fixture_root)

    assert [skill.name for skill in skills] == ["code-review", "summarize"]
    assert skills[0].description == "Review code for bugs, risks, and missing tests."
    assert skills[0].tools == ["read", "report"]
    assert skills[0].scripts == ["scripts/review_check.py"]


def test_load_skills_ignores_invalid_entries() -> None:
    fixture_root = Path("tests/fixtures/skills/invalid")

    skills = load_skills(fixture_root)

    assert skills == []


def test_load_skills_extracts_description_from_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "weather"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        'name: weather\n'
        'description: "Get current weather and forecasts."\n'
        "---\n\n"
        "# Weather Skill\n\n"
        "Use this when the user asks about weather.\n",
        encoding="utf-8",
    )

    skills = load_skills(tmp_path)

    assert [skill.name for skill in skills] == ["weather"]
    assert skills[0].description == "Get current weather and forecasts."
