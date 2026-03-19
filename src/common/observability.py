from __future__ import annotations

import sys
from contextvars import ContextVar, Token
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from loguru import logger

RUN_ID_HEADER = "X-Run-Id"
SESSION_ID_HEADER = "X-Session-Id"
TRACE_ID_HEADER = "X-Trace-Id"

run_id_ctx: ContextVar[str] = ContextVar("run_id", default="-")
session_id_ctx: ContextVar[str] = ContextVar("session_id", default="-")
trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="-")


def new_id() -> str:
    """Create a new runtime identifier."""
    return uuid4().hex


def new_trace_id() -> str:
    """Create a new trace identifier."""
    return new_id()


def new_run_id() -> str:
    """Create a new run identifier."""
    return new_id()


def new_session_id() -> str:
    """Create a new session identifier."""
    return new_id()


def bind_trace_id(trace_id: str | None = None) -> Token[str]:
    """Bind a trace id to the current execution context."""
    return trace_id_ctx.set(trace_id or new_trace_id())


def bind_run_id(run_id: str | None = None) -> Token[str]:
    """Bind a run id to the current execution context."""
    return run_id_ctx.set(run_id or new_run_id())


def bind_session_id(session_id: str | None = None) -> Token[str]:
    """Bind a session id to the current execution context."""
    return session_id_ctx.set(session_id or new_session_id())


def reset_trace_id(token: Token[str]) -> None:
    """Reset the current execution context to its previous trace id."""
    trace_id_ctx.reset(token)


def reset_run_id(token: Token[str]) -> None:
    """Reset the current execution context to its previous run id."""
    run_id_ctx.reset(token)


def reset_session_id(token: Token[str]) -> None:
    """Reset the current execution context to its previous session id."""
    session_id_ctx.reset(token)


def setup_loguru(
    service_name: str,
    log_to_stdout: bool = True,
    log_to_file: bool = False,
    log_dir: str = "logs",
) -> None:
    """Configure shared loguru sinks and trace-aware formatting."""
    logger.remove()
    logger.configure(
        extra={"service": service_name},
        patcher=lambda record: record["extra"].update(
            {
                "run_id": run_id_ctx.get("-"),
                "session_id": session_id_ctx.get("-"),
                "trace_id": trace_id_ctx.get("-"),
            }
        ),
    )
    if log_to_stdout:
        logger.add(
            sys.stdout,
            level="INFO",
            enqueue=True,
            backtrace=False,
            diagnose=False,
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {extra[service]} "
                "| run_id={extra[run_id]} | session_id={extra[session_id]} "
                "| trace_id={extra[trace_id]} | {message}"
            ),
        )

    if log_to_file:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        date_suffix = datetime.now().strftime("%Y-%m-%d")
        file_path = Path(log_dir) / f"{service_name}.{date_suffix}.log"
        logger.add(
            str(file_path),
            level="INFO",
            enqueue=True,
            backtrace=False,
            diagnose=False,
            encoding="utf-8",
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {extra[service]} "
                "| run_id={extra[run_id]} | session_id={extra[session_id]} "
                "| trace_id={extra[trace_id]} | {message}"
            ),
        )


def current_observability_context() -> dict[str, str]:
    """Return the currently bound runtime identifiers."""
    return {
        "run_id": run_id_ctx.get("-"),
        "session_id": session_id_ctx.get("-"),
        "trace_id": trace_id_ctx.get("-"),
    }


def current_trace_headers() -> dict[str, str]:
    """Build outbound headers for downstream trace propagation."""
    return {
        RUN_ID_HEADER: run_id_ctx.get("-"),
        SESSION_ID_HEADER: session_id_ctx.get("-"),
        TRACE_ID_HEADER: trace_id_ctx.get("-"),
    }
