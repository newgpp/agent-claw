"""OpenAI-compatible LLM adapter for the ReAct runtime."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

from clawcore.llm.base import BaseLLM
from clawcore.models import ReActStep, TokenUsage, ToolCall
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
- Runtime observations may be summarized for brevity. Do not assume missing detail was written to a file unless a prior tool result explicitly says it was written.
- Do not repeat the same tool call with the same payload unless the prior result failed or the user explicitly asked for more detail.
- Prefer using the available skill summaries first.
- If a skill seems relevant but you need its full procedure, call `read_skill` before downstream tools.
- Do not call `read_skill` when the current context is already sufficient to answer.
- Do not call `read` for a file path unless the user provided that path or a prior successful tool result explicitly created or referenced that file.
- When emitting long string payloads, output plain text content with normal JSON escaping only. Do not insert unnecessary backslashes before markdown punctuation.
- When `execution.active_subgoal` is present, it is the only executable scope for this turn.
- In planned runs, use `user_request` only as background constraints such as language, destination, recipient, or final output expectations.
- Do not start later subgoals just because you can infer them from the user request, plan summary, or prior observations.
- As soon as the active subgoal is satisfied, return `final_answer` immediately with a concise handoff summary instead of calling another tool.
- When `runtime.file_cache` already includes the file content you need, use it directly instead of calling `read` again.
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
        usage = self._extract_usage(response)
        session.state.token_usage.executor.add(usage)
        logger.info(
            "LLM response model={} usage={} content={}",
            self.config.model,
            self._dump_json_for_log(self._usage_to_payload(usage)),
            content,
        )
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
        state.sync_views()
        user_context = state.build_executor_context()

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

    def _extract_usage(self, response: Any) -> TokenUsage:
        usage = getattr(response, "usage", None)
        if usage is None:
            return TokenUsage()
        return TokenUsage(
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
        )

    def _usage_to_payload(self, usage: TokenUsage) -> dict[str, int]:
        return {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
        }

    def _parse_step(self, content: str) -> ReActStep:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            try:
                payload = json.loads(self._repair_common_json_escapes(content))
            except json.JSONDecodeError:
                logger.error(
                    "LLM response JSON parse failed model={} error_type={} detail={} content={}",
                    self.config.model,
                    type(exc).__name__,
                    str(exc),
                    content,
                )
                raise RuntimeError(f"OpenAI response was not valid JSON: {exc}") from exc

        if not isinstance(payload, dict):
            logger.error(
                "LLM response shape invalid model={} payload_type={} content={}",
                self.config.model,
                type(payload).__name__,
                content,
            )
            raise RuntimeError("OpenAI response must be a JSON object.")

        thought = str(payload.get("thought", "")).strip()
        if not thought:
            logger.error("LLM response missing thought model={} content={}", self.config.model, content)
            raise RuntimeError("OpenAI response must include a non-empty 'thought'.")

        raw_action = payload.get("action")
        raw_final_answer = payload.get("final_answer")

        action: ToolCall | None = None
        if raw_action is not None:
            if not isinstance(raw_action, dict):
                logger.error("LLM response action shape invalid model={} content={}", self.config.model, content)
                raise RuntimeError("'action' must be an object or null.")
            name = str(raw_action.get("name", "")).strip()
            if not name:
                logger.error("LLM response missing action.name model={} content={}", self.config.model, content)
                raise RuntimeError("'action.name' must be a non-empty string.")
            payload_obj = raw_action.get("payload", {})
            if not isinstance(payload_obj, dict):
                logger.error("LLM response action.payload invalid model={} content={}", self.config.model, content)
                raise RuntimeError("'action.payload' must be an object.")
            action = ToolCall(name=name, payload=payload_obj)

        final_answer: str | None = None
        if raw_final_answer is not None:
            final_answer = str(raw_final_answer).strip()
            if not final_answer:
                final_answer = None

        if (action is None) == (final_answer is None):
            logger.error(
                "LLM response action/final_answer invariant failed model={} content={}",
                self.config.model,
                content,
            )
            raise RuntimeError("OpenAI response must provide exactly one of 'action' or 'final_answer'.")

        return ReActStep(thought=thought, action=action, final_answer=final_answer)

    def _repair_common_json_escapes(self, content: str) -> str:
        """Repair common invalid backslash escapes sometimes emitted in long JSON strings."""
        return re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", content)

    def _dump_json_for_log(self, payload: dict[str, object]) -> str:
        """Render log payloads consistently without escaping Unicode input."""
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
