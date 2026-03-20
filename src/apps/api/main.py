"""FastAPI app for running configured agents over HTTP."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException

from agents.base import BaseAgent
from apps.api.dependencies import AgentCatalogEntry, get_agent_by_id, get_agent_catalog
from apps.api.schemas import (
    AgentSummaryResponse,
    DebugRunResponse,
    HealthResponse,
    RunRequest,
    RunResponse,
)


def create_app() -> FastAPI:
    app = FastAPI(title="agent-claw API")

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/agents", response_model=list[AgentSummaryResponse])
    async def list_agents(
        catalog: list[AgentCatalogEntry] = Depends(get_agent_catalog),
    ) -> list[AgentSummaryResponse]:
        return [AgentSummaryResponse.from_catalog(entry) for entry in catalog]

    @app.post("/runs", response_model=RunResponse)
    async def run_agent(
        payload: RunRequest,
        agent: BaseAgent = Depends(_resolve_agent_for_run),
    ) -> RunResponse:
        try:
            final_answer = await agent.run(
                payload.user_input,
                workspace_dir=Path(payload.workspace_dir) if payload.workspace_dir else None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return RunResponse(agent_id=payload.agent_id, final_answer=final_answer)

    @app.post("/runs/debug", response_model=DebugRunResponse)
    async def run_agent_debug(
        payload: RunRequest,
        agent: BaseAgent = Depends(_resolve_agent_for_run),
    ) -> DebugRunResponse:
        try:
            result = await agent.run_debug(
                payload.user_input,
                workspace_dir=Path(payload.workspace_dir) if payload.workspace_dir else None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return DebugRunResponse.from_runtime_result(agent_id=payload.agent_id, result=result)

    return app


def _resolve_agent_for_run(payload: RunRequest) -> BaseAgent:
    try:
        return get_agent_by_id(payload.agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


app = create_app()
