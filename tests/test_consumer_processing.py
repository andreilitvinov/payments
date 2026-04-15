from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Outbox, OutboxStatus, Payment, PaymentStatus
from app.messaging import consumer
from app.services.metrics import metrics_store


@pytest.mark.asyncio
async def test_payment_status_persists_when_webhook_fails(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(consumer, "SessionLocal", session_factory)
    monkeypatch.setattr(consumer.random, "uniform", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(consumer.random, "random", lambda: 0.1)

    async def _always_fail_webhook(*_args, **_kwargs):
        raise RuntimeError("webhook failed")

    monkeypatch.setattr(consumer, "send_webhook_with_retry", _always_fail_webhook)

    async with session_factory() as session:
        payment = Payment(
            amount=10,
            currency="USD",
            description="consumer-test",
            metadata_json={"case": "webhook-fail"},
            status=PaymentStatus.pending,
            idempotency_key="consumer-webhook-fail-1",
            webhook_url="https://example.com/webhook",
            created_at=datetime.now(timezone.utc),
        )
        session.add(payment)
        await session.commit()
        payment_id = payment.id

    await consumer.process_payment({"payment_id": str(payment_id), "attempt": 1})

    async with session_factory() as session:
        refreshed = await session.scalar(select(Payment).where(Payment.id == payment_id))
        outbox_messages = (
            await session.scalars(select(Outbox).where(Outbox.topic == "payments.new"))
        ).all()

    assert refreshed is not None
    assert refreshed.status == PaymentStatus.succeeded
    assert refreshed.processed_at is not None
    assert len(outbox_messages) == 1
    assert outbox_messages[0].status == OutboxStatus.pending
    assert outbox_messages[0].payload["attempt"] == 2

    await engine.dispose()


@pytest.mark.asyncio
async def test_invalid_message_goes_to_dlq(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(consumer, "SessionLocal", session_factory)

    await consumer.process_payment({"attempt": 1})

    async with session_factory() as session:
        dlq_messages = (
            await session.scalars(select(Outbox).where(Outbox.topic == "payments.dlq"))
        ).all()

    assert len(dlq_messages) == 1
    assert dlq_messages[0].status == OutboxStatus.pending
    assert dlq_messages[0].payload["reason"] == consumer.DLQ_REASON_INVALID_PAYLOAD

    await engine.dispose()


@pytest.mark.asyncio
async def test_webhook_failure_moves_to_dlq_on_third_attempt(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(consumer, "SessionLocal", session_factory)
    monkeypatch.setattr(consumer.random, "uniform", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(consumer.random, "random", lambda: 0.1)

    async def _always_fail_webhook(*_args, **_kwargs):
        raise RuntimeError("webhook failed")

    monkeypatch.setattr(consumer, "send_webhook_with_retry", _always_fail_webhook)

    async with session_factory() as session:
        payment = Payment(
            amount=10,
            currency="USD",
            description="dlq-third-attempt",
            metadata_json={"case": "dlq"},
            status=PaymentStatus.pending,
            idempotency_key="consumer-webhook-dlq-1",
            webhook_url="https://example.com/webhook",
            created_at=datetime.now(timezone.utc),
        )
        session.add(payment)
        await session.commit()
        payment_id = payment.id

    await consumer.process_payment({"payment_id": str(payment_id), "attempt": 1})
    await consumer.process_payment({"payment_id": str(payment_id), "attempt": 2})
    await consumer.process_payment({"payment_id": str(payment_id), "attempt": 3})

    async with session_factory() as session:
        retries = (await session.scalars(select(Outbox).where(Outbox.topic == "payments.new"))).all()
        dlq_messages = (await session.scalars(select(Outbox).where(Outbox.topic == "payments.dlq"))).all()

    assert len(retries) == 2
    assert len(dlq_messages) == 1
    assert dlq_messages[0].payload["attempt"] == 3
    assert dlq_messages[0].payload["reason"] == consumer.DLQ_REASON_WEBHOOK_DELIVERY_FAILED

    await engine.dispose()


@pytest.mark.asyncio
async def test_process_dead_letter_increments_metric():
    metrics_store.dlq_consumed_total = 0

    await consumer.process_dead_letter(
        {"payment_id": "00000000-0000-0000-0000-000000000000", "reason": "test"}
    )

    assert metrics_store.dlq_consumed_total == 1
