import os
from pathlib import Path

import pytest

from apps.env import (
    get_env_bool,
    load_dotenv,
    resolve_api_logging,
    resolve_default_dotenv_path,
)
from apps.api.run import resolve_api_bind


def test_load_dotenv_sets_missing_values_without_overwriting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        'OPENAI_API_KEY="test-key"\nAGENT_CLAW_API_HOST=0.0.0.0\nAGENT_CLAW_API_PORT=9000\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_CLAW_API_PORT", raising=False)
    monkeypatch.setenv("AGENT_CLAW_API_HOST", "127.0.0.1")

    loaded = load_dotenv(env_path)

    assert loaded == env_path.resolve()
    assert os.environ["OPENAI_API_KEY"] == "test-key"
    assert os.environ["AGENT_CLAW_API_HOST"] == "127.0.0.1"
    assert os.environ["AGENT_CLAW_API_PORT"] == "9000"


def test_resolve_default_dotenv_path_points_to_repo_root() -> None:
    assert resolve_default_dotenv_path() == Path(".env").resolve()


def test_resolve_api_bind_reads_env_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_CLAW_API_HOST", "0.0.0.0")
    monkeypatch.setenv("AGENT_CLAW_API_PORT", "9000")

    host, port = resolve_api_bind()

    assert host == "0.0.0.0"
    assert port == 9000


def test_get_env_bool_reads_common_true_false_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLAG_TRUE", "true")
    monkeypatch.setenv("FLAG_FALSE", "off")

    assert get_env_bool("FLAG_TRUE") is True
    assert get_env_bool("FLAG_FALSE", default=True) is False


def test_get_env_bool_rejects_invalid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLAG_INVALID", "maybe")

    with pytest.raises(ValueError, match="FLAG_INVALID must be a valid boolean value."):
        get_env_bool("FLAG_INVALID")


def test_resolve_api_logging_reads_env_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_CLAW_LOG_TO_FILE", "yes")
    monkeypatch.setenv("AGENT_CLAW_LOG_DIR", "runtime-logs")

    log_to_file, log_dir = resolve_api_logging()

    assert log_to_file is True
    assert log_dir == "runtime-logs"
