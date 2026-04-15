from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Outbox, OutboxStatus, Payment, PaymentStatus
from app.schemas.payment import CreatePaymentRequest
from app.services.exceptions import PaymentNotFoundError
from app.services.metrics import metrics_store


class PaymentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_payment(self, dto: CreatePaymentRequest, idempotency_key: str) -> Payment:
        try:
            existing = await self.session.scalar(
                select(Payment).where(Payment.idempotency_key == idempotency_key)
            )
            if existing:
                return existing

            payment = Payment(
                amount=Decimal(dto.amount),
                currency=dto.currency,
                description=dto.description,
                metadata_json=dto.metadata,
                status=PaymentStatus.pending,
                idempotency_key=idempotency_key,
                webhook_url=str(dto.webhook_url),
            )
            self.session.add(payment)
            await self.session.flush()

            outbox = Outbox(
                topic="payments.new",
                payload={"payment_id": str(payment.id), "attempt": 1},
                status=OutboxStatus.pending,
            )
            self.session.add(outbox)
            await self.session.commit()
            await self.session.refresh(payment)
        except IntegrityError:
            await self.session.rollback()
            existing = await self.session.scalar(
                select(Payment).where(Payment.idempotency_key == idempotency_key)
            )
            if existing is None:
                raise
            return existing

        metrics_store.payments_created_total += 1
        return payment

    async def get_payment(self, payment_id: UUID) -> Payment:
        payment = await self.session.get(Payment, payment_id)
        if payment is None:
            raise PaymentNotFoundError("Payment not found")
        metrics_store.payments_fetched_total += 1
        return payment

    async def update_payment_status(
        self,
        payment: Payment,
        status_value: PaymentStatus,
    ) -> Payment:
        payment.status = status_value
        payment.processed_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment
