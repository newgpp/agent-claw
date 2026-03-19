"""Business agent that summarizes a target workspace file."""

from __future__ import annotations

from pathlib import Path

from agents.base import AgentDescriptor
from agents.runtime_agent import AgentRunConfig, RuntimeAgent
from clawcore.llm.mock import MockLLM
from clawcore.models import ReActStep, ToolCall
from clawcore.runtime import ReActRuntime
from clawcore.runtime.session import AgentSession
from clawcore.skilling.loader import load_skills
from clawcore.skilling.models import SkillDefinition
from clawcore.tooling import ReadSkillTool, ReadTool, ToolExecutor, ToolRegistry


def _extract_observation_text(observation: str) -> str:
    _, _, content = observation.partition(": ")
    return content or observation


class FileSummaryAgent(RuntimeAgent):
    """Summarize a configured file inside the workspace."""

    descriptor = AgentDescriptor(
        name="file-summary-agent",
        description="Reads a configured workspace file and returns a compact summary.",
    )

    def __init__(self, *, target_path: str = "note.txt") -> None:
        self.target_path = target_path
        skills = self._load_bound_skills()
        registry = ToolRegistry()
        registry.register(ReadSkillTool())
        registry.register(ReadTool())

        async def step_fn(session: AgentSession) -> ReActStep:
            if session.state.active_skill is None:
                return ReActStep(
                    thought="I should load the file-summary skill before touching the workspace file.",
                    action=ToolCall(name="read_skill", payload={"skill": "file-summary"}),
                )

            if len(session.state.tool_results) < 2:
                return ReActStep(
                    thought=f"I should read {self.target_path} before answering.",
                    action=ToolCall(name="read", payload={"path": self.target_path}),
                )

            content = _extract_observation_text(session.state.scratchpad[-1]).strip()
            summary = f"Summary of {self.target_path}: {content}"
            return ReActStep(
                thought="I have the file contents and can produce a concise summary.",
                final_answer=summary,
            )

        super().__init__(
            ReActRuntime(
                llm=MockLLM(step_fn),
                tool_executor=ToolExecutor(registry),
            ),
            config=AgentRunConfig(
                base_instructions="Use available skill summaries to decide whether a skill should be loaded.",
                skills=tuple(skills),
                max_steps=3,
            ),
        )

    def _load_bound_skills(self) -> list[SkillDefinition]:
        skills_root = Path(__file__).resolve().parent / "skills"
        return load_skills(skills_root)
