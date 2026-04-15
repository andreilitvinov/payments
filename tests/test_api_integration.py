from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.models import Base
from app.db.session import get_db_session
from app.main import app, outbox_relay
from app.messaging.broker import broker
from app.services.metrics import metrics_store


@pytest.fixture
async def api_client() -> AsyncGenerator[AsyncClient, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with session_factory() as session:
            yield session

    async def _noop_async():
        return None

    def _noop():
        return None

    app.dependency_overrides[get_db_session] = _override_get_db
    broker.start = _noop_async  # type: ignore[method-assign]
    broker.close = _noop_async  # type: ignore[method-assign]
    outbox_relay.start = _noop  # type: ignore[method-assign]
    outbox_relay.stop = _noop_async  # type: ignore[method-assign]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_and_get_payment(api_client: AsyncClient):
    metrics_store.payments_created_total = 0
    metrics_store.payments_fetched_total = 0

    payload = {
        "amount": "99.99",
        "currency": "USD",
        "description": "Integration payment",
        "metadata": {"order_id": "A-1"},
        "webhook_url": "https://example.com/webhook",
    }
    headers = {"X-API-Key": settings.api_key, "Idempotency-Key": "idem-int-1"}

    create_res = await api_client.post("/api/v1/payments", json=payload, headers=headers)
    assert create_res.status_code == 202
    body = create_res.json()
    assert body["status"] == "pending"
    payment_id = body["payment_id"]

    get_res = await api_client.get(
        f"/api/v1/payments/{payment_id}",
        headers={"X-API-Key": settings.api_key},
    )
    assert get_res.status_code == 200
    fetched = get_res.json()
    assert fetched["id"] == payment_id
    assert fetched["currency"] == "USD"
    assert fetched["idempotency_key"] == "idem-int-1"
    assert metrics_store.payments_created_total == 1
    assert metrics_store.payments_fetched_total == 1


@pytest.mark.asyncio
async def test_idempotent_create_returns_same_payment(api_client: AsyncClient):
    payload = {
        "amount": "10.00",
        "currency": "EUR",
        "description": "Idempotency check",
        "metadata": {},
        "webhook_url": "https://example.com/webhook",
    }
    headers = {"X-API-Key": settings.api_key, "Idempotency-Key": "same-key"}

    first = await api_client.post("/api/v1/payments", json=payload, headers=headers)
    second = await api_client.post("/api/v1/payments", json=payload, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["payment_id"] == second.json()["payment_id"]


@pytest.mark.asyncio
async def test_rejects_invalid_api_key(api_client: AsyncClient):
    payload = {
        "amount": "10.00",
        "currency": "RUB",
        "description": "Invalid key",
        "metadata": {},
        "webhook_url": "https://example.com/webhook",
    }
    headers = {"X-API-Key": "bad-key", "Idempotency-Key": "idem-invalid-key"}

    response = await api_client.post("/api/v1/payments", json=payload, headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_metrics_endpoint(api_client: AsyncClient):
    response = await api_client.get("/metrics")
    assert response.status_code == 200
    assert "payments_created_total" in response.text


@pytest.mark.asyncio
async def test_rejects_too_long_idempotency_key(api_client: AsyncClient):
    payload = {
        "amount": "10.00",
        "currency": "USD",
        "description": "Invalid idempotency key",
        "metadata": {},
        "webhook_url": "https://example.com/webhook",
    }
    headers = {"X-API-Key": settings.api_key, "Idempotency-Key": "x" * 129}

    response = await api_client.post("/api/v1/payments", json=payload, headers=headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_rejects_private_webhook_url(api_client: AsyncClient):
    payload = {
        "amount": "10.00",
        "currency": "USD",
        "description": "Invalid webhook",
        "metadata": {},
        "webhook_url": "https://127.0.0.1/webhook",
    }
    headers = {"X-API-Key": settings.api_key, "Idempotency-Key": "idem-private-hook-1"}

    response = await api_client.post("/api/v1/payments", json=payload, headers=headers)
    assert response.status_code == 422
