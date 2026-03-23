"""
Client for external Bank API.

API contract (as per task):
- acquiring_start: POST JSON { order_number, order_amount } -> success: bank payment id; failure: error string
- acquiring_check: accepts bank payment id -> payment details or "payment not found"
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

import httpx

from config import Settings


class BankError(Exception):
    """Bank API returned an error or request failed."""


class BankErrorCode(str, Enum):
    TIMEOUT = "timeout"
    REQUEST_FAILED = "request_failed"
    NOT_FOUND = "not_found"
    INVALID_RESPONSE = "invalid_response"
    API_ERROR = "api_error"


class BankError(Exception):
    """Bank API returned an error or request failed."""

    def __init__(
        self,
        message: str,
        *,
        code: BankErrorCode = BankErrorCode.API_ERROR,
        status_code: int | None = None,
        body: Any = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.body = body
        super().__init__(message)


@dataclass
class BankPaymentInfo:
    bank_payment_id: str
    amount: Decimal
    status: str
    paid_at: datetime | None


class BankClient:
    """
    Calls external Bank API. Treat as unreliable: timeouts, 5xx, network errors.
    State can change on bank side without our knowledge — sync via acquiring_check.
    """

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        settings = Settings()
        self._base_url = (base_url or settings.bank_api_base_url).rstrip("/")
        self._timeout = timeout if timeout is not None else settings.bank_api_timeout_seconds

    def _url(self, path: str) -> str:
        return f"{self._base_url}/{path.lstrip('/')}"

    async def acquiring_start(self, order_number: str, order_amount: str | Decimal) -> str:
        """
        Start acquiring payment. Returns bank payment id on success.
        Raises BankError on failure (including API error response).
        """
        payload = {
            "order_number": order_number,
            "order_amount": str(order_amount),
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                r = await client.post(self._url("acquiring_start"), json=payload)
            except httpx.TimeoutException as e:
                raise BankError(f"Bank API timeout: {e}", code=BankErrorCode.TIMEOUT) from e
            except httpx.RequestError as e:
                raise BankError(f"Bank API request failed: {e}", code=BankErrorCode.REQUEST_FAILED) from e

            data = _parse_json(r)
            if r.is_success:
                bid = data.get("bank_payment_id") or data.get("id") or data.get("payment_id")
                if bid is None:
                    raise BankError(
                        "Bank API success response missing payment id",
                        code=BankErrorCode.INVALID_RESPONSE,
                        status_code=r.status_code,
                        body=data,
                    )
                return str(bid)
            # Failure: API returns error string or object with message
            err = data.get("error") or data.get("message") or data if isinstance(data, str) else str(data)
            raise BankError(str(err), code=BankErrorCode.API_ERROR, status_code=r.status_code, body=data)

    async def acquiring_check(self, bank_payment_id: str) -> BankPaymentInfo:
        """
        Check payment status at bank. Returns payment info or raises BankError("payment not found").
        """
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                r = await client.get(
                    self._url("acquiring_check"),
                    params={"bank_payment_id": bank_payment_id},
                )
            except httpx.TimeoutException as e:
                raise BankError(f"Bank API timeout: {e}", code=BankErrorCode.TIMEOUT) from e
            except httpx.RequestError as e:
                raise BankError(f"Bank API request failed: {e}", code=BankErrorCode.REQUEST_FAILED) from e

            data = _parse_json(r)
            if not r.is_success:
                msg = (data.get("error") or data.get("message") or str(data)).lower()
                if "not found" in msg or r.status_code == httpx.codes.NOT_FOUND:
                    raise BankError(
                        "payment not found",
                        code=BankErrorCode.NOT_FOUND,
                        status_code=r.status_code,
                        body=data,
                    )
                raise BankError(
                    msg or f"Bank API error {r.status_code}",
                    code=BankErrorCode.API_ERROR,
                    status_code=r.status_code,
                    body=data,
                )

            # Success: id, amount, status, date/time
            bid = data.get("bank_payment_id") or data.get("id") or bank_payment_id
            amount_raw = data.get("amount", 0)
            try:
                amount = Decimal(str(amount_raw))
            except Exception as e:
                raise BankError(
                    f"Invalid amount from bank: {amount_raw!r}",
                    code=BankErrorCode.INVALID_RESPONSE,
                    status_code=r.status_code,
                    body=data,
                ) from e
            status = str(data.get("status", "unknown"))
            paid_at = None
            if data.get("paid_at"):
                paid_at = _parse_datetime(data["paid_at"])
            elif data.get("date") or data.get("datetime"):
                paid_at = _parse_datetime(data.get("date") or data.get("datetime"))

            return BankPaymentInfo(bank_payment_id=str(bid), amount=amount, status=status, paid_at=paid_at)


def _parse_json(r: httpx.Response) -> Any:
    try:
        return r.json()
    except ValueError:
        return {"error": r.text or f"HTTP {r.status_code}"}


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
