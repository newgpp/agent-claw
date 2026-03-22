import asyncio
import json

import pytest

from agents.tools.open_meteo import OpenMeteoTool
from agents.tools.send_email import SendEmailTool
from agents.tools.tavily import TavilyTool
from clawcore.tooling import ToolExecutionContext


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


class FakeAsyncClient:
    calls: list[tuple[str, dict[str, object]]] = []

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        pass

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def post(self, url: str, json: dict[str, object]) -> FakeHTTPResponse:
        type(self).calls.append((url, json))
        return FakeHTTPResponse(
            {
                "answer": "Hong Kong is warm.",
                "results": [
                    {
                        "title": "Weather report",
                        "url": "https://example.com/weather",
                        "content": "Hong Kong will be warm today.",
                    }
                ],
            }
        )

    async def get(self, url: str, params: dict[str, object]) -> FakeHTTPResponse:
        type(self).calls.append((url, params))
        if "geocoding-api.open-meteo.com" in url:
            query = str(params.get("name", ""))
            if query == "北京":
                return FakeHTTPResponse(
                    {
                        "results": [
                            {
                                "name": "北京",
                                "country": "中国",
                                "admin1": "重庆市",
                                "admin2": "重庆市",
                                "latitude": 30.72,
                                "longitude": 108.67,
                                "feature_code": "PPL",
                            }
                        ]
                    }
                )
            if query == "北京市":
                return FakeHTTPResponse(
                    {
                        "results": [
                            {
                                "name": "北京市",
                                "country": "中国",
                                "admin1": "北京",
                                "admin2": "北京市",
                                "latitude": 39.90,
                                "longitude": 116.39,
                                "feature_code": "PPLC",
                                "population": 18960744,
                            }
                        ]
                    }
                )
            if query == "Beijing, China":
                return FakeHTTPResponse({"results": []})
            if query == "Beijing":
                return FakeHTTPResponse(
                    {
                        "results": [
                            {
                                "name": "北京市",
                                "country": "中国",
                                "admin1": "北京",
                                "admin2": "北京市",
                                "latitude": 39.90,
                                "longitude": 116.39,
                                "feature_code": "PPLC",
                                "population": 18960744,
                            }
                        ]
                    }
                )
            if query == "唐山":
                return FakeHTTPResponse(
                    {
                        "results": [
                            {
                                "name": "唐山",
                                "country": "中国",
                                "admin1": "河北",
                                "latitude": 39.64381,
                                "longitude": 118.18319,
                                "feature_code": "PPLA2",
                                "population": 3372102,
                            },
                            {
                                "name": "唐山",
                                "country": "中国",
                                "admin1": "贵州",
                                "latitude": 25.93,
                                "longitude": 104.68,
                                "feature_code": "PPL",
                            }
                        ]
                    }
                )
            return FakeHTTPResponse(
                {
                    "results": [
                        {
                            "name": "Tangshan",
                            "country": "China",
                            "admin1": "Hebei",
                            "latitude": 39.63,
                            "longitude": 118.18,
                        }
                    ]
                }
            )
        return FakeHTTPResponse(
            {
                "current": {
                    "temperature_2m": 14.2,
                    "relative_humidity_2m": 35,
                    "apparent_temperature": 12.8,
                    "weather_code": 1,
                    "wind_speed_10m": 11.3,
                },
                "daily": {
                    "temperature_2m_max": [18.1],
                    "temperature_2m_min": [9.4],
                    "precipitation_probability_max": [5],
                    "weather_code": [1],
                },
            }
        )


