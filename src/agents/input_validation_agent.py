"""Validate the case envelope before domain agents are called."""

from __future__ import annotations

from typing import Any

from src.policy import POLICY_VERSION


class InputValidationAgent:
    """Check only input-contract requirements; it does not make a policy decision."""

    name = "input_validation_agent"

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        case_id = request.get("case_id")
        customer_request = request.get("customer_request")

        if not isinstance(case_id, str) or not case_id.strip():
            errors.append({"code": "MISSING_CASE_ID", "field": "case_id"})
        if not isinstance(customer_request, dict):
            errors.append({"code": "INVALID_CUSTOMER_REQUEST", "field": "customer_request"})
        else:
            order_id = customer_request.get("claimed_order_id")
            if not isinstance(order_id, str) or not order_id.strip():
                errors.append({"code": "MISSING_ORDER_ID", "field": "customer_request.claimed_order_id"})

        if request.get("policy_version", POLICY_VERSION) != POLICY_VERSION:
            errors.append({"code": "UNSUPPORTED_POLICY", "field": "policy_version"})

        return {
            "agent": self.name,
            "case_id": case_id,
            "status": "success" if not errors else "error",
            "facts": {"input_valid": not errors},
            "errors": errors,
        }
