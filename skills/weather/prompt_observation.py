"""Prompt-facing observation compression for weather skill tool results."""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse


def summarize_tool_result(
    *,
    tool_name: str,
    action_payload: dict[str, object],
    result_content: str,
) -> str | None:
    if tool_name != "curl":
        return None

    url = str(action_payload.get("url", "")).strip()
    if not url or "wttr.in" not in url:
        return None

    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    formats = query.get("format", [])
    if "j1" not in formats:
        return None

    try:
        payload = json.loads(result_content)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    return _build_wttr_summary(payload)


def _build_wttr_summary(payload: dict[str, object]) -> str | None:
    weather_entries = payload.get("weather")
    if not isinstance(weather_entries, list) or not weather_entries:
        return None

    location = _first_nested_value(payload.get("nearest_area"), "areaName") or "Unknown location"
    current = _extract_current(payload.get("current_condition"))
    day_lines = [_extract_day_summary(entry) for entry in weather_entries[:3]]
    summarized_days = [line for line in day_lines if line]
    if not summarized_days:
        return None

    lines: list[str] = [f"Weather summary for {location}"]
    if current:
        lines.append(current)
    lines.extend(summarized_days)
    return "\n".join(lines)


def _extract_current(current_condition: object) -> str | None:
    if not isinstance(current_condition, list) or not current_condition:
        return None
    current = current_condition[0]
    if not isinstance(current, dict):
        return None

    condition = _first_value(current.get("weatherDesc")) or "Unknown"
    temp = _as_text(current.get("temp_C"))
    humidity = _as_text(current.get("humidity"))
    wind_speed = _as_text(current.get("windspeedKmph"))
    wind_dir = _as_text(current.get("winddir16Point"))
    parts = [f"Current: {condition}"]
    if temp:
        parts.append(f"{temp}C")
    if humidity:
        parts.append(f"humidity {humidity}%")
    if wind_speed:
        wind_part = f"wind {wind_speed} km/h"
        if wind_dir:
            wind_part += f" {wind_dir}"
        parts.append(wind_part)
    return ", ".join(parts)


def _extract_day_summary(entry: object) -> str | None:
    if not isinstance(entry, dict):
        return None

    date = _as_text(entry.get("date"))
    min_temp = _as_text(entry.get("mintempC"))
    max_temp = _as_text(entry.get("maxtempC"))
    hourly = entry.get("hourly")
    conditions = _collect_conditions(hourly)
    rain_chance = _max_rain_chance(hourly)
    condition_text = " -> ".join(conditions) if conditions else "Unknown"

    parts = [date or "Unknown date", condition_text]
    if min_temp or max_temp:
        parts.append(f"{min_temp or '?'}-{max_temp or '?'}C")
    if rain_chance is not None:
        parts.append(f"rain {rain_chance}%")
    return ": ".join([parts[0], ", ".join(parts[1:])])


def _collect_conditions(hourly: object) -> list[str]:
    if not isinstance(hourly, list):
        return []
    conditions: list[str] = []
    for item in hourly:
        if not isinstance(item, dict):
            continue
        condition = _first_value(item.get("weatherDesc"))
        if not condition:
            continue
        normalized = " ".join(condition.split())
        if normalized and normalized not in conditions:
            conditions.append(normalized)
    if not conditions:
        return []
    if len(conditions) == 1:
        return conditions
    return [conditions[0], conditions[-1]]


def _max_rain_chance(hourly: object) -> int | None:
    if not isinstance(hourly, list):
        return None
    values: list[int] = []
    for item in hourly:
        if not isinstance(item, dict):
            continue
        raw = _as_text(item.get("chanceofrain"))
        if raw is None:
            continue
        try:
            values.append(int(raw))
        except ValueError:
            continue
    return max(values) if values else None


def _first_nested_value(entries: object, key: str) -> str | None:
    if not isinstance(entries, list) or not entries:
        return None
    first = entries[0]
    if not isinstance(first, dict):
        return None
    return _first_value(first.get(key))


def _first_value(entries: object) -> str | None:
    if not isinstance(entries, list) or not entries:
        return None
    first = entries[0]
    if not isinstance(first, dict):
        return None
    return _as_text(first.get("value"))


def _as_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
