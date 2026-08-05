"""Delivery-domain agent.

The agent receives normalized order/item facts. It owns timestamp comparison only;
it neither reads payments nor applies refund policy.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _parse_timestamp(value: Any, field: str) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp for {field}: {value!r}") from exc


class DeliveryAgent:
    """Determine lateness and which delivery stage caused it."""

    name = "delivery_agent"

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        case_id = request.get("case_id")
        order_facts = request.get("order_facts", request.get("facts", {}))
        items = request.get("item_facts", order_facts.get("items", []))

        try:
            delivered_customer = _parse_timestamp(
                order_facts.get("order_delivered_customer_date")
                or order_facts.get("delivered_customer_date"),
                "order_delivered_customer_date",
            )
            estimated = _parse_timestamp(
                order_facts.get("order_estimated_delivery_date")
                or order_facts.get("estimated_delivery_date"),
                "order_estimated_delivery_date",
            )
            delivered_carrier = _parse_timestamp(
                order_facts.get("order_delivered_carrier_date")
                or order_facts.get("delivered_carrier_date"),
                "order_delivered_carrier_date",
            )

            delivered_late = bool(
                delivered_customer is not None
                and estimated is not None
                and delivered_customer > estimated
            )
            delivered_within_estimate = bool(
                delivered_customer is not None
                and estimated is not None
                and delivered_customer <= estimated
            )

            late_seller_ids: list[str] = []
            late_item_ids: list[str] = []
            if delivered_carrier is not None:
                for item in items:
                    shipping_limit = _parse_timestamp(
                        item.get("shipping_limit_date"), "shipping_limit_date"
                    )
                    if shipping_limit is not None and delivered_carrier > shipping_limit:
                        seller_id = str(item.get("seller_id", ""))
                        item_id = str(item.get("order_item_id", ""))
                        if seller_id and seller_id not in late_seller_ids:
                            late_seller_ids.append(seller_id)
                        if item_id:
                            late_item_ids.append(item_id)

            seller_handoff_late = bool(late_seller_ids)
            delay_owner = None
            if delivered_late:
                delay_owner = "seller" if seller_handoff_late else "logistics_provider"

            return {
                "agent": self.name,
                "case_id": case_id,
                "status": "success",
                "facts": {
                    "delivered_late": delivered_late,
                    "delivered_within_estimate": delivered_within_estimate,
                    "seller_handoff_late": seller_handoff_late,
                    "late_seller_ids": late_seller_ids,
                    "late_item_ids": late_item_ids,
                    "delay_owner": delay_owner,
                },
                "errors": [],
            }
        except (TypeError, ValueError) as exc:
            return {
                "agent": self.name,
                "case_id": case_id,
                "status": "error",
                "facts": {},
                "errors": [{"code": "INVALID_DELIVERY_FACTS", "message": str(exc)}],
            }
