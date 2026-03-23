from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session

from db.models import PaymentModel


class PaymentRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(
        self,
        order_id: int,
        payment_type: str,
        *,
        bank_payment_id: str | None = None,
        status: str = "pending",
    ) -> PaymentModel:
        payment = PaymentModel(
            order_id=order_id,
            payment_type=payment_type,
            deposited_amount=Decimal("0"),
            refunded_amount=Decimal("0"),
            status=status,
            bank_payment_id=bank_payment_id,
        )
        self._db.add(payment)
        return payment

    def get_by_id(self, id: int) -> PaymentModel | None:
        return self._db.get(PaymentModel, id)

    def get_by_order_id(self, order_id: int) -> list[PaymentModel]:
        return list(
            self._db.query(PaymentModel).filter(PaymentModel.order_id == order_id).order_by(PaymentModel.id).all()
        )

    def get_by_bank_payment_id(self, bank_payment_id: str) -> PaymentModel | None:
        return self._db.query(PaymentModel).filter(PaymentModel.bank_payment_id == bank_payment_id).first()

    def set_deposited(self, payment: PaymentModel, amount: Decimal) -> None:
        payment.deposited_amount = amount

    def set_refunded(self, payment: PaymentModel, amount: Decimal) -> None:
        payment.refunded_amount = amount

    def set_status(self, payment: PaymentModel, status: str) -> None:
        payment.status = status

    def set_bank_checked_at(self, payment: PaymentModel, when: datetime | None = None) -> None:
        payment.bank_checked_at = when if when is not None else datetime.now(timezone.utc)
