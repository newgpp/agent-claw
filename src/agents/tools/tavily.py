"""Agent-owned web search tool backed by Tavily."""

from __future__ import annotations

import json
import os

import httpx

from clawcore.tooling import BaseTool, ToolExecutionContext


class TavilyTool(BaseTool):
    """Search the web via Tavily and return normalized JSON results."""

    name = "tavily"
    max_content_chars = 800
    max_answer_chars = 800
    description = (
        "Search the web using Tavily. "
        "Payload: {query:string, max_results?:int, search_depth?:string, topic?:string}."
    )

    async def execute(self, payload: dict[str, object], context: ToolExecutionContext) -> str:
        query = str(payload.get("query", "")).strip()
        if not query:
            raise ValueError("tavily requires a non-empty 'query'.")

        api_key = os.environ.get("TAVILY_API_KEY", "").strip()
        if not api_key:
            raise ValueError("TAVILY_API_KEY is required for the tavily tool.")

        max_results = payload.get("max_results", 5)
        if isinstance(max_results, bool) or not isinstance(max_results, int) or max_results <= 0:
            raise ValueError("tavily 'max_results' must be a positive integer.")

        search_depth = str(payload.get("search_depth", "basic")).strip().lower() or "basic"
        if search_depth not in {"basic", "advanced"}:
            raise ValueError("tavily 'search_depth' must be 'basic' or 'advanced'.")

        topic = str(payload.get("topic", "general")).strip().lower() or "general"
        if topic not in {"general", "news"}:
            topic = "general"

        base_url = os.environ.get("TAVILY_API_URL", "https://api.tavily.com/search").strip()
        request_payload = {
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "topic": topic,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(base_url, json=request_payload)
            response.raise_for_status()
            data = response.json()

        normalized = {
            "query": query,
            "answer": self._truncate_text(str(data.get("answer", "")).strip(), limit=self.max_answer_chars),
            "results": [
                {
                    "title": str(item.get("title", "")).strip(),
                    "url": str(item.get("url", "")).strip(),
                    "content": self._truncate_text(
                        str(item.get("content", "")).strip(),
                        limit=self.max_content_chars,
                    ),
                }
                for item in data.get("results", [])
                if isinstance(item, dict)
            ],
        }
        return json.dumps(normalized, ensure_ascii=False, sort_keys=True)

    def _truncate_text(self, value: str, *, limit: int) -> str:
        if len(value) <= limit:
            return value
        return value[: limit - 3] + "..."
