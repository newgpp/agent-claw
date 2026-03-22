from clawcore.models import ExecutionPlan, PlanArtifact, PlanStatus, PlanSubgoal
from clawcore.runtime import RuntimeState


def test_runtime_state_defaults_support_direct_mode_without_plan() -> None:
    state = RuntimeState(user_input="hello")

    assert state.plan is None
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
    assert state.replanning_count == 1
