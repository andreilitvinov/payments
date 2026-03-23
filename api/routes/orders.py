from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas import OrderCreate, OrderResponse, PaymentCreate, PaymentResponse
from api.deps import get_payment_service
from services.payment_service import PaymentService
from payments.money import MoneyError
from integrations.bank_client import BankError
from integrations.bank_client import BankErrorCode

router = APIRouter()


@router.get("", response_model=list[OrderResponse])
def list_orders(
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> list:
    orders = service.list_orders()
    return [OrderResponse.model_validate(o) for o in orders]


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    service: Annotated[PaymentService, Depends(get_payment_service)],
):
    try:
        order = service.get_order_by_id(order_id)
        return OrderResponse.model_validate(order)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    body: OrderCreate,
    service: Annotated[PaymentService, Depends(get_payment_service)],
):
    try:
        order = service.add_order(body.total_amount)
        return OrderResponse.model_validate(order)
    except MoneyError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{order_id}/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment(
    order_id: int,
    body: PaymentCreate,
    service: Annotated[PaymentService, Depends(get_payment_service)],
):
    try:
        payment = await service.create_payment(order_id, body.payment_type, body.amount)
        return PaymentResponse.model_validate(payment)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MoneyError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BankError as e:
        if e.code == BankErrorCode.NOT_FOUND:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found at bank")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Bank API error: {e.message}")
