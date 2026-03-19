from common.events import RunFinished, RunStarted, ToolCalled, ToolReturned


def test_runtime_events_serialize_predictably() -> None:
    event = RunStarted(
        run_id="run-1",
        session_id="session-1",
        trace_id="trace-1",
        payload={"user_input": "hello"},
    )

    data = event.to_dict()

    assert data["event_type"] == "run.started"
    assert data["run_id"] == "run-1"
    assert data["session_id"] == "session-1"
    assert data["trace_id"] == "trace-1"
    assert data["payload"] == {"user_input": "hello"}
    assert isinstance(data["timestamp"], str)


def test_specialized_event_types_have_expected_names() -> None:
    assert ToolCalled(run_id="r", session_id="s", trace_id="t").event_type == "tool.called"
    assert ToolReturned(run_id="r", session_id="s", trace_id="t").event_type == "tool.returned"
    assert RunFinished(run_id="r", session_id="s", trace_id="t").event_type == "run.finished"
