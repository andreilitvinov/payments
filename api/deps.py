from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from db.session import SessionLocal, get_db
from integrations.bank_client import BankClient
from services.payment_service import PaymentService


def get_payment_service(db: Annotated[Session, Depends(get_db)]) -> PaymentService:
    return PaymentService(db=db, bank_client=BankClient())
