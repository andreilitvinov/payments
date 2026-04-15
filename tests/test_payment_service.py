import asyncio
from pathlib import Path
import tempfile

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Payment
from app.schemas.payment import CreatePaymentRequest
from app.services.payment_service import PaymentService


@pytest.mark.asyncio
async def test_create_payment_is_idempotent(db_session):
    service = PaymentService(db_session)
    payload = CreatePaymentRequest(
        amount="10.50",
        currency="USD",
        description="test",
        metadata={"order_id": "123"},
        webhook_url="https://example.com/webhook",
    )

    first = await service.create_payment(payload, idempotency_key="idem-key-1")
    second = await service.create_payment(payload, idempotency_key="idem-key-1")

    assert first.id == second.id
    assert first.status.value == "pending"


@pytest.mark.asyncio
async def test_create_payment_is_idempotent_under_concurrency():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    async with engine.begin() as conn:
        from app.db.models import Base

        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    payload = CreatePaymentRequest(
        amount="10.50",
        currency="USD",
        description="concurrent test",
        metadata={"order_id": "123"},
        webhook_url="https://example.com/webhook",
    )

    async def _create_once():
        async with session_factory() as session:
            return await PaymentService(session).create_payment(payload, idempotency_key="idem-concurrent-1")

    first, second = await asyncio.gather(_create_once(), _create_once())

    assert first.id == second.id

    async with session_factory() as verify_session:
        all_items = (await verify_session.scalars(select(Payment))).all()
    assert len(all_items) == 1

    await engine.dispose()
    db_path.unlink(missing_ok=True)
