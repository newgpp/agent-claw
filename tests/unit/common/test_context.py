from common.context import RunContext
from common.events import RunStarted


def test_run_context_has_sane_defaults() -> None:
    context = RunContext(user_input="hello")

    assert context.user_input == "hello"
    assert context.run_id
    assert context.session_id
    assert context.trace_id
    assert context.metadata == {}
    assert context.events == []
    assert context.trace.events == []


def test_run_context_can_record_runtime_events() -> None:
    context = RunContext(user_input="hello")
    event = RunStarted(
        run_id=context.run_id,
        session_id=context.session_id,
        trace_id=context.trace_id,
        payload={"user_input": context.user_input},
    )

    context.emit(event)

    assert context.events == [event]
