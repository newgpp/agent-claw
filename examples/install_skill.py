"""Install a GitHub-hosted document-skill into the local skills directory."""

from __future__ import annotations

from pathlib import Path

from clawcore.skilling.cli import build_install_skill_parser
from clawcore.skilling.install import GitHubArchiveDownloader, install_github_skill


def main() -> None:
    parser = build_install_skill_parser()
    args = parser.parse_args()

    downloader = GitHubArchiveDownloader(proxy_url=args.proxy)
    installed = install_github_skill(
        args.url,
        skills_root=Path(args.skills_root),
        downloader=downloader,
    )

    print(f"Installed skill: {installed.name}")
    print(f"Location: {installed.install_dir}")
    print(f"Manifest: {installed.manifest_path}")
    if installed.scripts:
        print("Scripts:")
        for script in installed.scripts:
            print(f"  - {script}")


if __name__ == "__main__":
    main()
