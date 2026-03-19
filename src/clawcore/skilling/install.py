"""Install document-skills from GitHub references."""

from __future__ import annotations

import os
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

from clawcore.skilling.github import (
    GitHubSkillRef,
    collect_archive_members,
    parse_github_skill_url,
)
from clawcore.skilling.loader import SKILL_FILENAME
from clawcore.skilling.manifest import build_skill_manifest, write_skill_manifest


class SkillDownloader(Protocol):
    """Download a GitHub skill directory into a local path."""

    def fetch(self, skill_ref: GitHubSkillRef, destination: Path) -> Path:
        """Fetch the skill directory and return its local path."""


@dataclass(slots=True)
class GitHubArchiveDownloader:
    """Download GitHub skill directories via repository zip archives."""

    proxy_url: str | None = None
    timeout_seconds: float = 30.0

    def fetch(self, skill_ref: GitHubSkillRef, destination: Path) -> Path:
        archive_bytes = self._download_archive(skill_ref.archive_url)
        extracted_dir = destination / skill_ref.default_name
        extracted_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
            member_names = archive.namelist()
            relevant_members = collect_archive_members(skill_ref, member_names)
            if not relevant_members:
                raise ValueError("Referenced GitHub skill directory was not found in the archive.")

            prefix = f"{skill_ref.archive_skill_prefix}/"
            for member_name in relevant_members:
                relative_name = member_name.removeprefix(prefix)
                if not relative_name:
                    continue
                target_path = extracted_dir / relative_name
                if member_name.endswith("/"):
                    target_path.mkdir(parents=True, exist_ok=True)
                    continue
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member_name) as source, target_path.open("wb") as output:
                    output.write(source.read())
        return extracted_dir

    def _download_archive(self, archive_url: str) -> bytes:
        handlers: list[urllib.request.BaseHandler] = []
        proxy_url = self.proxy_url or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy_url:
            handlers.append(
                urllib.request.ProxyHandler(
                    {
                        "http": proxy_url,
                        "https": proxy_url,
                    }
                )
            )
        opener = urllib.request.build_opener(*handlers)
        request = urllib.request.Request(
            archive_url,
            headers={
                "User-Agent": "agent-claw/0.1",
                "Accept": "application/zip",
            },
        )
        with opener.open(request, timeout=self.timeout_seconds) as response:
            return response.read()


@dataclass(slots=True)
class InstalledSkill:
    """The result of a completed skill installation."""

    name: str
    install_dir: Path
    manifest_path: Path
    scripts: list[str]
    source: GitHubSkillRef


def install_github_skill(
    url: str,
    *,
    skills_root: str | Path,
    downloader: SkillDownloader | None = None,
) -> InstalledSkill:
    """Install a GitHub-hosted skill into the local skills directory."""
    skill_ref = parse_github_skill_url(url)
    skill_name = skill_ref.default_name
    root = Path(skills_root)
    root.mkdir(parents=True, exist_ok=True)
    target_dir = root / skill_name
    downloader_impl = downloader or GitHubArchiveDownloader()

    with TemporaryDirectory(prefix="agent-claw-skill-") as tmpdir:
        downloaded_dir = downloader_impl.fetch(skill_ref, Path(tmpdir))
        _validate_downloaded_skill(downloaded_dir)
        scripts = _collect_script_paths(downloaded_dir)

        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(downloaded_dir, target_dir)

    manifest = build_skill_manifest(skill_name=skill_name, source=skill_ref, scripts=scripts)
    manifest_path = write_skill_manifest(target_dir, manifest)
    return InstalledSkill(
        name=skill_name,
        install_dir=target_dir,
        manifest_path=manifest_path,
        scripts=scripts,
        source=skill_ref,
    )


def _validate_downloaded_skill(skill_dir: Path) -> None:
    if not skill_dir.exists() or not skill_dir.is_dir():
        raise ValueError("Downloaded skill directory does not exist.")
    skill_file = skill_dir / SKILL_FILENAME
    if not skill_file.exists() or not skill_file.is_file():
        raise ValueError("Installed skill must contain SKILL.md.")


def _collect_script_paths(skill_dir: Path) -> list[str]:
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.exists() or not scripts_dir.is_dir():
        return []

    collected: list[str] = []
    for path in sorted(scripts_dir.rglob("*")):
        if path.is_file():
            collected.append(str(path.relative_to(skill_dir)).replace("\\", "/"))
    return collected
