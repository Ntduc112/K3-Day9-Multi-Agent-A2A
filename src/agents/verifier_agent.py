"""Independent output verifier for schema, policy consistency and evidence IDs."""

from __future__ import annotations

import csv
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from src.policy import CAUSES, ISSUE_RULES

CENT = Decimal("0.01")
EVIDENCE_PATTERN = re.compile(
    r"^(order:[^:]+|item:[^:]+:[^:]+|payment:[^:]+:[^:]+|seller:[^:]+|policy:[A-Z_]+)$"
)


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return None


class EvidenceIndex:
    """Load only IDs required for evidence verification."""

    def __init__(self, data_dir: str | Path = "data") -> None:
        data_dir = Path(data_dir)
        self.orders = self._column(data_dir / "olist_orders_dataset.csv", "order_id")
        self.sellers = self._column(data_dir / "olist_sellers_dataset.csv", "seller_id")
        self.items = self._pairs(
            data_dir / "olist_order_items_dataset.csv", "order_id", "order_item_id"
        )
        self.payments = self._pairs(
            data_dir / "olist_order_payments_dataset.csv", "order_id", "payment_sequential"
        )

    @staticmethod
    def _column(path: Path, column: str) -> set[str]:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return {row[column] for row in csv.DictReader(handle)}

    @staticmethod
    def _pairs(path: Path, first: str, second: str) -> set[tuple[str, str]]:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return {(row[first], row[second]) for row in csv.DictReader(handle)}

    def contains(self, evidence_id: str) -> bool:
        parts = evidence_id.split(":")
        if parts[0] == "order" and len(parts) == 2:
            return parts[1] in self.orders
        if parts[0] == "seller" and len(parts) == 2:
            return parts[1] in self.sellers
        if parts[0] == "item" and len(parts) == 3:
            return (parts[1], parts[2]) in self.items
        if parts[0] == "payment" and len(parts) == 3:
            return (parts[1], parts[2]) in self.payments
        if parts[0] == "policy" and len(parts) == 2:
            return parts[1] in CAUSES
        return False


