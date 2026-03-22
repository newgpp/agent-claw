"""Restricted curl-based HTTP request tool for agent workflows."""

from __future__ import annotations

import asyncio

from clawcore.tooling import BaseTool, ToolExecutionContext


class CurlTool(BaseTool):
    """Execute a limited HTTP request via curl."""

    name = "curl"
    description = (
        "Execute an HTTP request with curl. "
        "Payload: {url:string, method?:string, headers?:object, data?:string, max_time?:int}."
    )

    async def execute(self, payload: dict[str, object], context: ToolExecutionContext) -> str:
        raw_url = str(payload.get("url", "")).strip()
        if not raw_url:
            raise ValueError("curl requires a non-empty 'url'.")
        if raw_url.startswith(("http://", "https://")):
            normalized_url = raw_url
        else:
            normalized_url = f"https://{raw_url}"

        method = str(payload.get("method", "GET")).strip().upper() or "GET"
        command = ["curl", "-s", "-L", "-X", method]

        raw_headers = payload.get("headers", {})
        if isinstance(raw_headers, dict):
            for key, value in raw_headers.items():
                header_name = str(key).strip()
                header_value = str(value).strip()
                if header_name:
                    command.extend(["-H", f"{header_name}: {header_value}"])

        if "data" in payload:
            command.extend(["--data", str(payload["data"])])

        max_time = payload.get("max_time", 10)
        if isinstance(max_time, bool) or not isinstance(max_time, int) or max_time <= 0:
            raise ValueError("curl 'max_time' must be a positive integer.")
        command.extend(["--max-time", str(max_time)])
        command.append(normalized_url)

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            stderr_text = stderr.decode().strip() or f"exit code {process.returncode}"
            raise RuntimeError(stderr_text)

        output = stdout.decode().strip()
        if not output:
            raise RuntimeError("curl returned an empty response.")
        return output
