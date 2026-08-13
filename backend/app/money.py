"""Decimal money helpers — never float."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, List


def D(value: str | int | Decimal) -> Decimal:
    """Parse money as Decimal. Reject float."""
    if isinstance(value, float):
        raise TypeError("float is not allowed for money; use str or Decimal")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def money(value: str | int | Decimal) -> Decimal:
    """Quantize to cents."""
    return D(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def allocate(total: Decimal, periods: int) -> List[Decimal]:
    """
    Split total across N periods; remainder absorbed in the final period
    so the schedule sums exactly to total.
    """
    if periods < 1:
        raise ValueError("periods must be >= 1")
    total = money(total)
    if periods == 1:
        return [total]
    base = money(total / periods)
    parts = [base] * (periods - 1)
    parts.append(money(total - sum(parts)))
    return parts


def assert_no_float(value: object) -> None:
    if isinstance(value, float):
        raise TypeError(f"float not allowed: {value!r}")


def sum_money(values: Iterable[Decimal]) -> Decimal:
    return money(sum((money(v) for v in values), Decimal("0")))
