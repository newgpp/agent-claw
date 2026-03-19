"""CLI helpers for skill installation flows."""

from __future__ import annotations

import argparse


def build_install_skill_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for GitHub skill installation."""
    parser = argparse.ArgumentParser(description="Install a GitHub-hosted skill.")
    parser.add_argument(
        "url",
        help="GitHub tree URL pointing to a skill directory.",
    )
    parser.add_argument(
        "--skills-root",
        default="skills",
        help="Local skills installation directory. Defaults to ./skills",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help="Optional HTTP/HTTPS proxy URL, for example http://127.0.0.1:7890",
    )
    return parser
