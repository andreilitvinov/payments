"""
Service layer: payment and order operations.
Uses repositories for persistence and BankClient for acquiring.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy.orm import Session

from payments.money import money, MoneyLike, MoneyError
from payments.models import OrderPaymentStatus, PaymentStatus, PaymentType
from db.repositories import OrderRepository, PaymentRepository
from integrations.bank_client import BankClient, BankError, BankErrorCode

if TYPE_CHECKING:
    from db.models import OrderModel, PaymentModel


class PaymentService:
    def __init__(self, db: Session, bank_client: BankClient | None = None) -> None:
        self._db = db
        self._orders = OrderRepository(db)
        self._payments = PaymentRepository(db)
        self._bank = bank_client or BankClient()

    def add_order(self, total_amount: MoneyLike) -> "OrderModel":
        try:
            total = money(total_amount)
            if total <= money("0"):
                raise MoneyError("Order total amount must be positive.")
            order = self._orders.add(Decimal(str(total)))
            self._db.commit()
            self._db.refresh(order)
            return order
        except Exception:
            self._db.rollback()
            raise

    def get_order_by_id(self, order_id: int) -> "OrderModel":
        o = self._orders.get_by_id(order_id)
        if not o:
            raise KeyError(f"Unknown order: {order_id}")
        return o

    def list_orders(self) -> list:
        return self._orders.list_all()

    def _order_net_paid(self, order_id: int) -> Decimal:
        payments = self._payments.get_by_order_id(order_id)
        total = Decimal("0")
        for p in payments:
            if p.status == PaymentStatus.COMPLETED.value:
                total += p.deposited_amount - p.refunded_amount
        return total

    def _recalc_order_status(self, order_id: int, total_amount: Decimal) -> None:
        order = self._orders.get_by_id(order_id)
        if not order:
            return
        paid = self._order_net_paid(order_id)
        if paid <= 0:
            status = OrderPaymentStatus.UNPAID.value
        elif paid < total_amount:
            status = OrderPaymentStatus.PARTIALLY_PAID.value
        else:
            status = OrderPaymentStatus.PAID.value
        self._orders.set_payment_status(order, status)

    async def create_payment(self, order_id: int, payment_type: PaymentType, amount: MoneyLike) -> "PaymentModel":
        try:
            amount_dec = money(amount)
            if amount_dec <= money("0"):
                raise MoneyError("Amount must be positive.")
            order = self.get_order_by_id(order_id)
            total = order.total_amount
            current_paid = self._order_net_paid(order.id)
            if current_paid + amount_dec > total:
                raise MoneyError("Total payments would exceed order amount.")

            if payment_type == PaymentType.CASH:
                payment = self._payments.add(
                    order.id,
                    PaymentType.CASH.value,
                    status=PaymentStatus.COMPLETED.value,
                )
                self._payments.set_deposited(payment, amount_dec)
                self._db.flush()
                self._recalc_order_status(order.id, total)
                self._db.commit()
                self._db.refresh(payment)
                return payment

            # Acquiring: call bank, then create payment in pending state
            bank_id = await self._bank.acquiring_start(str(order.id), str(amount_dec))
            payment = self._payments.add(
                order.id,
                PaymentType.ACQUIRING.value,
                bank_payment_id=bank_id,
                status=PaymentStatus.PENDING.value,
            )
            # Don't set deposited_amount until bank confirms (via sync)
            self._db.commit()
            self._db.refresh(payment)
            return payment
        except Exception:
            self._db.rollback()
            raise

    def get_payment(self, payment_id: int) -> "PaymentModel":
        p = self._payments.get_by_id(payment_id)
        if not p:
            raise KeyError(f"Unknown payment: {payment_id}")
        return p

    def refund(self, payment_id: int, amount: MoneyLike) -> None:
        try:
            amount_dec = money(amount)
            if amount_dec <= money("0"):
                raise MoneyError("Refund amount must be positive.")
            payment = self.get_payment(payment_id)
            if payment.status != PaymentStatus.COMPLETED.value:
                raise MoneyError("Can only refund completed payments.")
            net = payment.deposited_amount - payment.refunded_amount
            if amount_dec > net:
                raise MoneyError("Refund amount cannot exceed payment net amount.")
            self._payments.set_refunded(payment, payment.refunded_amount + amount_dec)
            self._payments.set_status(payment, PaymentStatus.REFUNDED.value if (net - amount_dec) == 0 else payment.status)
            order = payment.order
            self._db.flush()
            self._recalc_order_status(order.id, order.total_amount)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

    async def sync_acquiring_payment(self, payment_id: int) -> None:
        """Poll bank for payment status and update our state."""
        try:
            payment = self.get_payment(payment_id)
            if payment.payment_type != PaymentType.ACQUIRING.value or not payment.bank_payment_id:
                raise ValueError("Payment is not an acquiring payment or has no bank id.")
            try:
                info = await self._bank.acquiring_check(payment.bank_payment_id)
            except BankError as e:
                if e.code == BankErrorCode.NOT_FOUND:
                    self._payments.set_status(payment, PaymentStatus.FAILED.value)
                    self._payments.set_bank_checked_at(payment)
                    self._db.commit()
                raise

            self._payments.set_bank_checked_at(payment)
            status_lower = info.status.lower()
            if status_lower in ("paid", "completed", "success"):
                if info.amount <= Decimal("0"):
                    raise MoneyError("Bank returned non-positive payment amount.")
                order = payment.order
                current_paid_excluding_payment = self._order_net_paid(order.id) - (
                    payment.deposited_amount - payment.refunded_amount
                )
                if current_paid_excluding_payment + info.amount > order.total_amount:
                    raise MoneyError("Bank payment amount exceeds remaining order amount.")
                self._payments.set_deposited(payment, info.amount)
                self._payments.set_status(payment, PaymentStatus.COMPLETED.value)
                self._db.flush()
                self._recalc_order_status(order.id, order.total_amount)
                self._db.commit()
            elif status_lower in ("failed", "cancelled", "error"):
                self._payments.set_status(payment, PaymentStatus.FAILED.value)
                self._db.commit()
        except Exception:
            self._db.rollback()
            raise
