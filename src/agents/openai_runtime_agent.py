"""Runtime-backed agent that uses an OpenAI-compatible planner."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from agents.base import AgentDescriptor
from agents.runtime_agent import AgentRunConfig, RuntimeAgent
from clawcore.llm import OpenAIPlanner, OpenAIReActConfig, OpenAIReActLLM
from clawcore.runtime import ReActRuntime
from clawcore.tooling import BaseTool, ReadSkillTool, ToolExecutor, ToolPolicy, ToolRegistry


def _require_env(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required.")
    return value


def _parse_optional_float(env: Mapping[str, str], name: str) -> float | None:
    raw = env.get(name, "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid float.") from exc


def _parse_optional_int(env: Mapping[str, str], name: str) -> int | None:
    raw = env.get(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid integer.") from exc


def load_openai_react_config_from_env(
    env: Mapping[str, str] | None = None,
) -> OpenAIReActConfig:
    """Build an OpenAI-compatible LLM config from environment variables."""
    resolved_env = env or os.environ
    config = OpenAIReActConfig(
        model=_require_env(resolved_env, "OPENAI_MODEL"),
        api_key=_require_env(resolved_env, "OPENAI_API_KEY"),
        base_url=resolved_env.get("OPENAI_BASE_URL", "").strip() or None,
    )

    temperature = _parse_optional_float(resolved_env, "OPENAI_TEMPERATURE")
    max_tokens = _parse_optional_int(resolved_env, "OPENAI_MAX_TOKENS")
    if temperature is not None:
        config = OpenAIReActConfig(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=temperature,
            max_tokens=config.max_tokens,
            extra_create_args=config.extra_create_args,
        )
    if max_tokens is not None:
        config = OpenAIReActConfig(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=max_tokens,
            extra_create_args=config.extra_create_args,
        )
    return config


def _build_tool_registry(tools: Sequence[BaseTool], *, include_read_skill: bool) -> ToolRegistry:
    registry = ToolRegistry()
    if include_read_skill and not any(tool.name == ReadSkillTool.name for tool in tools):
        registry.register(ReadSkillTool())
    for tool in tools:
        registry.register(tool)
    return registry


@dataclass(frozen=True, slots=True)
class OpenAIRuntimeAgentOptions:
    """Options for constructing an OpenAI-backed runtime agent."""

    run_config: AgentRunConfig | None = None
    llm_config: OpenAIReActConfig | None = None
    include_read_skill: bool = True


class OpenAIRuntimeAgent(RuntimeAgent):
    """Generic runtime-backed agent that plans with an OpenAI-compatible LLM."""

    descriptor = AgentDescriptor(
        name="openai-runtime-agent",
        description="Runtime-backed agent powered by an OpenAI-compatible planner.",
    )

    def __init__(
        self,
        *,
        tools: Sequence[BaseTool],
        options: OpenAIRuntimeAgentOptions | None = None,
        client: Any | None = None,
        policy: ToolPolicy | None = None,
    ) -> None:
        resolved_options = options or OpenAIRuntimeAgentOptions()
        llm_config = resolved_options.llm_config or load_openai_react_config_from_env()
        registry = _build_tool_registry(
            tools,
            include_read_skill=resolved_options.include_read_skill,
        )
        runtime = ReActRuntime(
            llm=OpenAIReActLLM(llm_config, client=client),
            planner=OpenAIPlanner(llm_config, client=client),
            tool_executor=ToolExecutor(registry, policy=policy or ToolPolicy()),
        )
        super().__init__(runtime, config=resolved_options.run_config)
