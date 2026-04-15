from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_api_key
from app.db.session import get_db_session
from app.schemas.payment import (
    CreatePaymentRequest,
    PaymentAcceptedResponse,
    PaymentResponse,
    PaymentStatusResponse,
)
from app.services.exceptions import PaymentNotFoundError
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"], dependencies=[Depends(verify_api_key)])


def _to_response(payment) -> PaymentResponse:
    return PaymentResponse(
        id=payment.id,
        amount=payment.amount,
        currency=payment.currency,
        description=payment.description,
        metadata=payment.metadata_json,
        status=PaymentStatusResponse(payment.status.value),
        idempotency_key=payment.idempotency_key,
        webhook_url=payment.webhook_url,
        created_at=payment.created_at,
        processed_at=payment.processed_at,
    )


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=PaymentAcceptedResponse)
async def create_payment(
    payload: CreatePaymentRequest,
    session: AsyncSession = Depends(get_db_session),
    idempotency_key: Annotated[
        str,
        Header(
            ...,
            min_length=1,
            max_length=128,
            pattern=r"^[A-Za-z0-9._:-]+$",
            alias="Idempotency-Key",
        ),
    ] = "",
) -> PaymentAcceptedResponse:
    payment = await PaymentService(session).create_payment(payload, idempotency_key=idempotency_key)
    return PaymentAcceptedResponse(
        payment_id=payment.id,
        status=PaymentStatusResponse(payment.status.value),
        created_at=payment.created_at,
    )


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> PaymentResponse:
    try:
        payment = await PaymentService(session).get_payment(payment_id)
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(payment)
