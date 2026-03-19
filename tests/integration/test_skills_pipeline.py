from pathlib import Path

from clawcore.skilling.loader import load_skills
from clawcore.skilling.prompt import build_skills_prompt


def test_skills_pipeline_loads_and_renders_document_skills() -> None:
    fixture_root = Path("tests/fixtures/skills/multi")

    skills = load_skills(fixture_root)
    prompt = build_skills_prompt(skills)

    assert [skill.name for skill in skills] == ["doc-writer", "release-checker"]
    assert "<name>doc-writer</name>" in prompt
    assert "<name>release-checker</name>" in prompt
    assert "<tools>read, write</tools>" in prompt
    assert "<scripts>scripts/release_check.py</scripts>" in prompt
