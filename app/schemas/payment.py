from datetime import datetime
from decimal import Decimal
import enum
import ipaddress
import socket
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator

class PaymentStatusResponse(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"


class CreatePaymentRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(pattern="^(RUB|USD|EUR)$")
    description: str = Field(min_length=1, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)
    webhook_url: HttpUrl

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, value: HttpUrl) -> HttpUrl:
        host = value.host or ""
        if value.scheme != "https":
            raise ValueError("webhook_url must use https")

        if host.lower() == "localhost":
            raise ValueError("webhook_url host is not allowed")

        try:
            parsed_ip = ipaddress.ip_address(host)
        except ValueError:
            parsed_ip = None

        if parsed_ip is not None and _is_blocked_ip(parsed_ip):
            raise ValueError("webhook_url host is not allowed")

        if parsed_ip is None:
            try:
                addrinfo = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
            except socket.gaierror:
                addrinfo = []
            for entry in addrinfo:
                ip_text = entry[4][0]
                if _is_blocked_ip(ipaddress.ip_address(ip_text)):
                    raise ValueError("webhook_url host is not allowed")

        return value


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(
        [
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        ]
    )


class PaymentAcceptedResponse(BaseModel):
    payment_id: UUID
    status: PaymentStatusResponse
    created_at: datetime


class PaymentResponse(BaseModel):
    id: UUID
    amount: Decimal
    currency: str
    description: str
    metadata: dict[str, Any]
    status: PaymentStatusResponse
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None
