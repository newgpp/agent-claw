"""Dependency helpers for the FastAPI API layer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from agents import get_agent, load_agent_spec
from agents.base import BaseAgent


@dataclass(frozen=True, slots=True)
class AgentCatalogEntry:
    """Metadata describing one configured agent exposed by the API."""

    id: str
    type: str
    model: str
    config_path: str


def resolve_agents_config_dir() -> Path:
    """Return the configured directory that stores agent JSON configs."""
    override = os.environ.get("AGENT_CLAW_AGENTS_DIR", "").strip()
    if override:
        return Path(override).resolve()
    return (Path(__file__).resolve().parents[3] / "configs" / "agents").resolve()


def get_agent_catalog() -> list[AgentCatalogEntry]:
    """List configured agents without constructing runtime instances."""
    config_dir = resolve_agents_config_dir()
    if not config_dir.exists() or not config_dir.is_dir():
        return []

    catalog: list[AgentCatalogEntry] = []
    for path in sorted(config_dir.glob("*.json")):
        spec = load_agent_spec(path)
        catalog.append(
            AgentCatalogEntry(
                id=path.stem,
                type=spec.type,
                model=spec.model,
                config_path=str(path),
            )
        )
    return catalog


def get_agent_by_id(agent_id: str) -> BaseAgent:
    """Resolve and construct one configured agent by its config filename stem."""
    normalized = agent_id.strip()
    if not normalized:
        raise KeyError("Agent id must not be empty.")
    config_path = resolve_agents_config_dir() / f"{normalized}.json"
    if not config_path.exists() or not config_path.is_file():
        raise KeyError(f"Agent '{normalized}' was not found.")
    return get_agent(str(config_path.resolve()))
