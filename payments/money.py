from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import NewType, Union


Money = NewType("Money", Decimal)
MoneyLike = Union[str, int, float, Decimal, Money]


_Q = Decimal("0.01")


def money(value: MoneyLike) -> Money:
    """
    Convert value to a 2-decimal quantized Decimal.

    Notes:
    - Accepts strings to avoid float rounding surprises in call sites.
    - Uses ROUND_HALF_UP which is a common expectation for money amounts.
    """
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    q = d.quantize(_Q, rounding=ROUND_HALF_UP)
    return Money(q)


@dataclass(frozen=True, slots=True)
class MoneyError(ValueError):
    message: str

    def __str__(self) -> str:  # pragma: no cover
        return self.message

