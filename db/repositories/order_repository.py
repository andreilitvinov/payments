from __future__ import annotations

from decimal import Decimal
from sqlalchemy.orm import Session

from db.models import OrderModel


class OrderRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, total_amount: Decimal) -> OrderModel:
        order = OrderModel(total_amount=total_amount, payment_status="unpaid")
        self._db.add(order)
        return order

    def get_by_id(self, id: int) -> OrderModel | None:
        return self._db.get(OrderModel, id)

    def list_all(self) -> list[OrderModel]:
        return list(self._db.query(OrderModel).order_by(OrderModel.id).all())

    def set_payment_status(self, order: OrderModel, status: str) -> None:
        order.payment_status = status
