"""Policy checks for runtime-owned tools."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ToolPolicy:
    """Simple allowlist/denylist policy for tool execution."""

    allow: set[str] = field(default_factory=set)
    deny: set[str] = field(default_factory=set)

    def is_allowed(self, tool_name: str) -> bool:
        normalized = tool_name.strip()
        if normalized in self.deny:
            return False
        if self.allow and normalized not in self.allow:
            return False
        return True
