from pathlib import Path

from apps.api.dependencies import get_agent_catalog, resolve_agents_config_dir


def test_resolve_agents_config_dir_defaults_to_repo_configs() -> None:
    path = resolve_agents_config_dir()

    assert path == Path("configs/agents").resolve()


def test_get_agent_catalog_lists_configured_agents() -> None:
    catalog = get_agent_catalog()
    ids = [entry.id for entry in catalog]

    assert "openai_runtime" in ids
    assert "weather" in ids
