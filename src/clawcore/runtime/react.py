"""Async ReAct runtime implementation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from clawcore.llm.base import BaseLLM
from clawcore.models import ReActStep, ToolResult
from clawcore.runtime.result import RuntimeRunResult
from clawcore.skilling.models import SkillDefinition
from clawcore.tooling.base import ToolExecutionContext
from clawcore.tooling.executor import ToolExecutor
from clawcore.tooling.result import ToolExecutionStatus
from common.events import RunFinished, RunStarted, ToolCalled, ToolReturned
from common.observability import (
    bind_run_id,
    bind_session_id,
    bind_trace_id,
    logger,
    reset_run_id,
    reset_session_id,
    reset_trace_id,
)
from common.context import RunContext
from clawcore.runtime.hooks import RuntimeHook, emit_hook
from clawcore.runtime.prompt_builder import SystemPromptBuilder
from clawcore.runtime.session import AgentSession
from clawcore.runtime.state import RuntimeState


@dataclass(slots=True)
class ReActRuntime:
    """Executes a ReAct loop using an async LLM and tool executor."""

    llm: BaseLLM
    tool_executor: ToolExecutor
    prompt_builder: SystemPromptBuilder = field(default_factory=SystemPromptBuilder)
    event_hook: RuntimeHook | None = None

    async def run(
        self,
        user_input: str,
        *,
        skills: list[SkillDefinition] | None = None,
        active_skill: SkillDefinition | None = None,
        max_steps: int = 5,
        base_instructions: str = "",
        workspace_dir: Path | None = None,
    ) -> str:
        result = await self.run_debug(
            user_input,
            skills=skills,
            active_skill=active_skill,
            max_steps=max_steps,
            base_instructions=base_instructions,
            workspace_dir=workspace_dir,
        )
        return result.final_answer

    async def run_debug(
        self,
        user_input: str,
        *,
        skills: list[SkillDefinition] | None = None,
        active_skill: SkillDefinition | None = None,
        max_steps: int = 5,
        base_instructions: str = "",
        workspace_dir: Path | None = None,
    ) -> RuntimeRunResult:
        run_context = RunContext(user_input=user_input)
        trace_token = bind_trace_id(run_context.trace_id)
        run_token = bind_run_id(run_context.run_id)
        session_token = bind_session_id(run_context.session_id)
        resolved_skills = tuple(skills or [])
        try:
            state = RuntimeState(
                user_input=user_input,
                available_skills=resolved_skills,
                active_skill=active_skill,
                loaded_skills=[active_skill] if active_skill is not None else [],
            )
            session = AgentSession(state=state)
            state.system_prompt = self.prompt_builder.build(
                skills=list(resolved_skills),
                tool_names=self.tool_executor.registry.names(),
                tool_descriptions=self.tool_executor.registry.descriptions(),
                base_instructions=base_instructions,
            )
            run_started = RunStarted(
                run_id=run_context.run_id,
                session_id=run_context.session_id,
                trace_id=run_context.trace_id,
                payload={"user_input": user_input},
            )
            run_context.emit(run_started)
            await emit_hook(run_started, self.event_hook)
            state.events.append(run_started)
            state.trace.record("input", user_input)
            successful_tool_calls: dict[str, str] = {}

            for step_index in range(1, max_steps + 1):
                step = await self.llm.next_step(session)
                self._record_step(state, step_index, step)

                if step.final_answer is not None:
                    finished = RunFinished(
                        run_id=run_context.run_id,
                        session_id=run_context.session_id,
                        trace_id=run_context.trace_id,
                        payload={"final_answer": step.final_answer},
                    )
                    run_context.emit(finished)
                    await emit_hook(finished, self.event_hook)
                    state.events.append(finished)
                    state.trace.record("final_answer", step.final_answer)
                    logger.info("Finished ReAct loop in {} step(s)", step_index)
                    return RuntimeRunResult(final_answer=step.final_answer, state=state)

                if step.action is None:
                    raise RuntimeError("Planner returned neither an action nor a final answer.")

                called = ToolCalled(
                    run_id=run_context.run_id,
                    session_id=run_context.session_id,
                    trace_id=run_context.trace_id,
                    payload={"tool": step.action.name, "payload": step.action.payload},
                )
                run_context.emit(called)
                await emit_hook(called, self.event_hook)
                state.events.append(called)

                action_signature = self._action_signature(step.action.name, step.action.payload)
                cached_content = successful_tool_calls.get(action_signature)
                if cached_content is not None:
                    result_content = (
                        "Duplicate tool call avoided. Reuse the previous successful result to answer the user.\n"
                        f"Previous result: {cached_content}"
                    )
                    result_status = ToolExecutionStatus.SUCCESS
                    result_tool_name = step.action.name
                    logger.info(
                        "Skipped duplicate tool call name={} payload={}",
                        step.action.name,
                        step.action.payload,
                    )
                else:
                    result = await self.tool_executor.execute(
                        step.action.name,
                        step.action.payload,
                        context=ToolExecutionContext(
                            workspace_dir=workspace_dir or Path.cwd(),
                            active_skill=state.active_skill,
                            available_skills=resolved_skills,
                        ),
                    )
                    result_content = result.content
                    result_status = result.status
                    result_tool_name = result.tool_name
                returned = ToolReturned(
                    run_id=run_context.run_id,
                    session_id=run_context.session_id,
                    trace_id=run_context.trace_id,
                    payload={
                        "tool": result_tool_name,
                        "status": result_status,
                        "content": result_content,
                    },
                )
                run_context.emit(returned)
                await emit_hook(returned, self.event_hook)
                state.events.append(returned)

                if result_status != ToolExecutionStatus.SUCCESS:
                    raise RuntimeError(result_content)

                tool_result = ToolResult(name=result_tool_name, content=result_content)
                state.tool_results.append(tool_result)
                successful_tool_calls.setdefault(action_signature, result_content)
                if step.action.name == "read_skill":
                    selected_skill = self._resolve_skill_from_payload(step.action.payload, resolved_skills)
                    if selected_skill is not None:
                        state.active_skill = selected_skill
                        if selected_skill not in state.loaded_skills:
                            state.loaded_skills.append(selected_skill)
                observation = self._build_observation(
                    tool_name=result_tool_name,
                    result_content=result_content,
                    action_payload=step.action.payload,
                    skills=resolved_skills,
                )
                session.append_observation(observation)
                state.trace.record("observation", observation)
        finally:
            reset_session_id(session_token)
            reset_run_id(run_token)
            reset_trace_id(trace_token)

        raise RuntimeError("ReAct loop exceeded max_steps without a final answer.")

    def _record_step(self, state: RuntimeState, step_index: int, step: ReActStep) -> None:
        state.trace.record("thought", f"step={step_index} {step.thought}")
        logger.debug("Step {} thought: {}", step_index, step.thought)
        if step.action is not None:
            state.trace.record("action", f"{step.action.name} -> {step.action.payload}")

    def _resolve_skill_from_payload(
        self,
        payload: dict[str, object],
        skills: tuple[SkillDefinition, ...],
    ) -> SkillDefinition | None:
        requested = str(payload.get("skill", payload.get("skill_name", ""))).strip().lower()
        if not requested:
            return None
        for skill in skills:
            if skill.name.lower() == requested:
                return skill
        return None

    def _action_signature(self, tool_name: str, payload: dict[str, object]) -> str:
        return f"{tool_name}:{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"

    def _build_observation(
        self,
        *,
        tool_name: str,
        result_content: str,
        action_payload: dict[str, object],
        skills: tuple[SkillDefinition, ...],
    ) -> str:
        if tool_name != "read_skill":
            return f"{tool_name}: {result_content}"

        selected_skill = self._resolve_skill_from_payload(action_payload, skills)
        payload = {
            "skill_name": selected_skill.name if selected_skill is not None else str(
                action_payload.get("skill", action_payload.get("skill_name", ""))
            ).strip(),
            "summary": self._summarize_skill_content(result_content, selected_skill),
            "call_hint": self._extract_skill_call_hint(result_content),
            "full_doc_available": True,
        }
        return "read_skill_summary: " + json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def _summarize_skill_content(
        self,
        content: str,
        skill: SkillDefinition | None,
        *,
        limit: int = 3,
    ) -> list[str]:
        summaries: list[str] = []
        if skill is not None and skill.description.strip():
            summaries.append(skill.description.strip())

        for line in content.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            if cleaned.startswith(("---", "#", "```", "- ", "* ")):
                continue
            if ":" in cleaned and len(cleaned.split()) <= 4:
                continue
            if cleaned.startswith(("name:", "description:", "homepage:", "metadata:")):
                continue
            if cleaned in summaries:
                continue
            summaries.append(cleaned)
            if len(summaries) >= limit:
                break

        return summaries[:limit]

    def _extract_skill_call_hint(self, content: str) -> str | None:
        for line in content.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            if cleaned.startswith(("curl ", "curl\"", "curl \"", "curl '")):
                return cleaned
            if "wttr.in/" in cleaned or "https://" in cleaned:
                return cleaned

        match = re.search(r"`([^`]*(?:curl|https?://|wttr\.in/)[^`]*)`", content)
        if match is not None:
            return match.group(1).strip()
        return None
