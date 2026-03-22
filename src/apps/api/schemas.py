"""Pydantic schemas and serializers for the FastAPI API layer."""

from __future__ import annotations

from pydantic import BaseModel, Field

from apps.api.dependencies import AgentCatalogEntry
from clawcore.models import ExecutionPlan, PlanArtifact, PlanStatus, PlanSubgoal, RuntimeTokenUsage, TokenUsage
from clawcore.runtime import RuntimeRunResult


class HealthResponse(BaseModel):
    status: str


class AgentSummaryResponse(BaseModel):
    id: str
    type: str
    model: str
    config_path: str

    @classmethod
    def from_catalog(cls, entry: AgentCatalogEntry) -> "AgentSummaryResponse":
        return cls(
            id=entry.id,
            type=entry.type,
            model=entry.model,
            config_path=entry.config_path,
        )


class RunRequest(BaseModel):
    agent_id: str = Field(min_length=1)
    user_input: str = Field(min_length=1)


class RunResponse(BaseModel):
    agent_id: str
    final_answer: str


class ToolResultResponse(BaseModel):
    name: str
    content: str


class PlanSubgoalResponse(BaseModel):
    id: str
    task: str
    status: PlanStatus
    notes: str

    @classmethod
    def from_model(cls, subgoal: PlanSubgoal) -> "PlanSubgoalResponse":
        return cls(
            id=subgoal.id,
            task=subgoal.task,
            status=subgoal.status,
            notes=subgoal.notes,
        )


class PlanArtifactResponse(BaseModel):
    name: str
    content: str
    kind: str

    @classmethod
    def from_model(cls, artifact: PlanArtifact) -> "PlanArtifactResponse":
        return cls(name=artifact.name, content=artifact.content, kind=artifact.kind)


class PlanResponse(BaseModel):
    goal: str
    subgoals: list[PlanSubgoalResponse]
    success_criteria: list[str]
    assumptions: list[str]
    status: PlanStatus
    is_direct_answer: bool
    is_single_step: bool

    @classmethod
    def from_model(cls, plan: ExecutionPlan) -> "PlanResponse":
        return cls(
            goal=plan.goal,
            subgoals=[PlanSubgoalResponse.from_model(item) for item in plan.subgoals],
            success_criteria=list(plan.success_criteria),
            assumptions=list(plan.assumptions),
            status=plan.status,
            is_direct_answer=plan.is_direct_answer,
            is_single_step=plan.is_single_step,
        )


class TokenUsageResponse(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    @classmethod
    def from_model(cls, usage: TokenUsage) -> "TokenUsageResponse":
        return cls(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )


class RuntimeTokenUsageResponse(BaseModel):
    planner: TokenUsageResponse
    executor: TokenUsageResponse
    total: TokenUsageResponse

    @classmethod
    def from_model(cls, usage: RuntimeTokenUsage) -> "RuntimeTokenUsageResponse":
        return cls(
            planner=TokenUsageResponse.from_model(usage.planner),
            executor=TokenUsageResponse.from_model(usage.executor),
            total=TokenUsageResponse.from_model(usage.total),
        )


class PromptArtifactResponse(BaseModel):
    name: str
    kind: str
    summary: str


class PromptStateResponse(BaseModel):
    user_input: str
    active_skill: str | None = None
    loaded_skills: list[str] = Field(default_factory=list)
    step_summaries: list[str] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    plan: dict[str, object] | None = None
    active_subgoal_id: str | None = None
    active_subgoal_task: str | None = None
    active_subgoal_notes: str | None = None
    artifacts: list[PromptArtifactResponse] = Field(default_factory=list)


class DebugStateResponse(BaseModel):
    scratchpad: list[str] = Field(default_factory=list)
    tool_results: list[ToolResultResponse] = Field(default_factory=list)
    events: list[dict[str, object]] = Field(default_factory=list)
    trace: list[dict[str, object]] = Field(default_factory=list)


class DebugRunResponse(BaseModel):
    agent_id: str
    final_answer: str
    step_summaries: list[str] = Field(default_factory=list)
    prompt_state: PromptStateResponse
    debug_state: DebugStateResponse
    plan: PlanResponse | None = None
    active_subgoal_id: str | None = None
    artifacts: list[PlanArtifactResponse] = Field(default_factory=list)
    replanning_count: int = 0
    token_usage: RuntimeTokenUsageResponse

    @classmethod
    def from_runtime_result(cls, *, agent_id: str, result: RuntimeRunResult) -> "DebugRunResponse":
        result.state.sync_views()
        prompt_artifacts = [
            PromptArtifactResponse(
                name=str(item.get("name", "")),
                kind=str(item.get("kind", "")),
                summary=str(item.get("summary", "")),
            )
            for item in result.state.prompt_state.get("artifacts", [])
            if isinstance(item, dict)
        ]
        debug_tool_results = [
            ToolResultResponse(name=item.name, content=item.content)
            for item in result.state.tool_results
        ]
        return cls(
            agent_id=agent_id,
            final_answer=result.final_answer,
            step_summaries=list(result.state.step_summaries),
            prompt_state=PromptStateResponse(
                user_input=str(result.state.prompt_state.get("user_input", result.state.user_input)),
                active_skill=(
                    str(result.state.prompt_state["active_skill"])
                    if result.state.prompt_state.get("active_skill") is not None
                    else None
                ),
                loaded_skills=[
                    str(item) for item in result.state.prompt_state.get("loaded_skills", []) if isinstance(item, str)
                ],
                step_summaries=[
                    str(item) for item in result.state.prompt_state.get("step_summaries", []) if isinstance(item, str)
                ],
                observations=[
                    str(item) for item in result.state.prompt_state.get("observations", []) if isinstance(item, str)
                ],
                plan=(
                    result.state.prompt_state.get("plan")
                    if isinstance(result.state.prompt_state.get("plan"), dict)
                    else None
                ),
                active_subgoal_id=(
                    str(result.state.prompt_state["active_subgoal_id"])
                    if result.state.prompt_state.get("active_subgoal_id") is not None
                    else None
                ),
                active_subgoal_task=(
                    str(result.state.prompt_state["active_subgoal_task"])
                    if result.state.prompt_state.get("active_subgoal_task") is not None
                    else None
                ),
                active_subgoal_notes=(
                    str(result.state.prompt_state["active_subgoal_notes"])
                    if result.state.prompt_state.get("active_subgoal_notes") is not None
                    else None
                ),
                artifacts=prompt_artifacts,
            ),
            debug_state=DebugStateResponse(
                scratchpad=list(result.state.scratchpad),
                tool_results=debug_tool_results,
                events=[event.to_dict() for event in result.state.events],
                trace=[entry.to_dict() for entry in result.state.trace.events],
            ),
            plan=PlanResponse.from_model(result.state.plan) if result.state.plan is not None else None,
            active_subgoal_id=result.state.active_subgoal_id,
            artifacts=[PlanArtifactResponse.from_model(item) for item in result.state.artifacts],
            replanning_count=result.state.replanning_count,
            token_usage=RuntimeTokenUsageResponse.from_model(result.state.token_usage),
        )