class FakeSMTP:
    instances: list["FakeSMTP"] = []

    def __init__(self, host: str, port: int, timeout: int | None = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.logged_in = None
        self.messages: list[tuple[object, list[str] | None]] = []
        type(self).instances.append(self)

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.logged_in = (username, password)

    def send_message(self, message, to_addrs=None) -> None:  # type: ignore[no-untyped-def]
        self.messages.append((message, to_addrs))


def test_tavily_tool_requires_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")

    with pytest.raises(ValueError, match="non-empty 'query'"):
        asyncio.run(TavilyTool().execute({}, ToolExecutionContext()))


def test_tavily_tool_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    with pytest.raises(ValueError, match="TAVILY_API_KEY"):
        asyncio.run(TavilyTool().execute({"query": "weather in hong kong"}, ToolExecutionContext()))


def test_tavily_tool_returns_normalized_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setenv("TAVILY_API_URL", "https://api.tavily.test/search")
    monkeypatch.setattr("agents.tools.tavily.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.calls.clear()

    result = asyncio.run(
        TavilyTool().execute(
            {"query": "weather in hong kong", "max_results": 3, "search_depth": "advanced"},
            ToolExecutionContext(),
        )
    )

    payload = json.loads(result)

    assert payload["query"] == "weather in hong kong"
    assert payload["answer"] == "Hong Kong is warm."
    assert payload["results"][0]["url"] == "https://example.com/weather"
    assert FakeAsyncClient.calls[0][0] == "https://api.tavily.test/search"
    assert FakeAsyncClient.calls[0][1]["max_results"] == 3
    assert FakeAsyncClient.calls[0][1]["search_depth"] == "advanced"


def test_send_email_requires_required_fields() -> None:
    tool = SendEmailTool()

    with pytest.raises(ValueError, match="non-empty 'to'"):
        asyncio.run(tool.execute({"subject": "Hello", "body": "Body"}, ToolExecutionContext()))

    with pytest.raises(ValueError, match="non-empty 'subject'"):
        asyncio.run(tool.execute({"to": "user@example.com", "body": "Body"}, ToolExecutionContext()))

    with pytest.raises(ValueError, match="non-empty 'body'"):
        asyncio.run(tool.execute({"to": "user@example.com", "subject": "Hello"}, ToolExecutionContext()))


def test_open_meteo_requires_location() -> None:
    with pytest.raises(ValueError, match="non-empty 'location'"):
        asyncio.run(OpenMeteoTool().execute({}, ToolExecutionContext()))


def test_open_meteo_returns_normalized_weather(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agents.tools.open_meteo.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.calls.clear()

    result = asyncio.run(
        OpenMeteoTool().execute({"location": "Tangshan", "days": 1}, ToolExecutionContext())
    )

    payload = json.loads(result)

    assert payload["location"]["name"] == "Tangshan"
    assert payload["location"]["country"] == "China"
    assert payload["location"]["admin1"] == "Hebei"
    assert payload["current"]["temperature_2m"] == 14.2
    assert payload["daily"]["temperature_2m_max"] == [18.1]


def test_open_meteo_falls_back_from_short_chinese_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agents.tools.open_meteo.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.calls.clear()

    result = asyncio.run(
        OpenMeteoTool().execute({"location": "北京", "days": 1}, ToolExecutionContext())
    )

    payload = json.loads(result)

    assert payload["location"]["name"] == "北京市"
    assert payload["location"]["admin1"] == "北京"
    assert any(call[1].get("name") == "北京市" for call in FakeAsyncClient.calls if "geocoding-api.open-meteo.com" in call[0])


def test_open_meteo_falls_back_from_comma_separated_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agents.tools.open_meteo.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.calls.clear()

    result = asyncio.run(
        OpenMeteoTool().execute({"location": "Beijing, China", "days": 1}, ToolExecutionContext())
    )

    payload = json.loads(result)

    assert payload["location"]["name"] == "北京市"
    assert any(call[1].get("name") == "Beijing" for call in FakeAsyncClient.calls if "geocoding-api.open-meteo.com" in call[0])


def test_open_meteo_falls_back_from_specific_chinese_location(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agents.tools.open_meteo.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.calls.clear()

    result = asyncio.run(
        OpenMeteoTool().execute({"location": "唐山市, 河北, 中国", "days": 1}, ToolExecutionContext())
    )

    payload = json.loads(result)

    assert payload["location"]["name"] == "唐山"
    assert payload["location"]["admin1"] == "河北"
    queried_names = [call[1].get("name") for call in FakeAsyncClient.calls if "geocoding-api.open-meteo.com" in call[0]]
    assert "唐山市, 河北, 中国" in queried_names
    assert "唐山市" in queried_names
    assert "唐山" in queried_names



def test_send_email_requires_smtp_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)

    with pytest.raises(ValueError, match="SMTP_HOST"):
        asyncio.run(
            SendEmailTool().execute(
                {"to": "user@example.com", "subject": "Hello", "body": "Body"},
                ToolExecutionContext(),
            )
        )


def test_send_email_sends_message_via_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "agent@example.com")
    monkeypatch.setenv("SMTP_USE_TLS", "true")
    monkeypatch.setattr("agents.tools.send_email.smtplib.SMTP", FakeSMTP)
    FakeSMTP.instances.clear()

    result = asyncio.run(
        SendEmailTool().execute(
            {
                "to": ["to@example.com"],
                "cc": ["cc@example.com"],
                "bcc": ["bcc@example.com"],
                "subject": "Weather update",
                "body": "Bring an umbrella.",
            },
            ToolExecutionContext(),
        )
    )

    assert "Weather update" in result
    smtp = FakeSMTP.instances[0]
    assert smtp.host == "smtp.example.com"
    assert smtp.port == 587
    assert smtp.started_tls is True
    assert smtp.logged_in == ("user@example.com", "secret")
    message, recipients = smtp.messages[0]
    assert message["From"] == "agent@example.com"
    assert message["To"] == "to@example.com"
    assert message["Cc"] == "cc@example.com"
    assert recipients == ["to@example.com", "cc@example.com", "bcc@example.com"]
