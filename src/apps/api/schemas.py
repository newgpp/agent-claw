"""Pydantic schemas and serializers for the FastAPI API layer."""

from __future__ import annotations

from pydantic import BaseModel, Field

from apps.api.dependencies import AgentCatalogEntry
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


class DebugRunResponse(BaseModel):
    agent_id: str
    final_answer: str
    scratchpad: list[str]
    tool_results: list[ToolResultResponse]
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
            events=[event.to_dict() for event in result.state.events],
            trace=[entry.to_dict() for entry in result.state.trace.events],
        )
