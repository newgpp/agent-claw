"""Debug the send_email tool directly without going through the agent runtime."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from agents.tools.send_email import SendEmailTool
from apps.env import load_dotenv
from clawcore.tooling import ToolExecutionContext
from common.observability import setup_loguru


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send a debug email through the send_email tool.")
    parser.add_argument("--to", required=True, help="Recipient email address.")
    parser.add_argument("--subject", required=True, help="Email subject.")
    parser.add_argument(
        "--body",
        help="Email body text. Use either --body or --body-file.",
    )
    parser.add_argument(
        "--body-file",
        help="Path to a UTF-8 text file containing the email body.",
    )
    return parser


def _resolve_body(*, body: str | None, body_file: str | None) -> str:
    if body and body_file:
        raise ValueError("Use either --body or --body-file, not both.")
    if body_file:
        return Path(body_file).read_text(encoding="utf-8")
    if body:
        return body
    raise ValueError("One of --body or --body-file is required.")


async def main() -> None:
    args = _build_parser().parse_args()
    load_dotenv()
    setup_loguru(service_name="agent-claw-send-email-debug")

    body = _resolve_body(body=args.body, body_file=args.body_file)
    result = await SendEmailTool().execute(
        {
            "to": args.to,
            "subject": args.subject,
            "body": body,
        },
        ToolExecutionContext(),
    )
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
