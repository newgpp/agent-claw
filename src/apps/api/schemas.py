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

    @classmethod
    def from_model(cls, plan: ExecutionPlan) -> "PlanResponse":
        return cls(
            goal=plan.goal,
            subgoals=[PlanSubgoalResponse.from_model(item) for item in plan.subgoals],
            success_criteria=list(plan.success_criteria),
            assumptions=list(plan.assumptions),
            status=plan.status,
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


class DebugRunResponse(BaseModel):
    agent_id: str
    final_answer: str
    scratchpad: list[str]
    tool_results: list[ToolResultResponse]
    plan: PlanResponse | None = None
    active_subgoal_id: str | None = None
    artifacts: list[PlanArtifactResponse] = Field(default_factory=list)
    replanning_count: int = 0
    token_usage: RuntimeTokenUsageResponse
    events: list[dict[str, object]]
    trace: list[dict[str, object]]

    @classmethod
    def from_runtime_result(cls, *, agent_id: str, result: RuntimeRunResult) -> "DebugRunResponse":
        return cls(
            agent_id=agent_id,
            final_answer=result.final_answer,
            scratchpad=list(result.state.scratchpad),
            tool_results=[
                ToolResultResponse(name=item.name, content=item.content)
                for item in result.state.tool_results
            ],
            plan=PlanResponse.from_model(result.state.plan) if result.state.plan is not None else None,
            active_subgoal_id=result.state.active_subgoal_id,
            artifacts=[PlanArtifactResponse.from_model(item) for item in result.state.artifacts],
            replanning_count=result.state.replanning_count,
            token_usage=RuntimeTokenUsageResponse.from_model(result.state.token_usage),
            events=[event.to_dict() for event in result.state.events],
            trace=[entry.to_dict() for entry in result.state.trace.events],
        )
