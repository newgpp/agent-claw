"""Agent factory helpers for JSON-backed app wiring."""

from __future__ import annotations

import json
import os
import importlib
import inspect
import pkgutil
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from agents.base import BaseAgent
from agents.openai_runtime_agent import OpenAIRuntimeAgent, OpenAIRuntimeAgentOptions
import agents.tools as agent_tools_package
from agents.runtime_agent import AgentRunConfig
from clawcore.llm import OpenAIReActConfig
from clawcore.skilling.loader import load_skills
from clawcore.tooling import BaseTool, ExecScriptTool, ReadTool, WriteTool


@dataclass(frozen=True, slots=True)
class OpenAIRuntimeAgentSpec:
    """JSON-backed app wiring spec for a singleton OpenAI runtime agent.

    This model captures the stable, file-based inputs needed to assemble an
    ``OpenAIRuntimeAgent`` from configuration rather than handwritten Python
    wiring. The spec is intentionally limited to construction-time concerns:
    runtime model settings, agent-owned tool names, selected skills from the
    fixed ``skills/`` directory, and basic run defaults.
    """

    # Stable agent kind identifier used by the factory dispatch.
    type: str
    # Planner model name passed to the OpenAI-compatible client.
    model: str
    # Agent-owned extension tool names resolved from src/agents/tools/.
    tools: tuple[str, ...] = ()
    # Skill names to load from the fixed skills/ directory.
    skills: tuple[str, ...] = ()
    # Extra system prompt guidance applied to every run.
    base_instructions: str = ""
    # Upper bound for the ReAct loop.
    max_steps: int = 5
    # Optional default workspace for file tools, resolved from config location.
    workspace_dir: str | None = None
    # Whether the factory should auto-register the built-in read_skill tool.
    include_read_skill: bool = True
    # Optional OpenAI-compatible API base URL override.
    base_url: str | None = None
    # Planner sampling temperature.
    temperature: float = 0.0
    # Optional max token limit for planner responses.
    max_tokens: int | None = None
    # Free-form extension slot for future app-level metadata.
    metadata: dict[str, object] = field(default_factory=dict)


def load_agent_spec(path: str | Path) -> OpenAIRuntimeAgentSpec:
    """Load and validate an agent spec from a JSON file."""
    config_path = Path(path).resolve()
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid agent JSON in {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"Agent config at {config_path} must be a JSON object.")

    type_name = str(raw.get("type", "")).strip()
    if type_name != "openai-runtime":
        raise ValueError(f"Unsupported agent type: {type_name or '(missing)'}")

    model = str(raw.get("model", "")).strip()
    if not model:
        raise ValueError("Agent config must define a non-empty 'model'.")

    raw_tools = raw.get("tools", [])
    if not isinstance(raw_tools, list):
        raise ValueError("'tools' must be a JSON array of strings.")
    tools: list[str] = []
    for item in raw_tools:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("'tools' entries must be non-empty strings.")
        tools.append(item.strip())

    raw_skills = raw.get("skills", [])
    if not isinstance(raw_skills, list):
        raise ValueError("'skills' must be a JSON array of strings.")
    skills: list[str] = []
    for item in raw_skills:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("'skills' entries must be non-empty strings.")
        skills.append(item.strip())

    max_steps = raw.get("max_steps", 5)
    if not isinstance(max_steps, int) or max_steps <= 0:
        raise ValueError("'max_steps' must be a positive integer.")

    include_read_skill = raw.get("include_read_skill", True)
    if not isinstance(include_read_skill, bool):
        raise ValueError("'include_read_skill' must be a boolean.")

    temperature = raw.get("temperature", 0.0)
    if not isinstance(temperature, (int, float)):
        raise ValueError("'temperature' must be numeric.")

    max_tokens = raw.get("max_tokens")
    if max_tokens is not None and (not isinstance(max_tokens, int) or max_tokens <= 0):
        raise ValueError("'max_tokens' must be a positive integer when provided.")

    def optional_string(field_name: str) -> str | None:
        value = raw.get(field_name)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"'{field_name}' must be a string when provided.")
        normalized = value.strip()
        return normalized or None

    metadata = raw.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("'metadata' must be a JSON object when provided.")

    return OpenAIRuntimeAgentSpec(
        type=type_name,
        model=model,
        tools=tuple(tools),
        skills=tuple(skills),
        base_instructions=optional_string("base_instructions") or "",
        max_steps=max_steps,
        workspace_dir=optional_string("workspace_dir"),
        include_read_skill=include_read_skill,
        base_url=optional_string("base_url"),
        temperature=float(temperature),
        max_tokens=max_tokens,
        metadata=dict(metadata),
    )


