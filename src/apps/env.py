"""Environment loading helpers for app-layer entrypoints."""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: str | Path | None = None) -> Path | None:
    """Load a simple .env file into ``os.environ`` without overwriting existing values."""
    env_path = Path(path).resolve() if path is not None else resolve_default_dotenv_path()
    if not env_path.exists() or not env_path.is_file():
        return None

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = key.strip()
        if not normalized_key or normalized_key in os.environ:
            continue
        os.environ[normalized_key] = _strip_optional_quotes(value.strip())
    return env_path


def resolve_default_dotenv_path() -> Path:
    """Return the repo-root .env path used by app entrypoints."""
    return (Path(__file__).resolve().parents[2] / ".env").resolve()


def _strip_optional_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
