"""Agent-owned web search tool backed by Tavily."""

from __future__ import annotations

import json
import os
import re

import httpx

from clawcore.tooling import BaseTool, ToolExecutionContext


class TavilyTool(BaseTool):
    """Search the web via Tavily and return normalized JSON results."""

    name = "tavily"
    max_content_chars = 600
    max_answer_chars = 400
    max_total_content_chars = 2400
    description = (
        "Search the web using Tavily. "
        "Payload: {query:string, max_results?:int, search_depth?:string, topic?:string, "
        "time_range?:string, start_date?:string, end_date?:string, "
        "include_domains?:string[], exclude_domains?:string[]}."
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
        if topic not in {"general", "news", "finance"}:
            topic = "general"

        time_range = self._normalize_time_range(payload.get("time_range"))
        if time_range and time_range not in {"day", "week", "month", "year", "d", "w", "m", "y"}:
            raise ValueError(
                "tavily 'time_range' must be one of 'day', 'week', 'month', 'year', 'd', 'w', 'm', 'y'."
            )

        start_date = self._optional_date(payload.get("start_date"), field_name="start_date")
        end_date = self._optional_date(payload.get("end_date"), field_name="end_date")
        include_domains = self._normalize_domains(payload.get("include_domains"), field_name="include_domains")
        exclude_domains = self._normalize_domains(payload.get("exclude_domains"), field_name="exclude_domains")

        base_url = os.environ.get("TAVILY_API_URL", "https://api.tavily.com/search").strip()
        request_payload = {
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "topic": topic,
        }
        if time_range:
            request_payload["time_range"] = time_range
        if start_date is not None:
            request_payload["start_date"] = start_date
        if end_date is not None:
            request_payload["end_date"] = end_date
        if include_domains:
            request_payload["include_domains"] = include_domains
        if exclude_domains:
            request_payload["exclude_domains"] = exclude_domains

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(base_url, json=request_payload)
            response.raise_for_status()
            data = response.json()

        results = [
            item
            for item in data.get("results", [])
            if isinstance(item, dict)
        ]
        content_limit = self._content_limit_for_results(len(results))

        normalized = {
            "query": query,
            "answer": self._truncate_text(str(data.get("answer", "")).strip(), limit=self.max_answer_chars),
            "results": [
                {
                    "title": str(item.get("title", "")).strip(),
                    "url": str(item.get("url", "")).strip(),
                    "content": self._truncate_text(
                        str(item.get("content", "")).strip(),
                        limit=content_limit,
                    ),
                }
                for item in results
            ],
        }
        return json.dumps(normalized, ensure_ascii=False, sort_keys=True)

    def _truncate_text(self, value: str, *, limit: int) -> str:
        if len(value) <= limit:
            return value
        return value[: limit - 3] + "..."

    def _content_limit_for_results(self, result_count: int) -> int:
        if result_count <= 0:
            return self.max_content_chars
        per_result_budget = max(160, self.max_total_content_chars // result_count)
        return min(self.max_content_chars, per_result_budget)

    def _optional_date(self, value: object, *, field_name: str) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        if len(normalized) != 10 or normalized[4] != "-" or normalized[7] != "-":
            raise ValueError(f"tavily '{field_name}' must use YYYY-MM-DD format.")
        year, month, day = normalized.split("-")
        if not (year.isdigit() and month.isdigit() and day.isdigit()):
            raise ValueError(f"tavily '{field_name}' must use YYYY-MM-DD format.")
        return normalized

    def _normalize_domains(self, value: object, *, field_name: str) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            domains = [value]
        elif isinstance(value, list):
            domains = value
        else:
            raise ValueError(f"tavily '{field_name}' must be a string list.")

        normalized: list[str] = []
        for item in domains:
            domain = str(item).strip().lower()
            if not domain:
                continue
            domain = domain.removeprefix("https://").removeprefix("http://").strip("/")
            if "/" in domain:
                domain = domain.split("/", 1)[0]
            # Tavily expects actual domains here. Drop loose keywords such as
            # "video" or "forum" rather than forwarding a bad request.
            if "." not in domain:
                continue
            if domain:
                normalized.append(domain)
        return normalized

    def _normalize_time_range(self, value: object) -> str:
        if value is None:
            return ""
        normalized = str(value).strip().lower()
        if not normalized:
            return ""

        aliases = {
            "1d": "day",
            "1w": "week",
            "1m": "month",
            "1y": "year",
            "day": "day",
            "week": "week",
            "month": "month",
            "year": "year",
            "d": "d",
            "w": "w",
            "m": "m",
            "y": "y",
        }
        if normalized in aliases:
            return aliases[normalized]

        match = re.fullmatch(r"(\d+)([dwmy])", normalized)
        if match is not None:
            quantity = int(match.group(1))
            unit = match.group(2)
            if quantity <= 1:
                return {"d": "day", "w": "week", "m": "month", "y": "year"}[unit]
            return unit

        return normalized
