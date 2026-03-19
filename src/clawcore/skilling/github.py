"""GitHub URL parsing helpers for document-skills."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(slots=True)
class GitHubSkillRef:
    """A parsed GitHub skill directory reference."""

    repo: str
    ref: str
    path: str
    url: str

    @property
    def default_name(self) -> str:
        """Return the default installation name derived from the path."""
        return self.path.rstrip("/").split("/")[-1]

    @property
    def archive_url(self) -> str:
        """Return the GitHub archive URL for the selected ref."""
        return f"https://github.com/{self.repo}/archive/refs/heads/{self.ref}.zip"

    @property
    def archive_root_prefix(self) -> str:
        """Return the root directory prefix expected inside the downloaded archive."""
        repo_name = self.repo.split("/")[-1]
        return f"{repo_name}-{self.ref}"

    @property
    def archive_skill_prefix(self) -> str:
        """Return the skill path prefix expected inside the downloaded archive."""
        return f"{self.archive_root_prefix}/{self.path.strip('/')}"


def parse_github_skill_url(url: str) -> GitHubSkillRef:
    """Parse a GitHub tree URL that points at a skill directory."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"https", "http"} or parsed.netloc != "github.com":
        raise ValueError("Only GitHub URLs are supported.")

    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 5 or segments[2] != "tree":
        raise ValueError("Expected a GitHub tree URL pointing to a skill directory.")

    owner, repo_name, _, ref, *path_segments = segments
    if not owner or not repo_name or not ref or not path_segments:
        raise ValueError("GitHub skill URL is missing required path segments.")

    return GitHubSkillRef(
        repo=f"{owner}/{repo_name}",
        ref=ref,
        path="/".join(path_segments),
        url=url,
    )


def collect_archive_members(skill_ref: GitHubSkillRef, member_names: list[str]) -> list[str]:
    """Filter archive members to those inside the referenced skill directory."""
    prefix = f"{skill_ref.archive_skill_prefix}/"
    return sorted(name for name in member_names if name.startswith(prefix))
