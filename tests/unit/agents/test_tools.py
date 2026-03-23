import asyncio
import json

import pytest

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


def test_tavily_tool_truncates_long_result_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setenv("TAVILY_API_URL", "https://api.tavily.test/search")

    class LongContentClient(FakeAsyncClient):
        async def post(self, url: str, json: dict[str, object]) -> FakeHTTPResponse:
            type(self).calls.append((url, json))
            return FakeHTTPResponse(
                {
                    "answer": "A" * 1200,
                    "results": [
                        {
                            "title": "Long result",
                            "url": "https://example.com/long",
                            "content": "B" * 2000,
                        }
                    ],
                }
            )

    monkeypatch.setattr("agents.tools.tavily.httpx.AsyncClient", LongContentClient)

    result = asyncio.run(
        TavilyTool().execute(
            {"query": "weather in hong kong"},
            ToolExecutionContext(),
        )
    )

    payload = json.loads(result)

    assert len(payload["answer"]) == TavilyTool.max_answer_chars
    assert payload["answer"].endswith("...")
    assert len(payload["results"][0]["content"]) == TavilyTool.max_content_chars
    assert payload["results"][0]["content"].endswith("...")


def test_tavily_tool_falls_back_to_general_topic_for_invalid_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setenv("TAVILY_API_URL", "https://api.tavily.test/search")
    monkeypatch.setattr("agents.tools.tavily.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.calls.clear()

    asyncio.run(
        TavilyTool().execute(
            {"query": "beijing travel weather", "topic": "travel"},
            ToolExecutionContext(),
        )
    )

    assert FakeAsyncClient.calls[0][1]["topic"] == "general"


def test_tavily_tool_supports_finance_topic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setenv("TAVILY_API_URL", "https://api.tavily.test/search")
    monkeypatch.setattr("agents.tools.tavily.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.calls.clear()

    asyncio.run(
        TavilyTool().execute(
            {"query": "tesla latest news", "topic": "finance"},
            ToolExecutionContext(),
        )
    )

    assert FakeAsyncClient.calls[0][1]["topic"] == "finance"


def test_tavily_tool_distributes_content_budget_across_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setenv("TAVILY_API_URL", "https://api.tavily.test/search")

    class MultiResultClient(FakeAsyncClient):
        async def post(self, url: str, json: dict[str, object]) -> FakeHTTPResponse:
            type(self).calls.append((url, json))
            return FakeHTTPResponse(
                {
                    "answer": "Market update",
                    "results": [
                        {
                            "title": f"Result {index}",
                            "url": f"https://example.com/{index}",
                            "content": "X" * 1200,
                        }
                        for index in range(6)
                    ],
                }
            )

    monkeypatch.setattr("agents.tools.tavily.httpx.AsyncClient", MultiResultClient)

    result = asyncio.run(
        TavilyTool().execute(
            {"query": "ai market news", "max_results": 6},
            ToolExecutionContext(),
        )
    )

    payload = json.loads(result)

    # 2400 total budget across 6 results -> 400 chars each.
    assert len(payload["results"]) == 6
    assert len(payload["results"][0]["content"]) == 400
    assert payload["results"][0]["content"].endswith("...")


def test_send_email_requires_required_fields() -> None:
    tool = SendEmailTool()

    with pytest.raises(ValueError, match="non-empty 'to'"):
        asyncio.run(tool.execute({"subject": "Hello", "body": "Body"}, ToolExecutionContext()))

    with pytest.raises(ValueError, match="non-empty 'subject'"):
        asyncio.run(tool.execute({"to": "user@example.com", "body": "Body"}, ToolExecutionContext()))

    with pytest.raises(ValueError, match="non-empty 'body'"):
        asyncio.run(tool.execute({"to": "user@example.com", "subject": "Hello"}, ToolExecutionContext()))



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
