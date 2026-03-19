"""Runtime hook helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from common.events import RuntimeEvent

RuntimeHook = Callable[[RuntimeEvent], Awaitable[None] | None]


async def emit_hook(event: RuntimeEvent, hook: RuntimeHook | None) -> None:
    """Emit a runtime event through an optional hook."""
    if hook is None:
        return
    result = hook(event)
    if result is not None:
        await result
