"""Agent-owned weather tool backed by Open-Meteo."""

from __future__ import annotations

import json

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
            geo_response = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": location, "count": 1, "language": "zh", "format": "json"},
            )
            geo_response.raise_for_status()
            geo_payload = geo_response.json()
            results = geo_payload.get("results", [])
            if not isinstance(results, list) or not results:
                raise RuntimeError(f"open_meteo could not resolve location '{location}'.")

            top = results[0]
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
