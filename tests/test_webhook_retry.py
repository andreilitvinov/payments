import httpx
import pytest

from app.services.webhook import send_webhook_with_retry


class DummyClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, json):
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class DummyResponse:
    def __init__(self, ok: bool, status_code: int = 500):
        self.ok = ok
        self.status_code = status_code

    def raise_for_status(self):
        if not self.ok:
            raise httpx.HTTPStatusError(
                "error",
                request=httpx.Request("POST", "https://example.com"),
                response=httpx.Response(self.status_code),
            )


@pytest.mark.asyncio
async def test_webhook_retry_success(monkeypatch):
    responses = [httpx.ConnectError("connection failed"), DummyResponse(ok=True)]
    dummy_client = DummyClient(responses)
    monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: dummy_client)

    await send_webhook_with_retry(
        "https://example.com/hook",
        {"status": "succeeded"},
        base_delay_seconds=0,
    )


@pytest.mark.asyncio
async def test_webhook_retry_exhausted(monkeypatch):
    responses = [
        httpx.ConnectError("connection failed"),
        httpx.ConnectError("connection failed"),
        httpx.ConnectError("connection failed"),
    ]
    dummy_client = DummyClient(responses)
    monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: dummy_client)

    with pytest.raises(httpx.ConnectError):
        await send_webhook_with_retry(
            "https://example.com/hook",
            {"status": "failed"},
            base_delay_seconds=0,
        )


@pytest.mark.asyncio
async def test_webhook_does_not_retry_on_4xx(monkeypatch):
    responses = [DummyResponse(ok=False, status_code=400)]
    dummy_client = DummyClient(responses)
    monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: dummy_client)

    with pytest.raises(httpx.HTTPStatusError):
        await send_webhook_with_retry(
            "https://example.com/hook",
            {"status": "failed"},
            base_delay_seconds=0,
        )

    assert dummy_client.calls == 1
