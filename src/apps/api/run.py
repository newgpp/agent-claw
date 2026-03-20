"""Local development entrypoint for the FastAPI API server."""

from __future__ import annotations

import os

import uvicorn

from apps.env import load_dotenv


def resolve_api_bind() -> tuple[str, int]:
    """Return the configured host/port for local API serving."""
    load_dotenv()
    host = os.environ.get("AGENT_CLAW_API_HOST", "127.0.0.1").strip() or "127.0.0.1"
    raw_port = os.environ.get("AGENT_CLAW_API_PORT", "8000").strip() or "8000"
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError("AGENT_CLAW_API_PORT must be a valid integer.") from exc
    return host, port


def main() -> None:
    """Run the API server using .env-backed host and port values."""
    host, port = resolve_api_bind()
    uvicorn.run("apps.api.main:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
