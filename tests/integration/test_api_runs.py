import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from apps.api.dependencies import AgentCatalogEntry
from apps.api.main import _resolve_agent_for_run, create_app
from agents.base import AgentDescriptor, BaseAgent
from clawcore.models import ToolResult
from clawcore.runtime import RuntimeRunResult, RuntimeState
from common.events import RunFinished


class DemoAPIAgent(BaseAgent):
    descriptor = AgentDescriptor(name="demo-api-agent", description="Demo API test agent.")

    async def run(self, user_input: str, *, workspace_dir=None) -> str:  # type: ignore[no-untyped-def]
        assert workspace_dir is None
        return f"done: {user_input}"

    async def run_debug(self, user_input: str, *, workspace_dir=None) -> RuntimeRunResult:  # type: ignore[no-untyped-def]
        assert workspace_dir is None
        state = RuntimeState(user_input=user_input)
        state.scratchpad.append(f"echo_payload: {user_input}")
        state.prompt_observations.append(f"echo_payload: {user_input}")
        state.tool_results.append(ToolResult(name="echo_payload", content=user_input))
        state.events.append(
            RunFinished(
                run_id="run-1",
                session_id="session-1",
                trace_id="trace-1",
                payload={"final_answer": f"done: {user_input}"},
            )
        )
        state.trace.record("final_answer", f"done: {user_input}")
        return RuntimeRunResult(final_answer=f"done: {user_input}", state=state)


def test_api_endpoints_match_fixture_cases() -> None:
    app = create_app()
    fixture_cases = json.loads(Path("tests/fixtures/api/run_cases.json").read_text(encoding="utf-8"))

    from apps.api.dependencies import get_agent_catalog

    app.dependency_overrides[get_agent_catalog] = lambda: [
        AgentCatalogEntry(
            id="demo-agent",
            type="openai-runtime",
            model="gpt-test",
            config_path="/virtual/configs/demo-agent.json",
        )
    ]
    app.dependency_overrides[_resolve_agent_for_run] = lambda: DemoAPIAgent()
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    agents = client.get("/agents")
    assert agents.status_code == 200
    assert agents.json() == [
        {
            "id": "demo-agent",
            "type": "openai-runtime",
            "model": "gpt-test",
            "config_path": "/virtual/configs/demo-agent.json",
        }
    ]

    for case in fixture_cases:
        response = client.request(case["method"], case["path"], json=case["body"])
        assert response.status_code == case["status_code"]
        payload = response.json()
        for key, value in case["expected"].items():
            assert payload[key] == value
        if case["name"] == "debug":
            assert payload["debug_state"]["scratchpad"] == ["echo_payload: hello"]
            assert payload["debug_state"]["tool_results"] == [{"name": "echo_payload", "content": "hello"}]
            assert payload["debug_state"]["events"][0]["event_type"] == "run.finished"
            assert payload["debug_state"]["trace"][0]["kind"] == "final_answer"


def test_api_logs_run_request_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()
    records: list[tuple[str, tuple[object, ...]]] = []

    def fake_info(message: str, *args: object) -> None:
        records.append((message, args))

    from apps.api.dependencies import get_agent_catalog

    app.dependency_overrides[get_agent_catalog] = lambda: [
        AgentCatalogEntry(
            id="demo-agent",
            type="openai-runtime",
            model="gpt-test",
            config_path="/virtual/configs/demo-agent.json",
        )
    ]
    app.dependency_overrides[_resolve_agent_for_run] = lambda: DemoAPIAgent()
    monkeypatch.setattr("apps.api.main.logger.info", fake_info)
    client = TestClient(app)

    response = client.post(
        "/runs",
        json={"agent_id": "demo-agent", "user_input": "trace this request"},
    )

    assert response.status_code == 200
    assert records[0] == (
        "API request path=/runs agent_id={} user_input={}",
        ("demo-agent", "trace this request"),
    )
