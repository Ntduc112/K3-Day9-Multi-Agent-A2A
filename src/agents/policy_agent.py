"""Deterministic EC_POLICY_V1 decision agent."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from src.policy import ISSUE_RULES, POLICY_VERSION

CENT = Decimal("0.01")


def _money(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0")).quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid money value: {value!r}") from exc


def _facts(result: dict[str, Any], key: str) -> dict[str, Any]:
    value = result.get(key, result)
    if isinstance(value, dict) and "facts" in value:
        envelope = value
        value = dict(envelope["facts"])
        # Entity and evidence lists belong to the agent response envelope in the
        # A2A contract, while domain values live under `facts`.
        for field in (
            "order_ids",
            "item_ids",
            "seller_ids",
            "payment_ids",
            "evidence_ids",
        ):
            if field in envelope and field not in value:
                value[field] = envelope[field]
    return value if isinstance(value, dict) else {}


class PolicyAgent:
    """Apply policy in the exact priority order defined by the assignment."""

    name = "policy_agent"

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        case_id = request.get("case_id")
        try:
            if request.get("policy_version", POLICY_VERSION) != POLICY_VERSION:
                raise ValueError(f"Unsupported policy: {request.get('policy_version')}")

            order = _facts(request, "order_facts")
            payment = _facts(request, "payment_facts")
            delivery = _facts(request, "delivery_facts")

            status = order.get("order_status")
            payment_total = _money(payment.get("payment_total_brl", 0))
            item_total = _money(order.get("item_total_brl", 0))
            freight_total = _money(order.get("freight_total_brl", 0))
            payment_rows = int(payment.get("payment_row_count", 0))
            reconciled = bool(payment.get("is_reconciled", False))

            if status == "canceled" and payment_total > 0:
                issue = "canceled_order_paid"
            elif status == "unavailable" and payment_total > 0:
                issue = "unavailable_order_paid"
            elif delivery.get("delivered_late") and delivery.get("seller_handoff_late"):
                issue = "late_delivery_seller"
            elif delivery.get("delivered_late") and not delivery.get("seller_handoff_late"):
                issue = "late_delivery_logistics"
            elif payment_rows >= 2 and reconciled:
                issue = "valid_split_payment"
            elif delivery.get("delivered_within_estimate") and reconciled:
                issue = "unsupported_late_claim"
            else:
                raise ValueError("Facts do not match any EC_POLICY_V1 rule")

            rule = ISSUE_RULES[issue]
            if rule["refund_source"] == "payment":
                refund = payment_total
            elif rule["refund_source"] == "freight":
                refund = freight_total
            else:
                refund = Decimal("0.00")

            parties = []
            if rule["party_type"] == "seller":
                seller_ids = delivery.get("late_seller_ids", [])
                if not seller_ids:
                    raise ValueError("Seller issue requires a late seller ID")
                parties = [
                    {"party_type": "seller", "party_id": str(seller_id)}
                    for seller_id in seller_ids[:3]
                ]
            elif rule["party_type"]:
                parties = [{"party_type": rule["party_type"], "party_id": rule["party_id"]}]

            output = {
                "case_id": case_id,
                "assessment": {
                    "primary_issue": issue,
                    "case_status": "action_required" if refund > 0 else "no_action",
                    "confidence": 1.0,
                },
                "affected_entities": {
                    "order_ids": list(order.get("order_ids", []))[:5],
                    "item_ids": list(order.get("item_ids", []))[:5],
                    "seller_ids": list(order.get("seller_ids", []))[:5],
                    "payment_ids": list(payment.get("payment_ids", []))[:5],
                },
                "root_cause_analysis": {
                    "ranked_causes": [{"cause_code": rule["cause"], "rank": 1}],
                    "responsible_parties": parties,
                },
                "evidence_ids": self._evidence(order, payment, issue, rule["cause"]),
                "financial_resolution": {
                    "currency": "BRL",
                    "item_total_brl": float(item_total),
                    "freight_total_brl": float(freight_total),
                    "payment_total_brl": float(payment_total),
                    "recommended_refund_brl": float(refund),
                },
                "resolution_actions": [rule["action"]],
            }
            return {
                "agent": self.name,
                "case_id": case_id,
                "status": "success",
                "proposal": output,
                "errors": [],
            }
        except (TypeError, ValueError) as exc:
            return {
                "agent": self.name,
                "case_id": case_id,
                "status": "error",
                "proposal": None,
                "errors": [{"code": "POLICY_NOT_APPLICABLE", "message": str(exc)}],
            }

    @staticmethod
    def _evidence(
        order: dict[str, Any], payment: dict[str, Any], issue: str, cause: str
    ) -> list[str]:
        candidates = list(order.get("evidence_ids", [])) + list(
            payment.get("evidence_ids", [])
        )
        # Seller evidence is useful for seller liability; platform/logistics do not
        # have dataset-backed entity evidence formats in the assignment.
        if issue != "late_delivery_seller":
            candidates = [value for value in candidates if not value.startswith("seller:")]
        candidates.append(f"policy:{cause}")
        return list(dict.fromkeys(str(value) for value in candidates))[:10]
