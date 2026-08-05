"""Audit A2A handoffs between the deterministic domain agents."""

from __future__ import annotations

from typing import Any


def _payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    facts = value.get("facts")
    payload = dict(facts) if isinstance(facts, dict) else dict(value)
    for key in ("order_ids", "item_ids", "seller_ids", "payment_ids", "evidence_ids"):
        if key in value and key not in payload:
            payload[key] = value[key]
    nested_ids = value.get("entity_ids")
    if isinstance(nested_ids, dict):
        for key in ("order_ids", "item_ids", "seller_ids", "payment_ids"):
            if key in nested_ids and key not in payload:
                payload[key] = nested_ids[key]
    return payload


class ContractAuditAgent:
    """Find missing or inconsistent handoff fields without changing business facts."""

    name = "contract_audit_agent"

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        order = _payload(request.get("order_facts"))
        payment = _payload(request.get("payment_facts"))
        delivery = _payload(request.get("delivery_facts"))

        order_id = request.get("claimed_order_id") or order.get("order_id")
        if not order_id:
            errors.append({"code": "MISSING_ORDER_FACT", "field": "order_facts.order_id"})
        if not order.get("order_ids"):
            errors.append({"code": "MISSING_ORDER_IDS", "field": "order_facts.order_ids"})
        if payment and not payment.get("payment_ids") and int(payment.get("payment_row_count", 0)) > 0:
            errors.append({"code": "MISSING_PAYMENT_IDS", "field": "payment_facts.payment_ids"})
        if delivery and "delivered_late" not in delivery:
            errors.append({"code": "MISSING_DELIVERY_FACT", "field": "delivery_facts.delivered_late"})

        order_ids = set(str(item) for item in order.get("order_ids", []))
        payment_ids = [str(item) for item in payment.get("payment_ids", [])]
        for payment_id in payment_ids:
            if order_ids and not payment_id.startswith(tuple(f"{oid}:" for oid in order_ids)):
                errors.append({"code": "CROSS_ORDER_PAYMENT", "field": "payment_facts.payment_ids"})
                break

        return {
            "agent": self.name,
            "case_id": request.get("case_id"),
            "status": "success" if not errors else "error",
            "valid": not errors,
            "errors": errors,
        }
