"""Agent-owned weather tool backed by Open-Meteo."""

from __future__ import annotations

import json
import re

import httpx

from clawcore.tooling import BaseTool, ToolExecutionContext


class OpenMeteoTool(BaseTool):
    """Fetch current weather from Open-Meteo with built-in geocoding."""

    name = "open_meteo"
    description = (
        "Fetch current weather using Open-Meteo. "
        "Payload: {location:string, days?:int}."
    )

    async def execute(self, payload: dict[str, object], context: ToolExecutionContext) -> str:
        location = str(payload.get("location", "")).strip()
        if not location:
            raise ValueError("open_meteo requires a non-empty 'location'.")

        days = payload.get("days", 1)
        if isinstance(days, bool) or not isinstance(days, int) or days <= 0:
            raise ValueError("open_meteo 'days' must be a positive integer.")

        async with httpx.AsyncClient(timeout=20.0) as client:
            top = await self._resolve_location(client, location)
            latitude = top.get("latitude")
            longitude = top.get("longitude")
            if latitude is None or longitude is None:
                raise RuntimeError(f"open_meteo location '{location}' is missing coordinates.")

            weather_response = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                    "timezone": "auto",
                    "forecast_days": min(days, 3),
                },
            )
            weather_response.raise_for_status()
            weather_payload = weather_response.json()

        normalized = {
            "location": {
                "name": str(top.get("name", location)).strip(),
                "country": str(top.get("country", "")).strip(),
                "admin1": str(top.get("admin1", "")).strip(),
                "latitude": latitude,
                "longitude": longitude,
            },
            "current": weather_payload.get("current", {}),
            "daily": weather_payload.get("daily", {}),
        }
        return json.dumps(normalized, ensure_ascii=False, sort_keys=True)

    async def _resolve_location(self, client: httpx.AsyncClient, location: str) -> dict[str, object]:
        ranked_candidates: list[tuple[tuple[int, int, int, str], dict[str, object]]] = []
        for candidate in self._candidate_queries(location):
            geo_response = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": candidate, "count": 10, "language": "zh", "format": "json"},
            )
            geo_response.raise_for_status()
            geo_payload = geo_response.json()
            results = geo_payload.get("results", [])
            if isinstance(results, list) and results:
                for item in results:
                    if isinstance(item, dict):
                        ranked_candidates.append((self._result_rank(item, candidate), item))

        if ranked_candidates:
            ranked_candidates.sort(key=lambda pair: pair[0])
            return ranked_candidates[0][1]

        raise RuntimeError(f"open_meteo could not resolve location '{location}'.")

    def _candidate_queries(self, location: str) -> list[str]:
        candidates: list[str] = []

        def add(value: str) -> None:
            normalized = value.strip()
            if normalized and normalized not in candidates:
                candidates.append(normalized)

        add(location)
        add(location.split(",", 1)[0])
        add(location.split("，", 1)[0])

        primary = candidates[0] if candidates else location
        if self._contains_cjk(primary) and not primary.endswith(("市", "区", "县")):
            add(f"{primary}市")

        return candidates

    def _result_rank(self, result: dict[str, object], query: str) -> tuple[int, int, int, str]:
        feature_code = str(result.get("feature_code", "")).strip().upper()
        feature_priority = {
            "PPLC": 0,
            "PPLA": 1,
            "PPLA2": 2,
            "PPLA3": 3,
            "ADM1": 4,
            "PPL": 5,
        }.get(feature_code, 9)

        population = int(result.get("population", 0) or 0)
        exact_match_score = 1
        result_name = str(result.get("name", "")).strip()
        admin1 = str(result.get("admin1", "")).strip()
        stripped_query = query.strip()
        if result_name == stripped_query or admin1 == stripped_query:
            exact_match_score = 0
        if stripped_query.endswith("市"):
            plain_query = stripped_query[:-1]
            if result_name == plain_query or admin1 == plain_query:
                exact_match_score = 0

        return (exact_match_score, feature_priority, -population, result_name)

    def _contains_cjk(self, value: str) -> bool:
        return bool(re.search(r"[\u4e00-\u9fff]", value))
