from decimal import Decimal
from pydantic import BaseModel, Field
from payments.models import OrderPaymentStatus, PaymentStatus, PaymentType


class OrderCreate(BaseModel):
    total_amount: Decimal = Field(..., gt=0)

    class Config:
        json_encoders = {Decimal: str}


class OrderResponse(BaseModel):
    id: int
    total_amount: Decimal
    payment_status: OrderPaymentStatus

    class Config:
        from_attributes = True


class PaymentCreate(BaseModel):
    payment_type: PaymentType
    amount: Decimal = Field(..., gt=0)

    class Config:
        json_encoders = {Decimal: str}


class PaymentResponse(BaseModel):
    id: int
    order_id: int
    payment_type: PaymentType
    deposited_amount: Decimal
    refunded_amount: Decimal
    status: PaymentStatus
    bank_payment_id: str | None

    class Config:
        from_attributes = True


class RefundRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)

    class Config:
        json_encoders = {Decimal: str}
