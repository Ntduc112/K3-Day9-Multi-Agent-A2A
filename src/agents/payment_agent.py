"""Payment-domain agent.

The agent reconciles order payments against item + freight totals supplied by
the Order & Seller Agent (via the coordinator). It owns payment_value
aggregation only; it never applies refund policy or reads delivery/order facts.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from src.money import money_str, to_decimal

RECONCILIATION_TOLERANCE_BRL = Decimal("0.10")


class PaymentIndex:
    """Loads olist_order_payments_dataset.csv once and indexes rows by order_id."""

    def __init__(self, data_dir: str | Path = "data") -> None:
        path = Path(data_dir) / "olist_order_payments_dataset.csv"
        rows_by_order: dict[str, list[dict[str, str]]] = defaultdict(list)
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                rows_by_order[row["order_id"]].append(row)
        self._rows_by_order = dict(rows_by_order)

    def rows_for(self, order_id: str) -> list[dict[str, str]]:
        rows = self._rows_by_order.get(order_id, [])
        return sorted(rows, key=lambda row: int(row["payment_sequential"]))


class PaymentAgent:
    """Reconciles order payments with item + freight totals."""

    name = "payment_agent"

    def __init__(self, index: PaymentIndex | None = None, data_dir: str | Path = "data") -> None:
        self.index = index or PaymentIndex(data_dir)

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        case_id = request.get("case_id")
        order_id = request.get("order_id")
        try:
            if not order_id:
                raise ValueError("order_id is required")

            item_total = to_decimal(request.get("item_total_brl", "0"))
            freight_total = to_decimal(request.get("freight_total_brl", "0"))
            rows = self.index.rows_for(order_id)

            payment_total = Decimal("0.00")
            for row in rows:
                payment_total += to_decimal(row["payment_value"])

            expected_total = item_total + freight_total
            is_reconciled = abs(payment_total - expected_total) <= RECONCILIATION_TOLERANCE_BRL
            valid_split_payment = len(rows) >= 2 and is_reconciled

            payment_ids = [f"{order_id}:{row['payment_sequential']}" for row in rows]
            evidence_ids = [f"payment:{order_id}:{row['payment_sequential']}" for row in rows]

            return {
                "agent": self.name,
                "case_id": case_id,
                "status": "success",
                "facts": {
                    "payment_total_brl": money_str(payment_total),
                    "payment_row_count": len(rows),
                    "is_reconciled": is_reconciled,
                    "valid_split_payment": valid_split_payment,
                },
                "payment_ids": payment_ids,
                "evidence_ids": evidence_ids,
                "errors": [],
            }
        except (TypeError, ValueError, InvalidOperation, KeyError) as exc:
            return {
                "agent": self.name,
                "case_id": case_id,
                "status": "error",
                "facts": {},
                "payment_ids": [],
                "evidence_ids": [],
                "errors": [{"code": "INVALID_PAYMENT_REQUEST", "message": str(exc)}],
            }
