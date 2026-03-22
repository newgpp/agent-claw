"""OpenAI-compatible LLM adapter for the ReAct runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

from clawcore.llm.base import BaseLLM
from clawcore.models import ReActStep, ToolCall
from clawcore.runtime.session import AgentSession
from common.observability import logger

_PROTOCOL_INSTRUCTIONS = """
You are the planner for a ReAct agent runtime.
Return exactly one JSON object with this schema:
{
  "thought": "string",
  "action": {"name": "tool_name", "payload": {}} | null,
  "final_answer": "string" | null
}
Rules:
- Return valid JSON only. Do not wrap it in markdown fences.
- If you need a tool, set "action" and set "final_answer" to null.
- If you can answer the user, set "final_answer" and set "action" to null.
- Never leave both "action" and "final_answer" null.
- If an existing scratchpad observation already answers the user, return `final_answer` instead of calling another tool.
- Do not repeat the same tool call with the same payload unless the prior result failed or the user explicitly asked for more detail.
- Prefer using the available skill summaries first.
- If a skill seems relevant but you need its full procedure, call `read_skill` before downstream tools.
- Do not call `read_skill` when the current context is already sufficient to answer.
- Use `exec_script` only for declared script file paths such as `scripts/foo.py`.
- Never pass shell commands like `curl ...` or `python ...` as the `script` value for `exec_script`.
- If a skill summary recommends `curl` or shows `curl` command examples, call the `curl` tool directly instead of `exec_script`.
""".strip()


@dataclass(frozen=True, slots=True)
class OpenAIReActConfig:
    """Configuration for an OpenAI-compatible ReAct client."""

    model: str
    api_key: str
    base_url: str | None = None
    temperature: float = 0.0
    max_tokens: int | None = None
    extra_create_args: dict[str, object] = field(default_factory=dict)


class OpenAIReActLLM(BaseLLM):
    """Drive ReAct steps through an OpenAI-compatible chat completions API."""

    def __init__(self, config: OpenAIReActConfig, client: AsyncOpenAI | None = None) -> None:
        self.config = config
        self.client = client or AsyncOpenAI(api_key=config.api_key, base_url=config.base_url)

    async def next_step(self, session: AgentSession) -> ReActStep:
        messages = self._build_messages(session)
        logger.info(
            "LLM request model={} payload={}",
            self.config.model,
            self._dump_json_for_log({"messages": messages}),
        )
        response = await self._create_completion(messages)
        content = self._extract_content(response)
        logger.info("LLM response model={} content={}", self.config.model, content)
        return self._parse_step(content)

    async def _create_completion(self, messages: list[dict[str, str]]) -> Any:
        request: dict[str, object] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
        }
        if self.config.max_tokens is not None:
            request["max_tokens"] = self.config.max_tokens
        request.update(self.config.extra_create_args)
        return await self.client.chat.completions.create(**request)

    def _build_messages(self, session: AgentSession) -> list[dict[str, str]]:
        state = session.state
        user_context: dict[str, object] = {
            "user_input": state.user_input,
            "active_skill": state.active_skill.name if state.active_skill is not None else None,
            "loaded_skills": [skill.name for skill in state.loaded_skills],
            "scratchpad_observations": list(state.scratchpad),
            "plan": {
                "goal": state.plan.goal,
                "status": state.plan.status,
                "subgoals": [
                    {
                        "id": subgoal.id,
                        "task": subgoal.task,
                        "status": subgoal.status,
                        "notes": subgoal.notes,
                    }
                    for subgoal in state.plan.subgoals
                ],
                "success_criteria": list(state.plan.success_criteria),
                "assumptions": list(state.plan.assumptions),
            }
            if state.plan is not None
            else None,
            "active_subgoal_id": state.active_subgoal_id,
            "active_subgoal_task": state.active_subgoal_task,
            "active_subgoal_notes": state.active_subgoal_notes,
            "artifacts": [
                {"name": artifact.name, "kind": artifact.kind, "content": artifact.content}
                for artifact in state.artifacts
            ],
        }

        return [
            {
                "role": "system",
                "content": "\n\n".join(part for part in [state.system_prompt, _PROTOCOL_INSTRUCTIONS] if part),
            },
            {
                "role": "user",
                "content": "Runtime context:\n" + self._dump_json_for_log(user_context),
            },
        ]

    def _extract_content(self, response: Any) -> str:
        choices = getattr(response, "choices", None)
        if not choices:
            raise RuntimeError("OpenAI client returned no choices.")
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("OpenAI client returned an empty message content.")
        return content.strip()

    def _parse_step(self, content: str) -> ReActStep:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"OpenAI response was not valid JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("OpenAI response must be a JSON object.")

        thought = str(payload.get("thought", "")).strip()
        if not thought:
            raise RuntimeError("OpenAI response must include a non-empty 'thought'.")

        raw_action = payload.get("action")
        raw_final_answer = payload.get("final_answer")

        action: ToolCall | None = None
        if raw_action is not None:
            if not isinstance(raw_action, dict):
                raise RuntimeError("'action' must be an object or null.")
            name = str(raw_action.get("name", "")).strip()
            if not name:
                raise RuntimeError("'action.name' must be a non-empty string.")
            payload_obj = raw_action.get("payload", {})
            if not isinstance(payload_obj, dict):
                raise RuntimeError("'action.payload' must be an object.")
            action = ToolCall(name=name, payload=payload_obj)

        final_answer: str | None = None
        if raw_final_answer is not None:
            final_answer = str(raw_final_answer).strip()
            if not final_answer:
                final_answer = None

        if (action is None) == (final_answer is None):
            raise RuntimeError("OpenAI response must provide exactly one of 'action' or 'final_answer'.")

        return ReActStep(thought=thought, action=action, final_answer=final_answer)

    def _dump_json_for_log(self, payload: dict[str, object]) -> str:
        """Render log payloads consistently without escaping Unicode input."""
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
