from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from api.schemas import PaymentResponse, RefundRequest
from api.deps import get_payment_service
from services.payment_service import PaymentService
from payments.money import MoneyError
from integrations.bank_client import BankError
from integrations.bank_client import BankErrorCode

router = APIRouter()


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(
    payment_id: int = Path(..., gt=0),
    service: Annotated[PaymentService, Depends(get_payment_service)] = None,
):
    try:
        payment = service.get_payment(payment_id)
        return PaymentResponse.model_validate(payment)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")


@router.post("/{payment_id}/refund", status_code=status.HTTP_204_NO_CONTENT)
def refund_payment(
    payment_id: int = Path(..., gt=0),
    body: RefundRequest = ...,
    service: Annotated[PaymentService, Depends(get_payment_service)] = None,
):
    try:
        service.refund(payment_id, body.amount)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    except MoneyError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{payment_id}/sync", status_code=status.HTTP_204_NO_CONTENT)
async def sync_payment(
    payment_id: int = Path(..., gt=0),
    service: Annotated[PaymentService, Depends(get_payment_service)] = None,
):
    try:
        await service.sync_acquiring_payment(payment_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BankError as e:
        if e.code == BankErrorCode.NOT_FOUND:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found at bank")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Bank API error: {e.message}")
