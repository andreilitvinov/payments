import asyncio
from datetime import datetime, timedelta, timezone

from faststream.rabbit import RabbitQueue
from sqlalchemy import or_, select

from app.core.config import settings
from app.db.models import Outbox, OutboxStatus
from app.db.session import SessionLocal
from app.messaging.broker import broker

QUEUE_SETTINGS: dict[str, RabbitQueue] = {
    "payments.new": RabbitQueue(
        "payments.new",
        durable=True,
        arguments={"x-message-ttl": 86400000},
    ),
    "payments.dlq": RabbitQueue(
        "payments.dlq",
        durable=True,
        arguments={"x-message-ttl": 604800000},
    ),
}


class OutboxRelay:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False

    def start(self) -> None:
        if self._task is None:
            self._running = True
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None

    async def _run(self) -> None:
        try:
            while self._running:
                await self._publish_once()
                await asyncio.sleep(settings.outbox_poll_interval_seconds)
        except asyncio.CancelledError:
            raise

    async def _publish_once(self) -> None:
        for _ in range(50):
            async with SessionLocal() as session:
                now = datetime.now(timezone.utc)
                stmt = (
                    select(Outbox)
                    .where(
                        Outbox.status == OutboxStatus.pending,
                        or_(Outbox.next_retry_at.is_(None), Outbox.next_retry_at <= now),
                    )
                    .order_by(Outbox.created_at)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                message = await session.scalar(stmt)
                if message is None:
                    return

                try:
                    queue = QUEUE_SETTINGS.get(message.topic, message.topic)
                    await broker.publish(message.payload, queue=queue)
                    message.status = OutboxStatus.published
                    message.published_at = datetime.now(timezone.utc)
                    message.next_retry_at = None
                    message.error = None
                except Exception as exc:
                    message.attempts += 1
                    message.error = str(exc)
                    if message.attempts >= settings.outbox_max_attempts:
                        message.status = OutboxStatus.failed
                        message.next_retry_at = None
                    else:
                        message.next_retry_at = datetime.now(timezone.utc) + timedelta(
                            seconds=2 ** (message.attempts - 1)
                        )
                await session.commit()
