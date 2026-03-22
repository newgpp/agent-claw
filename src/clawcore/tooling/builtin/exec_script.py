"""Built-in script execution tool."""

from __future__ import annotations

import asyncio
from pathlib import Path

from clawcore.tooling.base import BaseTool, ToolExecutionContext


class ExecScriptTool(BaseTool):
    """Execute a declared script relative to the active skill directory."""

    name = "exec_script"
    description = (
        "Execute a declared script path from the active skill only. "
        "Payload: {script:string, args?:list}. "
        "The 'script' value must be a declared relative file path like scripts/foo.py, not a shell command."
    )
    risk_level = "restricted"

    async def execute(self, payload: dict[str, object], context: ToolExecutionContext) -> str:
        active_skill = context.active_skill
        if active_skill is None:
            raise ValueError("exec_script requires an active skill.")

        raw_script = str(payload.get("script", "")).strip()
        if not raw_script:
            raise ValueError("exec_script requires a non-empty 'script'.")
        if raw_script not in active_skill.scripts:
            raise PermissionError(
                f"Script '{raw_script}' is not declared by active skill '{active_skill.name}'."
            )

        script_path = (active_skill.directory / raw_script).resolve()
        if not script_path.exists() or not script_path.is_file():
            raise FileNotFoundError(f"Script '{raw_script}' does not exist.")

        command = ["python3", str(script_path)]
        raw_args = payload.get("args", [])
        if isinstance(raw_args, list):
            command.extend(str(item) for item in raw_args)

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=context.workspace_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            stderr_text = stderr.decode().strip() or f"exit code {process.returncode}"
            raise RuntimeError(stderr_text)
        return stdout.decode().strip()
