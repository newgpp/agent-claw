from pathlib import Path

import pytest

from agents.factory import (
    OpenAIRuntimeAgentSpec,
    build_agent,
    clear_agent_cache,
    get_agent,
    load_agent_spec,
)


def test_load_agent_spec_reads_valid_json_fixture() -> None:
    spec = load_agent_spec(Path("tests/fixtures/agents/openai_runtime_basic.json"))

    assert spec == OpenAIRuntimeAgentSpec(
        type="openai-runtime",
        model="gpt-test",
        tools=("echo_payload",),
        skills=("weather",),
        base_instructions="Use the available tools carefully.",
        max_steps=4,
        workspace_dir="../runtime/workspace",
        include_read_skill=True,
        base_url="http://localhost:1234/v1",
        temperature=0.2,
        max_tokens=256,
        metadata={},
    )


def test_build_agent_resolves_relative_paths_from_config_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    config_path = Path("tests/fixtures/agents/openai_runtime_basic.json").resolve()
    spec = load_agent_spec(config_path)

    agent = build_agent(spec, config_path=config_path)

    assert [skill.name for skill in agent.config.skills] == ["weather"]
    assert agent.config.workspace_dir == Path("tests/fixtures/runtime/workspace").resolve()
    assert "read" in agent.runtime.tool_executor.registry.names()
    assert "write" in agent.runtime.tool_executor.registry.names()
    assert "exec_script" in agent.runtime.tool_executor.registry.names()
    assert "read_skill" in agent.runtime.tool_executor.registry.names()
    assert "echo_payload" in agent.runtime.tool_executor.registry.names()
    assert agent.runtime.llm.config.model == "gpt-test"


def test_get_agent_returns_singleton_per_config_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    clear_agent_cache()
    config_path = str(Path("tests/fixtures/agents/openai_runtime_basic.json").resolve())

    first = get_agent(config_path)
    second = get_agent(config_path)

    assert first is second


def test_get_agent_returns_distinct_singletons_for_distinct_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    clear_agent_cache()
    first_path = tmp_path / "agent-one.json"
    second_path = tmp_path / "agent-two.json"
    config = (
        '{'
        '"type":"openai-runtime",'
        '"model":"gpt-test",'
        '"tools":["echo_payload"],'
        '"base_instructions":"Use the read tool.",'
        '"max_steps":3,'
        '"include_read_skill":false'
        '}'
    )
    first_path.write_text(config, encoding="utf-8")
    second_path.write_text(config, encoding="utf-8")

    first = get_agent(str(first_path.resolve()))
    second = get_agent(str(second_path.resolve()))

    assert first is not second


def test_load_agent_spec_rejects_invalid_tool_entries(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid-agent.json"
    invalid_path.write_text(
        '{"type":"openai-runtime","model":"gpt-test","tools":["read", 3]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="tools"):
        load_agent_spec(invalid_path)


def test_build_agent_resolves_discovered_agent_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    spec = OpenAIRuntimeAgentSpec(
        type="openai-runtime",
        model="gpt-test",
        tools=("echo_payload",),
    )

    agent = build_agent(spec)

    assert "echo_payload" in agent.runtime.tool_executor.registry.names()
