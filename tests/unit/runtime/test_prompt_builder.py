from pathlib import Path

from clawcore.runtime.prompt_builder import SystemPromptBuilder
from clawcore.skilling.models import SkillDefinition


def test_prompt_builder_includes_skills_and_tools() -> None:
    builder = SystemPromptBuilder()
    prompt = builder.build(
        skills=[
            SkillDefinition(
                name="release-checker",
                description="Check release steps.",
                directory=Path("/tmp/release"),
                skill_file=Path("/tmp/release/SKILL.md"),
            )
        ],
        tool_names=["write", "read"],
        base_instructions="Follow the active skill.",
    )

    assert "Follow the active skill." in prompt
    assert "Available tools: read, write" in prompt
    assert "Available skills: release-checker" in prompt
