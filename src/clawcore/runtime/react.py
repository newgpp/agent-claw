"""Async ReAct runtime implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from clawcore.llm.base import BaseLLM
from clawcore.models import ReActStep, ToolResult
from clawcore.skilling.models import SkillDefinition
from clawcore.tooling.base import ToolExecutionContext
from clawcore.tooling.executor import ToolExecutor
from clawcore.tooling.result import ToolExecutionStatus
from common.events import RunFinished, RunStarted, ToolCalled, ToolReturned
from common.observability import logger
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
        run_context = RunContext(user_input=user_input)
        state = RuntimeState(user_input=user_input, active_skill=active_skill)
        session = AgentSession(state=state)
        tool_context = ToolExecutionContext(
            workspace_dir=workspace_dir or Path.cwd(),
            active_skill=state.active_skill,
        )
        state.system_prompt = self.prompt_builder.build(
            skills=skills or [],
            tool_names=self.tool_executor.registry.names(),
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
                return step.final_answer

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

            result = await self.tool_executor.execute(
                step.action.name,
                step.action.payload,
                context=tool_context,
            )
            returned = ToolReturned(
                run_id=run_context.run_id,
                session_id=run_context.session_id,
                trace_id=run_context.trace_id,
                payload={"tool": result.tool_name, "status": result.status, "content": result.content},
            )
            run_context.emit(returned)
            await emit_hook(returned, self.event_hook)
            state.events.append(returned)

            if result.status != ToolExecutionStatus.SUCCESS:
                raise RuntimeError(result.content)

            tool_result = ToolResult(name=result.tool_name, content=result.content)
            state.tool_results.append(tool_result)
            observation = f"{result.tool_name}: {result.content}"
            session.append_observation(observation)
            state.trace.record("observation", observation)

        raise RuntimeError("ReAct loop exceeded max_steps without a final answer.")

    def _record_step(self, state: RuntimeState, step_index: int, step: ReActStep) -> None:
        state.trace.record("thought", f"step={step_index} {step.thought}")
        logger.debug("Step {} thought: {}", step_index, step.thought)
        if step.action is not None:
            state.trace.record("action", f"{step.action.name} -> {step.action.payload}")
