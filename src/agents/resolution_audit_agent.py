"""Independent consistency check for the policy proposal."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from src.policy import ISSUE_RULES


class ResolutionAuditAgent:
    """Check issue/action/refund/status relationships before dataset verification."""

    name = "resolution_audit_agent"

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        proposal = request.get("proposal") or {}
        errors: list[dict[str, Any]] = []
        assessment = proposal.get("assessment", {})
        finance = proposal.get("financial_resolution", {})
        issue = assessment.get("primary_issue")
        rule = ISSUE_RULES.get(issue)

        if rule is None:
            errors.append({"code": "UNKNOWN_PRIMARY_ISSUE", "field": "assessment.primary_issue"})
        else:
            expected_action = rule["action"]
            if proposal.get("resolution_actions") != [expected_action]:
                errors.append({"code": "ACTION_MISMATCH", "field": "resolution_actions", "expected": expected_action})
            try:
                refund = Decimal(str(finance.get("recommended_refund_brl", 0)))
            except (InvalidOperation, TypeError, ValueError):
                refund = None
            if refund is None or refund < 0:
                errors.append({"code": "INVALID_REFUND", "field": "financial_resolution.recommended_refund_brl"})
            expected_status = "action_required" if refund is not None and refund > 0 else "no_action"
            if assessment.get("case_status") != expected_status:
                errors.append({"code": "STATUS_MISMATCH", "field": "assessment.case_status", "expected": expected_status})

        return {
            "agent": self.name,
            "case_id": request.get("case_id"),
            "status": "success" if not errors else "error",
            "valid": not errors,
            "errors": errors,
        }
