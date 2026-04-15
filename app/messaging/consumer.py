import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Outbox, OutboxStatus, Payment, PaymentStatus
from app.db.session import SessionLocal
from app.messaging.broker import broker
from app.services.metrics import metrics_store
from app.services.webhook import send_webhook_with_retry

MAX_PROCESS_ATTEMPTS = 3
DLQ_REASON_INVALID_PAYLOAD = "invalid_payload"
DLQ_REASON_STATUS_UPDATE_FAILED = "status_update_failed"
DLQ_REASON_WEBHOOK_DELIVERY_FAILED = "webhook_delivery_failed"

logger = logging.getLogger(__name__)


def _build_webhook_payload(payment: Payment) -> dict:
    return {
        "payment_id": str(payment.id),
        "status": payment.status.value,
        "amount": float(payment.amount),
        "currency": payment.currency,
    }


def _extract_message_data(message: dict) -> tuple[UUID, int]:
    payment_id = UUID(str(message["payment_id"]))
    attempt = int(message.get("attempt", 1))
    return payment_id, max(1, attempt)


async def _publish_retry_or_dlq(payment_id: UUID, attempt: int, reason: str) -> None:
    retry_delay_seconds = 2 ** (attempt - 1)
    if attempt >= MAX_PROCESS_ATTEMPTS:
        _record_dlq_reason(reason)
        metrics_store.dlq_published_total += 1
        await _enqueue_outbox_message(
            topic="payments.dlq",
            payload={"payment_id": str(payment_id), "attempt": attempt, "reason": reason},
        )
        return
    await _enqueue_outbox_message(
        topic="payments.new",
        payload={"payment_id": str(payment_id), "attempt": attempt + 1, "reason": reason},
        delay_seconds=retry_delay_seconds,
    )


async def _publish_invalid_message_to_dlq(message: dict) -> None:
    _record_dlq_reason(DLQ_REASON_INVALID_PAYLOAD)
    metrics_store.dlq_published_total += 1
    await _enqueue_outbox_message(
        topic="payments.dlq",
        payload={"message": message, "reason": DLQ_REASON_INVALID_PAYLOAD},
    )


async def _enqueue_outbox_message(topic: str, payload: dict, delay_seconds: int = 0) -> None:
    async with SessionLocal() as session:
        outbox = Outbox(topic=topic, payload=payload, status=OutboxStatus.pending)
        if delay_seconds > 0:
            outbox.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        session.add(outbox)
        await session.commit()


def _record_dlq_reason(reason: str) -> None:
    if reason == DLQ_REASON_INVALID_PAYLOAD:
        metrics_store.dlq_invalid_payload_total += 1
    elif reason == DLQ_REASON_STATUS_UPDATE_FAILED:
        metrics_store.dlq_status_update_failed_total += 1
    elif reason == DLQ_REASON_WEBHOOK_DELIVERY_FAILED:
        metrics_store.dlq_webhook_delivery_failed_total += 1


async def _load_payment_for_processing(session: AsyncSession, payment_id: UUID) -> Payment | None:
    stmt = (
        select(Payment)
        .where(Payment.id == payment_id, Payment.status == PaymentStatus.pending)
        .with_for_update(skip_locked=True)
    )
    return await session.scalar(stmt)


async def _load_payment_for_webhook_retry(session: AsyncSession, payment_id: UUID) -> Payment | None:
    stmt = select(Payment).where(Payment.id == payment_id)
    return await session.scalar(stmt)


@broker.subscriber("payments.new")
async def process_payment(message: dict) -> None:
    try:
        payment_id, attempt = _extract_message_data(message)
    except (KeyError, TypeError, ValueError):
        await _publish_invalid_message_to_dlq(message)
        return

    async with SessionLocal() as session:
        payment = await _load_payment_for_processing(session, payment_id)
        if payment is None:
            payment = await _load_payment_for_webhook_retry(session, payment_id)
            if payment is None or payment.status == PaymentStatus.pending:
                return
        else:
            await asyncio.sleep(random.uniform(2, 5))
            is_success = random.random() <= 0.9
            payment.status = PaymentStatus.succeeded if is_success else PaymentStatus.failed
            payment.processed_at = datetime.now(timezone.utc)
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                await _publish_retry_or_dlq(payment_id, attempt, DLQ_REASON_STATUS_UPDATE_FAILED)
                return

            if payment.status == PaymentStatus.succeeded:
                metrics_store.payment_processing_success_total += 1
            else:
                metrics_store.payment_processing_failed_total += 1

        webhook_payload = _build_webhook_payload(payment)
        try:
            await send_webhook_with_retry(payment.webhook_url, webhook_payload)
        except Exception:
            metrics_store.webhook_failures_total += 1
            await _publish_retry_or_dlq(payment_id, attempt, DLQ_REASON_WEBHOOK_DELIVERY_FAILED)
            return


@broker.subscriber("payments.dlq")
async def process_dead_letter(message: dict) -> None:
    metrics_store.dlq_consumed_total += 1
    logger.error("DLQ message consumed", extra={"dlq_message": message})
