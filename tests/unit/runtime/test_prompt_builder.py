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
        tool_descriptions={
            "read": "Read file contents from the workspace.",
            "write": "Write file contents into the workspace.",
        },
        base_instructions="Follow the active skill.",
    )

    assert "Follow the active skill." in prompt
    assert "Skill loading policy:" in prompt
    assert "Call `read_skill` only when a skill summary looks relevant" in prompt
    assert "Available tools:" in prompt
    assert "- read: Read file contents from the workspace." in prompt
    assert "- write: Write file contents into the workspace." in prompt
    assert "Available skills:" in prompt
    assert "<name>release-checker</name>" in prompt
    assert "<description>Check release steps.</description>" in prompt
