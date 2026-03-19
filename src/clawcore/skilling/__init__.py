"""Skill loading and prompt rendering helpers."""

from clawcore.skilling.cli import build_install_skill_parser
from clawcore.skilling.github import GitHubSkillRef, parse_github_skill_url
from clawcore.skilling.install import InstalledSkill, install_github_skill
from clawcore.skilling.loader import load_skills
from clawcore.skilling.manifest import build_skill_manifest, write_skill_manifest
from clawcore.skilling.models import SkillDefinition
from clawcore.skilling.prompt import build_skills_prompt

__all__ = [
    "GitHubSkillRef",
    "InstalledSkill",
    "SkillDefinition",
    "build_install_skill_parser",
    "build_skills_prompt",
    "build_skill_manifest",
    "install_github_skill",
    "load_skills",
    "parse_github_skill_url",
    "write_skill_manifest",
]
