"""FastAPI app for running configured agents over HTTP."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException
from starlette.requests import Request
from starlette.responses import Response

from agents.base import BaseAgent
from apps.env import load_dotenv, resolve_api_logging
from apps.api.dependencies import AgentCatalogEntry, get_agent_by_id, get_agent_catalog
from apps.api.schemas import (
    AgentSummaryResponse,
    DebugRunResponse,
    HealthResponse,
    RunRequest,
    RunResponse,
)
from common.observability import bind_trace_id, logger, reset_trace_id, setup_loguru


def create_app() -> FastAPI:
    load_dotenv()
    log_to_file, log_dir = resolve_api_logging()
    setup_loguru(
        service_name="agent-claw-api",
        log_to_file=log_to_file,
        log_dir=log_dir,
    )
    app = FastAPI(title="agent-claw API")

    @app.middleware("http")
    async def bind_request_trace_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        trace_token = bind_trace_id()
        try:
            return await call_next(request)
        finally:
            reset_trace_id(trace_token)

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
        logger.info(
            "API request path=/runs agent_id={} user_input={}",
            payload.agent_id,
            payload.user_input,
        )
        try:
            final_answer = await agent.run(payload.user_input)
        except ValueError as exc:
            logger.exception(
                "API request failed path=/runs agent_id={} error_type={} detail={}",
                payload.agent_id,
                type(exc).__name__,
                str(exc),
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except NotImplementedError as exc:
            logger.exception(
                "API request failed path=/runs agent_id={} error_type={} detail={}",
                payload.agent_id,
                type(exc).__name__,
                str(exc),
            )
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except RuntimeError as exc:
            logger.exception(
                "API request failed path=/runs agent_id={} error_type={} detail={}",
                payload.agent_id,
                type(exc).__name__,
                str(exc),
            )
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return RunResponse(agent_id=payload.agent_id, final_answer=final_answer)

    @app.post("/runs/debug", response_model=DebugRunResponse)
    async def run_agent_debug(
        payload: RunRequest,
        agent: BaseAgent = Depends(_resolve_agent_for_run),
    ) -> DebugRunResponse:
        logger.info(
            "API request path=/runs/debug agent_id={} user_input={}",
            payload.agent_id,
            payload.user_input,
        )
        try:
            result = await agent.run_debug(payload.user_input)
        except ValueError as exc:
            logger.exception(
                "API request failed path=/runs/debug agent_id={} error_type={} detail={}",
                payload.agent_id,
                type(exc).__name__,
                str(exc),
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except NotImplementedError as exc:
            logger.exception(
                "API request failed path=/runs/debug agent_id={} error_type={} detail={}",
                payload.agent_id,
                type(exc).__name__,
                str(exc),
            )
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except RuntimeError as exc:
            logger.exception(
                "API request failed path=/runs/debug agent_id={} error_type={} detail={}",
                payload.agent_id,
                type(exc).__name__,
                str(exc),
            )
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
