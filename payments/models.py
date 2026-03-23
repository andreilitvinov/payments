from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from .money import Money, MoneyLike, MoneyError, money


class PaymentType(str, Enum):
    CASH = "cash"
    ACQUIRING = "acquiring"


class OrderPaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"


class PaymentStatus(str, Enum):
    """Payment lifecycle status (for acquiring: pending until bank confirms)."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass(slots=True)
class Order:
    id: int
    total_amount: Money
    payment_status: OrderPaymentStatus = OrderPaymentStatus.UNPAID
    payments: List["Payment"] = field(default_factory=list, repr=False)

    @property
    def net_paid_amount(self) -> Money:
        total = Decimal("0")
        for p in self.payments:
            total += p.net_amount
        return money(total)

    def _recalc_payment_status(self) -> None:
        if self.net_paid_amount <= money("0"):
            self.payment_status = OrderPaymentStatus.UNPAID
        elif self.net_paid_amount < self.total_amount:
            self.payment_status = OrderPaymentStatus.PARTIALLY_PAID
        else:
            self.payment_status = OrderPaymentStatus.PAID

    def add_payment(self, payment: "Payment") -> None:
        self.payments.append(payment)
        self._recalc_payment_status()


@dataclass(slots=True)
class Payment:
    payment_id: str
    order: Order = field(repr=False)
    payment_type: PaymentType
    deposited_amount: Money = field(default_factory=lambda: money("0"))
    refunded_amount: Money = field(default_factory=lambda: money("0"))

    @property
    def net_amount(self) -> Money:
        return money(Decimal(self.deposited_amount) - Decimal(self.refunded_amount))

    def deposit(self, amount: MoneyLike) -> None:
        if (amt := money(amount)) <= money("0"):
            raise MoneyError("Deposit amount must be positive.")

        new_order_net = money(Decimal(self.order.net_paid_amount) + Decimal(amt))
        if new_order_net > self.order.total_amount:
            raise MoneyError(
                "Total paid amount for the order cannot exceed order total."
            )

        self.deposited_amount = money(Decimal(self.deposited_amount) + Decimal(amt))
        self.order._recalc_payment_status()

    def refund(self, amount: MoneyLike) -> None:
        if (amt := money(amount)) <= money("0"):
            raise MoneyError("Refund amount must be positive.")

        available = self.net_amount
        if amt > available:
            raise MoneyError("Refund amount cannot exceed payment net amount.")

        self.refunded_amount = money(Decimal(self.refunded_amount) + Decimal(amt))
        self.order._recalc_payment_status()

