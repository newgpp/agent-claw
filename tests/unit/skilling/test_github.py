import pytest

from clawcore.skilling.github import parse_github_skill_url


def test_parse_github_skill_url_parses_tree_reference() -> None:
    parsed = parse_github_skill_url(
        "https://github.com/anthropics/skills/tree/main/skills/xlsx"
    )

    assert parsed.repo == "anthropics/skills"
    assert parsed.ref == "main"
    assert parsed.path == "skills/xlsx"
    assert parsed.default_name == "xlsx"
    assert parsed.archive_url == "https://github.com/anthropics/skills/archive/refs/heads/main.zip"


def test_parse_github_skill_url_rejects_non_github_urls() -> None:
    with pytest.raises(ValueError, match="Only GitHub URLs are supported"):
        parse_github_skill_url("https://example.com/skills/xlsx")


def test_parse_github_skill_url_rejects_non_tree_urls() -> None:
    with pytest.raises(ValueError, match="Expected a GitHub tree URL"):
        parse_github_skill_url("https://github.com/anthropics/skills/blob/main/skills/xlsx/SKILL.md")
