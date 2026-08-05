"""Deterministic money helpers shared across domain agents.

Money must be represented as Decimal internally and as a fixed two-decimal
string when crossing an agent boundary (e.g. "115.00"), per the EC_POLICY_V1
contract convention. Never sum BRL values with binary float.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

CENT = Decimal("0.01")


def to_decimal(value: Any) -> Decimal:
    """Parse a raw CSV/JSON value into a 2-decimal-place Decimal."""
    if value is None or value == "":
        value = "0"
    try:
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid money value: {value!r}") from exc


def money_str(value: Decimal) -> str:
    """Format a Decimal as the contract's fixed 2-decimal string, e.g. '115.00'."""
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))
