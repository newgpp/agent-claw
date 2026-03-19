from common.observability import (
    bind_run_id,
    bind_session_id,
    bind_trace_id,
    current_observability_context,
    current_trace_headers,
    reset_run_id,
    reset_session_id,
    reset_trace_id,
    setup_loguru,
)


def test_observability_context_can_bind_and_reset_ids() -> None:
    run_token = bind_run_id("run-123")
    session_token = bind_session_id("session-123")
    trace_token = bind_trace_id("trace-123")

    try:
        assert current_observability_context() == {
            "run_id": "run-123",
            "session_id": "session-123",
            "trace_id": "trace-123",
        }
        assert current_trace_headers() == {
            "X-Run-Id": "run-123",
            "X-Session-Id": "session-123",
            "X-Trace-Id": "trace-123",
        }
    finally:
        reset_trace_id(trace_token)
        reset_session_id(session_token)
        reset_run_id(run_token)

    assert current_observability_context() == {
        "run_id": "-",
        "session_id": "-",
        "trace_id": "-",
    }


def test_setup_loguru_can_be_called_multiple_times() -> None:
    setup_loguru(service_name="unit-test")
    setup_loguru(service_name="unit-test")