class VerifierAgent:
    """Return structured errors instead of mutating a proposed resolution."""

    name = "verifier_agent"

    def __init__(self, data_dir: str | Path = "data", verify_dataset: bool = True) -> None:
        self.index = EvidenceIndex(data_dir) if verify_dataset else None

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        case_id = request.get("case_id")
        proposal = request.get("proposal", request.get("output"))
        errors: list[dict[str, Any]] = []
        if not isinstance(proposal, dict):
            errors.append(self._error("MISSING_PROPOSAL", "$", "Output must be an object"))
            return self._result(case_id, errors)

        self._required_fields(proposal, errors)
        if errors:
            return self._result(case_id, errors)

        if proposal.get("case_id") != case_id:
            errors.append(self._error("CASE_ID_MISMATCH", "case_id", case_id, proposal.get("case_id")))

        assessment = proposal["assessment"]
        entities = proposal["affected_entities"]
        root = proposal["root_cause_analysis"]
        finance = proposal["financial_resolution"]
        issue = assessment.get("primary_issue")

        if issue not in ISSUE_RULES:
            errors.append(self._error("INVALID_ISSUE", "assessment.primary_issue", "known issue", issue))
        else:
            self._policy_consistency(issue, assessment, root, finance, proposal, errors)

        confidence = assessment.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
            errors.append(self._error("INVALID_CONFIDENCE", "assessment.confidence", "0..1", confidence))

        limits = {
            "order_ids": 5,
            "item_ids": 5,
            "seller_ids": 5,
            "payment_ids": 5,
        }
        for field, limit in limits.items():
            value = entities.get(field)
            if not isinstance(value, list) or len(value) > limit:
                errors.append(self._error("ENTITY_LIMIT", f"affected_entities.{field}", f"list <= {limit}", value))

        if len(root.get("ranked_causes", [])) > 3:
            errors.append(self._error("CAUSE_LIMIT", "root_cause_analysis.ranked_causes", "<= 3"))
        if len(root.get("responsible_parties", [])) > 3:
            errors.append(self._error("PARTY_LIMIT", "root_cause_analysis.responsible_parties", "<= 3"))
        if len(proposal.get("resolution_actions", [])) > 5:
            errors.append(self._error("ACTION_LIMIT", "resolution_actions", "<= 5"))

        evidence = proposal.get("evidence_ids")
        if not isinstance(evidence, list) or len(evidence) > 10:
            errors.append(self._error("EVIDENCE_LIMIT", "evidence_ids", "list <= 10", evidence))
        elif len(evidence) != len(set(evidence)):
            errors.append(self._error("DUPLICATE_EVIDENCE", "evidence_ids", "unique IDs"))
        else:
            for evidence_id in evidence:
                if not isinstance(evidence_id, str) or not EVIDENCE_PATTERN.fullmatch(evidence_id):
                    errors.append(self._error("INVALID_EVIDENCE_FORMAT", "evidence_ids", "valid evidence ID", evidence_id))
                elif self.index is not None and not self.index.contains(evidence_id):
                    errors.append(self._error("UNKNOWN_EVIDENCE", "evidence_ids", "dataset-backed ID", evidence_id))

        if finance.get("currency") != "BRL":
            errors.append(self._error("INVALID_CURRENCY", "financial_resolution.currency", "BRL", finance.get("currency")))
        for field in (
            "item_total_brl",
            "freight_total_brl",
            "payment_total_brl",
            "recommended_refund_brl",
        ):
            money = _decimal(finance.get(field))
            if money is None or money < 0:
                errors.append(self._error("INVALID_MONEY", f"financial_resolution.{field}", "non-negative money", finance.get(field)))

        return self._result(case_id, errors)

    def _policy_consistency(self, issue, assessment, root, finance, proposal, errors) -> None:
        rule = ISSUE_RULES[issue]
        causes = root.get("ranked_causes", [])
        actual_cause = causes[0].get("cause_code") if causes else None
        if actual_cause != rule["cause"]:
            errors.append(self._error("INVALID_ROOT_CAUSE", "root_cause_analysis.ranked_causes", rule["cause"], actual_cause))

        expected_refund = Decimal("0.00")
        if rule["refund_source"] == "payment":
            expected_refund = _decimal(finance.get("payment_total_brl"))
        elif rule["refund_source"] == "freight":
            expected_refund = _decimal(finance.get("freight_total_brl"))
        actual_refund = _decimal(finance.get("recommended_refund_brl"))
        if expected_refund is not None and actual_refund != expected_refund:
            errors.append(self._error("INVALID_REFUND", "financial_resolution.recommended_refund_brl", float(expected_refund), finance.get("recommended_refund_brl")))

        expected_status = "action_required" if expected_refund and expected_refund > 0 else "no_action"
        if assessment.get("case_status") != expected_status:
            errors.append(self._error("INVALID_CASE_STATUS", "assessment.case_status", expected_status, assessment.get("case_status")))
        if proposal.get("resolution_actions") != [rule["action"]]:
            errors.append(self._error("INVALID_ACTION", "resolution_actions", [rule["action"]], proposal.get("resolution_actions")))

        parties = root.get("responsible_parties", [])
        if rule["party_type"] is None and parties:
            errors.append(self._error("UNEXPECTED_PARTY", "root_cause_analysis.responsible_parties", [], parties))
        elif rule["party_type"] and not parties:
            errors.append(self._error("MISSING_PARTY", "root_cause_analysis.responsible_parties", rule["party_type"], parties))
        elif parties and any(p.get("party_type") != rule["party_type"] for p in parties):
            errors.append(self._error("INVALID_PARTY_TYPE", "root_cause_analysis.responsible_parties", rule["party_type"], parties))
        elif parties and rule["party_id"] and any(p.get("party_id") != rule["party_id"] for p in parties):
            errors.append(self._error("INVALID_PARTY_ID", "root_cause_analysis.responsible_parties", rule["party_id"], parties))

    @staticmethod
    def _required_fields(proposal: dict[str, Any], errors: list[dict[str, Any]]) -> None:
        required = {
            "case_id": str,
            "assessment": dict,
            "affected_entities": dict,
            "root_cause_analysis": dict,
            "evidence_ids": list,
            "financial_resolution": dict,
            "resolution_actions": list,
        }
        for field, expected_type in required.items():
            if not isinstance(proposal.get(field), expected_type):
                errors.append(VerifierAgent._error("MISSING_OR_INVALID_FIELD", field, expected_type.__name__, type(proposal.get(field)).__name__))

    @staticmethod
    def _error(code: str, field: str, expected: Any, actual: Any = None) -> dict[str, Any]:
        return {"code": code, "field": field, "expected": expected, "actual": actual}

    def _result(self, case_id: str | None, errors: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "agent": self.name,
            "case_id": case_id,
            "status": "success" if not errors else "error",
            "valid": not errors,
            "errors": errors,
        }
