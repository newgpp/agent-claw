from pathlib import Path

from apps.api.schemas import DebugRunResponse
from clawcore.models import ToolResult
from clawcore.runtime import RuntimeRunResult, RuntimeState
from common.events import RunFinished


def test_debug_run_response_serializes_runtime_result_stably() -> None:
    state = RuntimeState(user_input="hello")
    state.scratchpad.append("echo_payload: hello")
    state.tool_results.append(ToolResult(name="echo_payload", content="hello"))
    state.events.append(
        RunFinished(
            run_id="run-1",
            session_id="session-1",
            trace_id="trace-1",
            payload={"final_answer": "done: hello"},
        )
    )
    state.trace.record("final_answer", "done: hello")
    response = DebugRunResponse.from_runtime_result(
        agent_id="demo-agent",
        result=RuntimeRunResult(final_answer="done: hello", state=state),
    )

    dumped = response.model_dump()

    assert dumped["agent_id"] == "demo-agent"
    assert dumped["tool_results"] == [{"name": "echo_payload", "content": "hello"}]
    assert dumped["events"][0]["event_type"] == "run.finished"
    assert dumped["trace"][0]["kind"] == "final_answer"
