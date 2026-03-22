from apps.api.schemas import DebugRunResponse
from clawcore.models import ExecutionPlan, PlanArtifact, PlanStatus, PlanSubgoal, ToolResult
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
    assert dumped["plan"] is None
    assert dumped["artifacts"] == []
    assert dumped["replanning_count"] == 0
    assert dumped["events"][0]["event_type"] == "run.finished"
    assert dumped["trace"][0]["kind"] == "final_answer"


def test_debug_run_response_serializes_plan_state() -> None:
    state = RuntimeState(
        user_input="write a weather email",
        plan=ExecutionPlan(
            goal="Write and send a weather email",
            subgoals=[
                PlanSubgoal(id="s1", task="Fetch the weather", status=PlanStatus.COMPLETED),
                PlanSubgoal(id="s2", task="Draft the email", status=PlanStatus.IN_PROGRESS),
            ],
            success_criteria=["Email draft is ready", "Recipient gets the message"],
            assumptions=["Recipient email is known"],
            status=PlanStatus.IN_PROGRESS,
        ),
        active_subgoal_id="s2",
        artifacts=[PlanArtifact(name="weather_report", content="Hong Kong: 26C", kind="note")],
        replanning_count=1,
    )

    response = DebugRunResponse.from_runtime_result(
        agent_id="planner-agent",
        result=RuntimeRunResult(final_answer="draft ready", state=state),
    )

    dumped = response.model_dump()

    assert dumped["plan"]["goal"] == "Write and send a weather email"
    assert dumped["plan"]["subgoals"][0]["status"] == "completed"
    assert dumped["active_subgoal_id"] == "s2"
    assert dumped["artifacts"] == [{"name": "weather_report", "content": "Hong Kong: 26C", "kind": "note"}]
    assert dumped["replanning_count"] == 1
