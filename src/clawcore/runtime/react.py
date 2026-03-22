"""Async ReAct runtime implementation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from clawcore.llm.base import BaseLLM, BasePlanner
from clawcore.models import ExecutionPlan, PlanArtifact, PlanStatus, PlanSubgoal, ReActStep, ToolResult
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
from clawcore.runtime.prompt_builder import PlanningPromptBuilder, SystemPromptBuilder
from clawcore.runtime.session import AgentSession
from clawcore.runtime.state import RuntimeState


@dataclass(slots=True)
class ReActRuntime:
    """Executes a ReAct loop using an async LLM and tool executor."""

    llm: BaseLLM
    tool_executor: ToolExecutor
    planner: BasePlanner | None = None
    prompt_builder: SystemPromptBuilder = field(default_factory=SystemPromptBuilder)
    planning_prompt_builder: PlanningPromptBuilder = field(default_factory=PlanningPromptBuilder)
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
        return await self._run_debug_direct(
            user_input,
            skills=skills,
            active_skill=active_skill,
            max_steps=max_steps,
            base_instructions=base_instructions,
            workspace_dir=workspace_dir,
        )

    async def run_planned(
        self,
        user_input: str,
        *,
        skills: list[SkillDefinition] | None = None,
        active_skill: SkillDefinition | None = None,
        max_steps: int = 5,
        base_instructions: str = "",
        workspace_dir: Path | None = None,
    ) -> str:
        result = await self.run_debug_planner_first(
            user_input,
            skills=skills,
            active_skill=active_skill,
            max_steps=max_steps,
            base_instructions=base_instructions,
            workspace_dir=workspace_dir,
        )
        return result.final_answer

    async def run_planner_first(
        self,
        user_input: str,
        *,
        skills: list[SkillDefinition] | None = None,
        active_skill: SkillDefinition | None = None,
        max_steps: int = 5,
        base_instructions: str = "",
        workspace_dir: Path | None = None,
    ) -> str:
        result = await self.run_debug_planner_first(
            user_input,
            skills=skills,
            active_skill=active_skill,
            max_steps=max_steps,
            base_instructions=base_instructions,
            workspace_dir=workspace_dir,
        )
        return result.final_answer

    async def run_debug_planned(
        self,
        user_input: str,
        *,
        skills: list[SkillDefinition] | None = None,
        active_skill: SkillDefinition | None = None,
        max_steps: int = 5,
        base_instructions: str = "",
        workspace_dir: Path | None = None,
    ) -> RuntimeRunResult:
        return await self.run_debug_planner_first(
            user_input,
            skills=skills,
            active_skill=active_skill,
            max_steps=max_steps,
            base_instructions=base_instructions,
            workspace_dir=workspace_dir,
        )

    async def run_debug_planner_first(
        self,
        user_input: str,
        *,
        skills: list[SkillDefinition] | None = None,
        active_skill: SkillDefinition | None = None,
        max_steps: int = 5,
        base_instructions: str = "",
        workspace_dir: Path | None = None,
    ) -> RuntimeRunResult:
        if self.planner is None:
            raise NotImplementedError("Planned execution requires a configured planner.")

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
            state.system_prompt = self.planning_prompt_builder.build(
                skills=list(resolved_skills),
                tool_names=self.tool_executor.registry.names(),
                tool_descriptions=self.tool_executor.registry.descriptions(),
                base_instructions=base_instructions,
            )
            await self._emit_run_started(run_context, state)
            state.trace.record("input", user_input)
            state.sync_views()

            plan = await self.planner.create_plan(session)
            state.plan = plan
            state.plan.status = PlanStatus.IN_PROGRESS
            state.sync_views()
            logger.info(
                "Plan created goal={} subgoal_count={} subgoal_ids={}",
                plan.goal,
                len(plan.subgoals),
                [subgoal.id for subgoal in plan.subgoals],
            )
            state.trace.record(
                "plan",
                plan.goal,
                subgoals=[subgoal.task for subgoal in plan.subgoals],
                success_criteria=list(plan.success_criteria),
            )
            final_answer = await self._execute_plan(
                session=session,
                run_context=run_context,
                plan=plan,
                max_steps=max_steps,
                workspace_dir=workspace_dir,
                skills=resolved_skills,
            )
            finished = await self._emit_run_finished(run_context, state, final_answer=final_answer)
            logger.info("Finished planner-first runtime with {} subgoal(s)", len(plan.subgoals))
            return RuntimeRunResult(final_answer=finished, state=state)
        except Exception as exc:
            logger.exception(
                "Planner-first runtime failed user_input={} active_subgoal_id={} error_type={} detail={}",
                user_input,
                state.active_subgoal_id if "state" in locals() else None,
                type(exc).__name__,
                str(exc),
            )
            raise
        finally:
            reset_session_id(session_token)
            reset_run_id(run_token)
            reset_trace_id(trace_token)

    async def _execute_plan(
        self,
        *,
        session: AgentSession,
        run_context: RunContext,
        plan: ExecutionPlan,
        max_steps: int,
        workspace_dir: Path | None,
        skills: tuple[SkillDefinition, ...],
    ) -> str:
        if plan.is_direct_answer:
            plan.status = PlanStatus.COMPLETED
            logger.info("Finished planner-first runtime with empty plan")
            return plan.goal

        final_answer = ""
        for subgoal in plan.subgoals:
            session.state.active_subgoal_id = subgoal.id
            session.state.active_subgoal_task = subgoal.task
            session.state.active_subgoal_notes = subgoal.notes
            session.state.prompt_observations.clear()
            subgoal.status = PlanStatus.IN_PROGRESS
            session.state.sync_views()
            session.state.trace.record("subgoal.started", subgoal.task, subgoal_id=subgoal.id)
            subgoal_answer = await self._run_subgoal_loop(
                session=session,
                run_context=run_context,
                max_steps=max_steps,
                workspace_dir=workspace_dir,
                skills=skills,
            )
            artifact = PlanArtifact(
                name=subgoal.id,
                content=subgoal_answer,
                kind="subgoal_result",
            )
            session.state.artifacts.append(artifact)
            session.state.step_summaries.append(
                self._build_step_summary(subgoal=subgoal, answer=subgoal_answer)
            )
            session.state.trace.record(
                "artifact",
                artifact.content,
                artifact_name=artifact.name,
                artifact_kind=artifact.kind,
            )
            subgoal.status = PlanStatus.COMPLETED
            session.state.prompt_observations.clear()
            session.state.sync_views()
            session.state.trace.record("subgoal.completed", subgoal.task, subgoal_id=subgoal.id)
            final_answer = subgoal_answer

        session.state.active_subgoal_id = None
        session.state.active_subgoal_task = None
        session.state.active_subgoal_notes = None
        session.state.plan.status = PlanStatus.COMPLETED
        session.state.sync_views()
        return final_answer

    async def _run_debug_direct(
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
            await self._emit_run_started(run_context, state)
            state.trace.record("input", user_input)
            state.sync_views()
            final_answer = await self._run_subgoal_loop(
                session=session,
                run_context=run_context,
                max_steps=max_steps,
                workspace_dir=workspace_dir,
                skills=resolved_skills,
            )
            finished = await self._emit_run_finished(run_context, state, final_answer=final_answer)
            logger.info("Finished ReAct loop")
            return RuntimeRunResult(final_answer=finished, state=state)
        except Exception as exc:
            logger.exception(
                "Direct runtime failed user_input={} active_subgoal_id={} error_type={} detail={}",
                user_input,
                state.active_subgoal_id if "state" in locals() else None,
                type(exc).__name__,
                str(exc),
            )
            raise
        finally:
            reset_session_id(session_token)
            reset_run_id(run_token)
            reset_trace_id(trace_token)

    async def _run_subgoal_loop(
        self,
        *,
        session: AgentSession,
        run_context: RunContext,
        max_steps: int,
        workspace_dir: Path | None,
        skills: tuple[SkillDefinition, ...],
    ) -> str:
        successful_tool_calls: dict[str, str] = {}

        for step_index in range(1, max_steps + 1):
            try:
                step = await self.llm.next_step(session)
            except Exception as exc:
                logger.exception(
                    "LLM step failed step_index={} active_subgoal_id={} error_type={} detail={}",
                    step_index,
                    session.state.active_subgoal_id,
                    type(exc).__name__,
                    str(exc),
                )
                raise
            self._record_step(session.state, step_index, step)

            if step.final_answer is not None:
                return step.final_answer

            if step.action is None:
                raise RuntimeError("Planner returned neither an action nor a final answer.")

            result_tool_name, result_status, result_content = await self._execute_tool_action(
                run_context=run_context,
                state=session.state,
                action_name=step.action.name,
                action_payload=step.action.payload,
                successful_tool_calls=successful_tool_calls,
                workspace_dir=workspace_dir,
                skills=skills,
            )
            if result_status != ToolExecutionStatus.SUCCESS:
                logger.error(
                    "Tool action returned non-success step_index={} tool_name={} status={} active_subgoal_id={} detail={}",
                    step_index,
                    result_tool_name,
                    result_status,
                    session.state.active_subgoal_id,
                    result_content,
                )
                raise RuntimeError(result_content)

            tool_result = ToolResult(name=result_tool_name, content=result_content)
            session.state.tool_results.append(tool_result)
            successful_tool_calls.setdefault(
                self._action_signature(step.action.name, step.action.payload),
                result_content,
            )
            self._cache_written_file(
                state=session.state,
                action_name=step.action.name,
                action_payload=step.action.payload,
                workspace_dir=workspace_dir,
            )
            if step.action.name == "read_skill":
                selected_skill = self._resolve_skill_from_payload(step.action.payload, skills)
                if selected_skill is not None:
                    session.state.active_skill = selected_skill
                    if selected_skill not in session.state.loaded_skills:
                        session.state.loaded_skills.append(selected_skill)
            observation = self._build_observation(
                tool_name=result_tool_name,
                result_content=result_content,
                action_payload=step.action.payload,
                skills=skills,
            )
            prompt_observation = self._build_prompt_observation(
                tool_name=result_tool_name,
                result_content=result_content,
                action_payload=step.action.payload,
                skills=skills,
            )
            session.append_observation(observation, prompt_observation=prompt_observation)
            session.state.trace.record("observation", observation)
            fast_path_answer = self._try_fast_path_completion(
                state=session.state,
                tool_name=result_tool_name,
                result_content=result_content,
            )
            if fast_path_answer is not None:
                return fast_path_answer

        raise RuntimeError("ReAct loop exceeded max_steps without a final answer.")

    async def _execute_tool_action(
        self,
        *,
        run_context: RunContext,
        state: RuntimeState,
        action_name: str,
        action_payload: dict[str, object],
        successful_tool_calls: dict[str, str],
        workspace_dir: Path | None,
        skills: tuple[SkillDefinition, ...],
    ) -> tuple[str, ToolExecutionStatus, str]:
        called = ToolCalled(
            run_id=run_context.run_id,
            session_id=run_context.session_id,
            trace_id=run_context.trace_id,
            payload={"tool": action_name, "payload": action_payload},
        )
        run_context.emit(called)
        await emit_hook(called, self.event_hook)
        state.events.append(called)
        state.sync_views()

        action_signature = self._action_signature(action_name, action_payload)
        cached_content = successful_tool_calls.get(action_signature)
        if cached_content is not None:
            result_content = (
                "Duplicate tool call avoided. Reuse the previous successful result to answer the user.\n"
                f"Previous result: {cached_content}"
            )
            result_status = ToolExecutionStatus.SUCCESS
            result_tool_name = action_name
            logger.info("Skipped duplicate tool call name={} payload={}", action_name, action_payload)
        else:
            result = await self.tool_executor.execute(
                action_name,
                action_payload,
                context=ToolExecutionContext(
                    workspace_dir=workspace_dir or Path.cwd(),
                    active_skill=state.active_skill,
                    available_skills=skills,
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
        state.sync_views()
        return result_tool_name, result_status, result_content

    async def _emit_run_started(self, run_context: RunContext, state: RuntimeState) -> None:
        run_started = RunStarted(
            run_id=run_context.run_id,
            session_id=run_context.session_id,
            trace_id=run_context.trace_id,
            payload={"user_input": state.user_input},
        )
        run_context.emit(run_started)
        await emit_hook(run_started, self.event_hook)
        state.events.append(run_started)
        state.sync_views()

    async def _emit_run_finished(
        self,
        run_context: RunContext,
        state: RuntimeState,
        *,
        final_answer: str,
    ) -> str:
        finished = RunFinished(
            run_id=run_context.run_id,
            session_id=run_context.session_id,
            trace_id=run_context.trace_id,
            payload={"final_answer": final_answer},
        )
        run_context.emit(finished)
        await emit_hook(finished, self.event_hook)
        state.events.append(finished)
        state.trace.record("final_answer", final_answer)
        state.sync_views()
        return final_answer

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
            "recommended_tools": self._extract_skill_recommended_tools(result_content, selected_skill),
            "command_examples": self._extract_skill_command_examples(result_content),
            "call_hint": self._extract_skill_call_hint(result_content),
            "full_doc_available": True,
        }
        return "read_skill_summary: " + json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def _build_prompt_observation(
        self,
        *,
        tool_name: str,
        result_content: str,
        action_payload: dict[str, object],
        skills: tuple[SkillDefinition, ...],
    ) -> str:
        if tool_name == "tavily":
            return self._summarize_tavily_observation(result_content)
        return self._build_observation(
            tool_name=tool_name,
            result_content=result_content,
            action_payload=action_payload,
            skills=skills,
        )

    def _build_step_summary(self, *, subgoal: PlanSubgoal, answer: str) -> str:
        return f"{subgoal.id}: {subgoal.task} -> {self._summarize_for_prompt(answer)}"

    def _summarize_for_prompt(self, value: str, *, limit: int = 280) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 3] + "..."

    def _summarize_tavily_observation(self, result_content: str) -> str:
        try:
            payload = json.loads(result_content)
        except json.JSONDecodeError:
            return f"tavily: {self._summarize_for_prompt(result_content)}"

        if not isinstance(payload, dict):
            return f"tavily: {self._summarize_for_prompt(result_content)}"

        query = str(payload.get("query", "")).strip()
        results = payload.get("results", [])
        total_results = len(results) if isinstance(results, list) else 0
        highlights: list[str] = []
        if isinstance(results, list):
            for item in results[:3]:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title", "")).strip()
                url = str(item.get("url", "")).strip()
                if title and url:
                    highlights.append(f"{title} ({url})")
                elif title:
                    highlights.append(title)
                elif url:
                    highlights.append(url)
        summary = {
            "query": query,
            "result_count": total_results,
            "top_results": highlights,
        }
        return "tavily_summary: " + json.dumps(summary, ensure_ascii=False, sort_keys=True)

    def _cache_written_file(
        self,
        *,
        state: RuntimeState,
        action_name: str,
        action_payload: dict[str, object],
        workspace_dir: Path | None,
    ) -> None:
        if action_name != "write":
            return
        raw_path = str(action_payload.get("path", "")).strip()
        content = action_payload.get("content")
        if not raw_path or not isinstance(content, str):
            return
        resolved_path = self._resolve_workspace_path(raw_path, workspace_dir)
        state.cached_files[str(resolved_path)] = content
        state.sync_views()

    def _resolve_workspace_path(self, raw_path: str, workspace_dir: Path | None) -> Path:
        candidate = Path(raw_path)
        if candidate.is_absolute():
            return candidate
        base_dir = workspace_dir or Path.cwd()
        return (base_dir / candidate).resolve()

    def _try_fast_path_completion(
        self,
        *,
        state: RuntimeState,
        tool_name: str,
        result_content: str,
    ) -> str | None:
        task = (state.active_subgoal_task or "").strip()
        if not task:
            return None

        expected_tools = self._infer_expected_tools_for_task(task)
        if len(expected_tools) != 1 or tool_name not in expected_tools:
            return None

        if tool_name == "read_skill":
            return None

        subgoal_id = state.active_subgoal_id or "subgoal"
        return (
            f"Subgoal {subgoal_id} completed: "
            f"{self._build_fast_path_summary(tool_name=tool_name, result_content=result_content)}"
        )

    def _infer_expected_tools_for_task(self, task: str) -> set[str]:
        lower_task = task.lower()
        expected: set[str] = set()
        explicit_tool_aliases: dict[str, Iterable[str]] = {
            "curl": ("curl", "wttr.in"),
            "tavily": ("tavily",),
            "send_email": ("send_email",),
            "read_skill": ("read_skill",),
            "exec_script": ("exec_script",),
            "read": ("read ", "read the", "read file"),
            "write": ("write ", "write it to a file", "write to a file", "save to a file"),
        }
        for tool_name, aliases in explicit_tool_aliases.items():
            if any(alias in lower_task for alias in aliases):
                expected.add(tool_name)
        return expected

    def _build_fast_path_summary(self, *, tool_name: str, result_content: str) -> str:
        if tool_name == "write":
            return self._summarize_for_prompt(result_content)
        if tool_name == "send_email":
            return self._summarize_for_prompt(result_content)
        if tool_name == "tavily":
            summary = self._summarize_tavily_observation(result_content)
            return summary.removeprefix("tavily_summary: ")
        return self._summarize_for_prompt(result_content)

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
            if cleaned.startswith(("---", "#", "```", "- ", "* ", "✅", "❌")):
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

    def _extract_skill_recommended_tools(
        self,
        content: str,
        skill: SkillDefinition | None,
    ) -> list[str]:
        tools: list[str] = []
        if skill is not None:
            for tool in skill.tools:
                if tool not in tools:
                    tools.append(tool)

        for line in content.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            if cleaned.startswith(("curl ", "curl\"", "curl \"", "curl '")) and "curl" not in tools:
                tools.append("curl")
            if cleaned.startswith(("python ", "python3 ", "./")) and "exec_script" not in tools:
                tools.append("exec_script")
        return tools

    def _extract_skill_command_examples(self, content: str, *, limit: int = 3) -> list[str]:
        commands: list[str] = []
        for raw_line in content.splitlines():
            cleaned = raw_line.strip()
            if not cleaned:
                continue
            if cleaned.startswith(("curl ", "curl\"", "curl \"", "curl '", "python ", "python3 ", "./")):
                commands.append(cleaned)
            if len(commands) >= limit:
                break
        return commands

    def _extract_skill_call_hint(self, content: str) -> str | None:
        command_examples = self._extract_skill_command_examples(content, limit=1)
        if command_examples:
            return command_examples[0]

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
