"""Run the file summary agent against a local workspace file."""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from agents import FileSummaryAgent
from common.observability import setup_loguru


async def main() -> None:
    setup_loguru(service_name="agent-claw-demo")
    with TemporaryDirectory() as temp_dir:
        workspace_dir = Path(temp_dir)
        target_file = workspace_dir / "note.txt"
        target_file.write_text("example workspace note", encoding="utf-8")

        agent = FileSummaryAgent(target_path="note.txt")
        result = await agent.run("Summarize the workspace note.", workspace_dir=workspace_dir)
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
