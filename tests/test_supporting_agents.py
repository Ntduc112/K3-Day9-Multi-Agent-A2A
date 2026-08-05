import unittest

from src.agents import (
    ContractAuditAgent,
    InputValidationAgent,
    ResolutionAuditAgent,
)


class SupportingAgentTests(unittest.TestCase):
    def test_input_validation_accepts_readme_case_shape(self):
        result = InputValidationAgent().run({
            "case_id": "EC_TEST",
            "policy_version": "EC_POLICY_V1",
            "customer_request": {"claimed_order_id": "order-1"},
        })
        self.assertTrue(result["facts"]["input_valid"])

    def test_input_validation_rejects_missing_order(self):
        result = InputValidationAgent().run({
            "case_id": "EC_TEST",
            "policy_version": "EC_POLICY_V1",
            "customer_request": {},
        })
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["errors"][0]["code"], "MISSING_ORDER_ID")

    def test_contract_audit_accepts_consistent_handoff(self):
        result = ContractAuditAgent().run({
            "case_id": "EC_TEST",
            "claimed_order_id": "order-1",
            "order_facts": {"facts": {"order_id": "order-1", "order_ids": ["order-1"]}},
            "payment_facts": {"facts": {"payment_row_count": 1}, "payment_ids": ["order-1:1"]},
            "delivery_facts": {"facts": {"delivered_late": False}},
        })
        self.assertTrue(result["valid"], result["errors"])

    def test_contract_audit_accepts_legacy_nested_entity_envelope(self):
        result = ContractAuditAgent().run({
            "claimed_order_id": "order-1",
            "order_facts": {
                "facts": {"order_id": "order-1"},
                "entity_ids": {"order_ids": ["order-1"]},
            },
            "payment_facts": {"facts": {"payment_row_count": 0}},
            "delivery_facts": {"facts": {"delivered_late": False}},
        })
        self.assertTrue(result["valid"], result["errors"])

    def test_contract_audit_rejects_cross_order_payment(self):
        result = ContractAuditAgent().run({
            "claimed_order_id": "order-1",
            "order_facts": {"order_ids": ["order-1"]},
            "payment_facts": {"payment_row_count": 1, "payment_ids": ["order-2:1"]},
            "delivery_facts": {"delivered_late": False},
        })
        self.assertFalse(result["valid"])
        self.assertIn("CROSS_ORDER_PAYMENT", {error["code"] for error in result["errors"]})

    def test_resolution_audit_accepts_no_action_rule(self):
        result = ResolutionAuditAgent().run({
            "proposal": {
                "assessment": {"primary_issue": "valid_split_payment", "case_status": "no_action"},
                "financial_resolution": {"recommended_refund_brl": 0.0},
                "resolution_actions": ["explain_valid_split_payment"],
            }
        })
        self.assertTrue(result["valid"], result["errors"])

    def test_resolution_audit_rejects_wrong_action(self):
        result = ResolutionAuditAgent().run({
            "proposal": {
                "assessment": {"primary_issue": "late_delivery_seller", "case_status": "action_required"},
                "financial_resolution": {"recommended_refund_brl": 15.0},
                "resolution_actions": ["issue_full_refund"],
            }
        })
        self.assertFalse(result["valid"])
        self.assertIn("ACTION_MISMATCH", {error["code"] for error in result["errors"]})


if __name__ == "__main__":
    unittest.main()
