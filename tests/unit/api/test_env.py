import os
from pathlib import Path

import pytest

from apps.env import load_dotenv, resolve_default_dotenv_path
from apps.api.run import resolve_api_bind


def test_load_dotenv_sets_missing_values_without_overwriting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        'OPENAI_API_KEY="test-key"\nAGENT_CLAW_API_HOST=0.0.0.0\nAGENT_CLAW_API_PORT=9000\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
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
