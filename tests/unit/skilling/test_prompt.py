from pathlib import Path

from clawcore.skilling.models import SkillDefinition
from clawcore.skilling.prompt import build_skills_prompt


def test_build_skills_prompt_renders_stable_order() -> None:
    skills = [
        SkillDefinition(
            name="zebra",
            description="Last skill alphabetically.",
            directory=Path("/tmp/zebra"),
            skill_file=Path("/tmp/zebra/SKILL.md"),
            tools=["read"],
        ),
        SkillDefinition(
            name="alpha",
            description="First skill alphabetically.",
            directory=Path("/tmp/alpha"),
            skill_file=Path("/tmp/alpha/SKILL.md"),
            scripts=["scripts/alpha.py"],
        ),
    ]

    prompt = build_skills_prompt(skills)

    assert "<available_skills>" in prompt
    assert prompt.index("<name>alpha</name>") < prompt.index("<name>zebra</name>")
    assert "<scripts>scripts/alpha.py</scripts>" in prompt
    assert "<tools>read</tools>" in prompt


def test_build_skills_prompt_returns_empty_for_no_skills() -> None:
    assert build_skills_prompt([]) == ""
