from clawcore.models import ExecutionPlan, PlanArtifact, PlanStatus, PlanSubgoal
from clawcore.runtime import RuntimeState


def test_runtime_state_defaults_support_direct_mode_without_plan() -> None:
    state = RuntimeState(user_input="hello")

    assert state.plan is None
    assert state.step_summaries == []
    assert state.prompt_state["user_input"] == "hello"
    assert state.debug_state["scratchpad"] == []
    assert state.active_subgoal_id is None
    assert state.active_subgoal_task is None
    assert state.active_subgoal_notes is None
    assert state.artifacts == []
    assert state.replanning_count == 0


def test_runtime_state_can_hold_structured_plan_data() -> None:
    plan = ExecutionPlan(
        goal="Write and send a weather email",
        subgoals=[
            PlanSubgoal(id="s1", task="Fetch weather", status=PlanStatus.COMPLETED),
            PlanSubgoal(id="s2", task="Draft email", status=PlanStatus.IN_PROGRESS),
        ],
        success_criteria=["Email is drafted"],
        assumptions=["Recipient is available"],
        status=PlanStatus.IN_PROGRESS,
    )
    artifact = PlanArtifact(name="weather_report", content="Hong Kong: 26C", kind="note")

    state = RuntimeState(
        user_input="write a weather email",
        plan=plan,
        active_subgoal_id="s2",
        active_subgoal_task="Draft email",
        active_subgoal_notes="Use the weather artifact as context.",
        artifacts=[artifact],
        replanning_count=1,
    )

    assert state.plan is plan
    assert state.plan.subgoals[0].status == PlanStatus.COMPLETED
    assert state.active_subgoal_id == "s2"
    assert state.active_subgoal_task == "Draft email"
    assert state.active_subgoal_notes == "Use the weather artifact as context."
    assert state.artifacts == [artifact]
    assert state.prompt_state["active_subgoal_id"] == "s2"
    assert state.replanning_count == 1


def test_runtime_state_builds_executor_context_with_plan_summary_only() -> None:
    plan = ExecutionPlan(
        goal="Write and send a weather email",
        subgoals=[
            PlanSubgoal(id="s1", task="Fetch weather", status=PlanStatus.COMPLETED, notes="Use curl."),
            PlanSubgoal(id="s2", task="Draft email", status=PlanStatus.IN_PROGRESS, notes="Write in Chinese."),
            PlanSubgoal(id="s3", task="Send email", status=PlanStatus.PENDING, notes="Deliver to recipient."),
        ],
        success_criteria=["Email is sent"],
        assumptions=["Recipient is valid"],
        status=PlanStatus.IN_PROGRESS,
    )

    state = RuntimeState(
        user_input="write a weather email in Chinese",
        plan=plan,
        active_subgoal_id="s2",
        active_subgoal_task="Draft email",
        active_subgoal_notes="Write in Chinese.",
    )

    context = state.build_executor_context()

    assert context["user_request"] == {"raw_input": "write a weather email in Chinese"}
    assert context["execution"]["active_subgoal"] == {  # type: ignore[index]
        "id": "s2",
        "task": "Draft email",
        "notes": "Write in Chinese.",
    }
    assert context["plan_summary"]["completed_subgoal_ids"] == ["s1"]  # type: ignore[index]
    assert context["plan_summary"]["remaining_subgoal_ids"] == ["s3"]  # type: ignore[index]
    assert "subgoals" not in context["plan_summary"]  # type: ignore[operator]


def test_runtime_state_executor_context_includes_cached_file_content() -> None:
    state = RuntimeState(user_input="email the guide")
    state.cached_files["/tmp/guide.md"] = "# Guide\n\nBring sunscreen."
    state.sync_views()

    context = state.build_executor_context()

    assert context["runtime"]["file_cache"] == [  # type: ignore[index]
        {"path": "/tmp/guide.md", "content": "# Guide\n\nBring sunscreen."}
    ]


def test_execution_plan_shape_helpers_cover_direct_and_single_step_cases() -> None:
    direct_plan = ExecutionPlan(goal="Answer directly")
    single_step_plan = ExecutionPlan(
        goal="Fetch the weather",
        subgoals=[PlanSubgoal(id="s1", task="Read weather data")],
    )

    assert direct_plan.is_direct_answer
    assert not direct_plan.is_single_step
    assert not single_step_plan.is_direct_answer
    assert single_step_plan.is_single_step