def build_agent(spec: OpenAIRuntimeAgentSpec, *, config_path: str | Path | None = None) -> BaseAgent:
    """Build a runtime-backed agent from a validated spec."""
    if spec.type != "openai-runtime":
        raise ValueError(f"Unsupported agent type: {spec.type}")

    resolved_config_path = Path(config_path).resolve() if config_path is not None else None
    tools = _build_default_builtin_tools() + [_build_agent_tool(name) for name in spec.tools]
    loaded_skills = []
    if spec.skills:
        skills_root = _resolve_fixed_skills_dir(resolved_config_path)
        available_skills = load_skills(skills_root)
        available_by_name = {skill.name: skill for skill in available_skills}
        missing = [name for name in spec.skills if name not in available_by_name]
        if missing:
            raise ValueError(f"Unknown skills in fixed skills directory: {', '.join(missing)}")
        loaded_skills = [available_by_name[name] for name in spec.skills]

    workspace_dir = _resolve_workspace_dir(
        spec=spec,
        config_path=resolved_config_path,
    )

    run_config = AgentRunConfig(
        base_instructions=spec.base_instructions,
        skills=tuple(loaded_skills),
        max_steps=spec.max_steps,
        workspace_dir=workspace_dir,
    )
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required.")
    llm_config = OpenAIReActConfig(
        model=spec.model,
        api_key=api_key,
        base_url=spec.base_url,
        temperature=spec.temperature,
        max_tokens=spec.max_tokens,
    )
    return OpenAIRuntimeAgent(
        tools=tools,
        options=OpenAIRuntimeAgentOptions(
            run_config=run_config,
            llm_config=llm_config,
            include_read_skill=spec.include_read_skill,
        ),
    )


@lru_cache(maxsize=None)
def get_agent(config_path: str) -> BaseAgent:
    """Build and cache a singleton agent for a config path."""
    spec = load_agent_spec(config_path)
    return build_agent(spec, config_path=config_path)


def clear_agent_cache() -> None:
    """Clear the singleton agent cache."""
    get_agent.cache_clear()


def _build_default_builtin_tools() -> list[BaseTool]:
    return [ReadTool(), WriteTool(), ExecScriptTool()]


def _build_agent_tool(name: str) -> BaseTool:
    normalized = name.strip().lower()
    tool_classes = _discover_agent_tool_classes()
    tool_class = tool_classes.get(normalized)
    if tool_class is None:
        raise ValueError(f"Unsupported agent tool: {name}")
    return tool_class()


@lru_cache(maxsize=1)
def _discover_agent_tool_classes() -> dict[str, type[BaseTool]]:
    tool_classes: dict[str, type[BaseTool]] = {}
    for module_info in pkgutil.iter_modules(agent_tools_package.__path__):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{agent_tools_package.__name__}.{module_info.name}")
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, BaseTool) or obj is BaseTool:
                continue
            if obj.__module__ != module.__name__:
                continue
            tool_name = str(getattr(obj, "name", "")).strip().lower()
            if not tool_name:
                continue
            if tool_name in tool_classes:
                raise ValueError(f"Duplicate agent tool name discovered: {tool_name}")
            tool_classes[tool_name] = obj
    return tool_classes


def _resolve_fixed_skills_dir(config_path: Path | None) -> Path:
    if config_path is not None:
        current = config_path.parent
        while True:
            candidate = (current / "skills").resolve()
            if candidate.exists() and candidate.is_dir():
                return candidate
            if current.parent == current:
                break
            current = current.parent
    candidate = Path("skills").resolve()
    if candidate.exists() and candidate.is_dir():
        return candidate
    raise ValueError("Could not resolve fixed skills directory named 'skills'.")


def _resolve_workspace_dir(*, spec: OpenAIRuntimeAgentSpec, config_path: Path | None) -> Path:
    if spec.workspace_dir:
        workspace_dir = Path(spec.workspace_dir)
        if not workspace_dir.is_absolute() and config_path is not None:
            workspace_dir = config_path.parent / workspace_dir
        return workspace_dir.resolve()

    agent_id = config_path.stem if config_path is not None else "default"
    project_root = config_path.parent.parent if config_path is not None else Path.cwd()
    return (project_root / "works" / agent_id).resolve()
