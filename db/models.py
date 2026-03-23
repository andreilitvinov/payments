from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Numeric, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from payments.models import PaymentType


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unpaid")

    payments: Mapped[list["PaymentModel"]] = relationship("PaymentModel", back_populates="order")

    def __repr__(self) -> str:
        return f"OrderModel(id={self.id}, total_amount={self.total_amount}, payment_status={self.payment_status})"


class PaymentModel(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    payment_type: Mapped[str] = mapped_column(String(32), nullable=False)  # cash | acquiring
    deposited_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    refunded_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending | completed | failed | refunded
    bank_payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    bank_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="payments")

    def __repr__(self) -> str:
        return f"PaymentModel(id={self.id}, order_id={self.order_id}, type={self.payment_type}, status={self.status})"
