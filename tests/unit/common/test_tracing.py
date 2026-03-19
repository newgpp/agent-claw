from common.tracing import TraceCollector


def test_trace_collector_records_serializable_events() -> None:
    collector = TraceCollector()

    collector.record("tool", "called echo", tool_name="echo")

    assert len(collector.events) == 1
    event = collector.events[0]
    assert event.kind == "tool"
    assert event.message == "called echo"
    assert event.data == {"tool_name": "echo"}
    assert isinstance(event.to_dict()["timestamp"], str)
