"""OpenAI-compatible planner adapter for structured plan generation."""

from __future__ import annotations

import json
from typing import Any

from clawcore.llm.base import BasePlanner
from clawcore.llm.openai_react import OpenAIReActConfig
from clawcore.models import ExecutionPlan, PlanStatus, PlanSubgoal
from clawcore.runtime.session import AgentSession
from common.observability import logger
from openai import AsyncOpenAI

_PLANNER_PROTOCOL_INSTRUCTIONS = """
You are the planner for a multi-step agent runtime.
Return exactly one JSON object with this schema:
{
  "goal": "string",
  "subgoals": [
    {
      "id": "string",
      "task": "string",
      "notes": "string"
    }
  ],
  "success_criteria": ["string"],
  "assumptions": ["string"]
}
Rules:
- Return valid JSON only. Do not wrap it in markdown fences.
- Create subgoals only when the task needs multiple dependent steps.
- Keep subgoals concrete and execution-oriented.
- Use stable short ids like "s1", "s2", "s3".
- Do not include statuses in the JSON; the runtime owns execution status.
- Prefer an empty assumptions list over speculative assumptions.
""".strip()


class OpenAIPlanner(BasePlanner):
    """Drive structured plan generation through an OpenAI-compatible chat API."""

    def __init__(
        self,
        config: OpenAIReActConfig,
        *,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.config = config
        self.client = client or AsyncOpenAI(api_key=config.api_key, base_url=config.base_url)

    async def create_plan(self, session: AgentSession) -> ExecutionPlan:
        messages = self._build_messages(session)
        logger.info(
            "Planner request model={} payload={}",
            self.config.model,
            self._dump_json_for_log({"messages": messages}),
        )
        response = await self._create_completion(messages)
        content = self._extract_content(response)
        logger.info("Planner response model={} content={}", self.config.model, content)
        return self._parse_plan(content)

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
            "loaded_skills": [skill.name for skill in state.loaded_skills],
            "active_skill": state.active_skill.name if state.active_skill is not None else None,
            "scratchpad_observations": list(state.scratchpad),
        }
        return [
            {
                "role": "system",
                "content": "\n\n".join(
                    part for part in [state.system_prompt, _PLANNER_PROTOCOL_INSTRUCTIONS] if part
                ),
            },
            {
                "role": "user",
                "content": "Planning context:\n" + self._dump_json_for_log(user_context),
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

    def _parse_plan(self, content: str) -> ExecutionPlan:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"OpenAI planner response was not valid JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("OpenAI planner response must be a JSON object.")

        goal = str(payload.get("goal", "")).strip()
        if not goal:
            raise RuntimeError("OpenAI planner response must include a non-empty 'goal'.")

        subgoals = self._parse_subgoals(payload.get("subgoals", []))
        success_criteria = self._parse_string_list(payload.get("success_criteria", []), "success_criteria")
        assumptions = self._parse_string_list(payload.get("assumptions", []), "assumptions")

        return ExecutionPlan(
            goal=goal,
            subgoals=subgoals,
            success_criteria=success_criteria,
            assumptions=assumptions,
            status=PlanStatus.PENDING,
        )

    def _parse_subgoals(self, value: object) -> list[PlanSubgoal]:
        if not isinstance(value, list):
            raise RuntimeError("'subgoals' must be a JSON array.")
        subgoals: list[PlanSubgoal] = []
        for item in value:
            if not isinstance(item, dict):
                raise RuntimeError("'subgoals' entries must be objects.")
            raw_id = str(item.get("id", "")).strip()
            raw_task = str(item.get("task", "")).strip()
            raw_notes = str(item.get("notes", "")).strip()
            if not raw_id:
                raise RuntimeError("Each subgoal must include a non-empty 'id'.")
            if not raw_task:
                raise RuntimeError("Each subgoal must include a non-empty 'task'.")
            subgoals.append(
                PlanSubgoal(
                    id=raw_id,
                    task=raw_task,
                    status=PlanStatus.PENDING,
                    notes=raw_notes,
                )
            )
        return subgoals

    def _parse_string_list(self, value: object, field_name: str) -> list[str]:
        if not isinstance(value, list):
            raise RuntimeError(f"'{field_name}' must be a JSON array.")
        items: list[str] = []
        for item in value:
            normalized = str(item).strip()
            if normalized:
                items.append(normalized)
        return items

    def _dump_json_for_log(self, payload: dict[str, object]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
