from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .money import MoneyLike, MoneyError, money
from .models import Order, Payment, PaymentType


@dataclass(slots=True)
class PaymentService:
    """
    In-memory service holding orders and their payments.

    Orders are "pre-existing" from the perspective of the task: this service
    doesn't form new orders in a business workflow, but allows to register
    existing orders into its in-memory list for payment operations.
    """

    _orders: Dict[int, Order] = None  # type: ignore[assignment]
    _payments: Dict[str, Payment] = None  # type: ignore[assignment]
    _seq: int = 0
    _order_seq: int = 0

    def __post_init__(self) -> None:
        self._orders = {}
        self._payments = {}

    def add_order(self, total_amount: MoneyLike) -> Order:
        total = money(total_amount)
        if total <= money("0"):
            raise MoneyError("Order total amount must be positive.")
        self._order_seq += 1
        order = Order(id=self._order_seq, total_amount=total)
        self._orders[order.id] = order
        return order

    def get_order(self, order_id: int) -> Order:
        try:
            return self._orders[order_id]
        except KeyError as e:
            raise KeyError(f"Unknown order: {order_id}") from e

    def create_payment(self, order_id: int, payment_type: PaymentType) -> Payment:
        order = self.get_order(order_id)
        self._seq += 1
        payment_id = f"p{self._seq}"
        payment = Payment(
            payment_id=payment_id,
            order=order,
            payment_type=payment_type,
        )
        order.add_payment(payment)
        self._payments[payment_id] = payment
        return payment

    def get_payment(self, payment_id: str) -> Payment:
        try:
            return self._payments[payment_id]
        except KeyError as e:
            raise KeyError(f"Unknown payment: {payment_id}") from e

