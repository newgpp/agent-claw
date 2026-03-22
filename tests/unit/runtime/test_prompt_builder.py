from pathlib import Path

from clawcore.runtime.prompt_builder import PlanningPromptBuilder, SystemPromptBuilder
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


def test_planning_prompt_builder_includes_planning_policy_skills_and_tools() -> None:
    builder = PlanningPromptBuilder()
    prompt = builder.build(
        skills=[
            SkillDefinition(
                name="weather",
                description="Check the current weather.",
                directory=Path("/tmp/weather"),
                skill_file=Path("/tmp/weather/SKILL.md"),
            )
        ],
        tool_names=["send_email", "curl"],
        tool_descriptions={
            "curl": "Fetch HTTP resources.",
            "send_email": "Send an email to a recipient.",
        },
        base_instructions="Plan carefully.",
    )

    assert "Plan carefully." in prompt
    assert "Planning policy:" in prompt
    assert "Decide whether the task needs multiple dependent steps." in prompt
    assert "Include success criteria" in prompt
    assert "Available tools:" in prompt
    assert "- curl: Fetch HTTP resources." in prompt
    assert "- send_email: Send an email to a recipient." in prompt
    assert "Available skills:" in prompt
    assert "<name>weather</name>" in prompt
