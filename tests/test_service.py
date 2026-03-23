"""Service layer tests with mocked bank client."""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.base import Base
from db.models import OrderModel, PaymentModel
from payments.models import PaymentType, PaymentStatus, OrderPaymentStatus
from services.payment_service import PaymentService
from integrations.bank_client import BankClient


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def mock_bank():
    bank = AsyncMock(spec=BankClient)
    bank.acquiring_start = AsyncMock(return_value="bank-123")
    bank.acquiring_check = AsyncMock(return_value=type("Info", (), {
        "bank_payment_id": "bank-123",
        "amount": Decimal("25.00"),
        "status": "paid",
        "paid_at": None,
    })())
    return bank


@pytest.fixture
def service(db, mock_bank):
    return PaymentService(db=db, bank_client=mock_bank)


@pytest.mark.asyncio
async def test_create_cash_payment(service, db):
    order = service.add_order("100.00")
    db.commit()
    payment = await service.create_payment(order.id, PaymentType.CASH, "40.00")
    db.commit()
    assert payment.payment_type == "cash"
    assert payment.status == PaymentStatus.COMPLETED.value
    assert payment.deposited_amount == Decimal("40.00")
    order = service.get_order_by_id(order.id)
    assert order.payment_status == "partially_paid"


@pytest.mark.asyncio
async def test_create_acquiring_payment(service, db, mock_bank):
    order = service.add_order("100.00")
    db.commit()
    payment = await service.create_payment(order.id, PaymentType.ACQUIRING, "100.00")
    db.commit()
    assert payment.payment_type == "acquiring"
    assert payment.status == PaymentStatus.PENDING.value
    assert payment.bank_payment_id == "bank-123"
    assert payment.deposited_amount == Decimal("0")  # until sync
    mock_bank.acquiring_start.assert_called_once()


@pytest.mark.asyncio
async def test_sync_acquiring_sets_completed(service, db, mock_bank):
    mock_bank.acquiring_check.return_value = type("Info", (), {
        "bank_payment_id": "bank-123",
        "amount": Decimal("50.00"),
        "status": "completed",
        "paid_at": None,
    })()
    order = service.add_order("50.00")
    db.commit()
    payment = await service.create_payment(order.id, PaymentType.ACQUIRING, "50.00")
    db.commit()
    await service.sync_acquiring_payment(payment.id)
    db.commit()
    payment = service.get_payment(payment.id)
    assert payment.status == PaymentStatus.COMPLETED.value
    assert payment.deposited_amount == Decimal("50.00")
    assert service.get_order_by_id(order.id).payment_status == "paid"


@pytest.mark.asyncio
async def test_refund(service, db):
    order = service.add_order("80.00")
    db.commit()
    p = await service.create_payment(order.id, PaymentType.CASH, "80.00")
    db.commit()
    service.refund(p.id, "30.00")
    db.commit()
    p = service.get_payment(p.id)
    assert p.refunded_amount == Decimal("30.00")
    assert service.get_order_by_id(order.id).payment_status == "partially_paid"
