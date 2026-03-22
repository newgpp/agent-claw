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


def get_env_bool(name: str, default: bool = False) -> bool:
    """Return a boolean env flag using common truthy/falsey string values."""
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a valid boolean value.")


def resolve_api_logging() -> tuple[bool, str]:
    """Return the configured API log file toggle and directory."""
    load_dotenv()
    log_to_file = get_env_bool("AGENT_CLAW_LOG_TO_FILE", default=False)
    log_dir = os.environ.get("AGENT_CLAW_LOG_DIR", "logs").strip() or "logs"
    return log_to_file, log_dir


def _strip_optional_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
