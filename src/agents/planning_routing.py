"""Planning routing policies for runtime-backed agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import re


class PlanningRoutingPolicy(ABC):
    """Strategy interface for deciding whether a request should use planned execution."""

    @abstractmethod
    def should_plan(self, user_input: str) -> bool:
        """Return True when the request should use planned execution."""


@dataclass(frozen=True, slots=True)
class StructuralPlanningRoutingPolicy(PlanningRoutingPolicy):
    """Default auto-routing policy based on structural multi-step signals."""

    list_item_pattern: re.Pattern[str] = re.compile(r"(?m)^\s*(?:[-*]|\d+[.)])\s+\S+")
    ordered_step_pattern: re.Pattern[str] = re.compile(
        r"(?i)\b(?:first|second|third|next|then|finally|after that)\b"
    )
    ordered_step_cn_pattern: re.Pattern[str] = re.compile(r"(先|然后|接着|再|之后|最后)")
    clause_separator_pattern: re.Pattern[str] = re.compile(r"[，,;；]\s*")
    sentence_separator_pattern: re.Pattern[str] = re.compile(r"[。！？.!?]\s+")
    coordinating_pattern: re.Pattern[str] = re.compile(
        r"(?i)\b(?:and then|then|after that|followed by)\b|并且|并|然后|再|之后"
    )

    def should_plan(self, user_input: str) -> bool:
        text = user_input.strip()
        if not text:
            return False

        if len(self.list_item_pattern.findall(text)) >= 2:
            return True

        if self.ordered_step_pattern.search(text) or self.ordered_step_cn_pattern.search(text):
            return True

        clause_count = len([part for part in self.clause_separator_pattern.split(text) if part.strip()])
        if clause_count >= 3:
            return True

        sentence_count = len([part for part in self.sentence_separator_pattern.split(text) if part.strip()])
        if sentence_count >= 2:
            return True

        return self.coordinating_pattern.search(text) is not None
