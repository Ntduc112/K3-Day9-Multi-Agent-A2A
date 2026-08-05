import unittest

from src.agents import DeliveryAgent, PolicyAgent, VerifierAgent


ORDER_ID = "order-1"
SELLER_ID = "seller-1"


def order_facts(status="delivered"):
    return {
        "order_status": status,
        "order_delivered_carrier_date": "2018-01-12 12:00:00",
        "order_delivered_customer_date": "2018-01-22 12:00:00",
        "order_estimated_delivery_date": "2018-01-20 00:00:00",
        "items": [
            {
                "order_item_id": "1",
                "seller_id": SELLER_ID,
                "shipping_limit_date": "2018-01-10 00:00:00",
            }
        ],
        "order_ids": [ORDER_ID],
        "item_ids": [f"{ORDER_ID}:1"],
        "seller_ids": [SELLER_ID],
        "item_total_brl": "100.00",
        "freight_total_brl": "15.00",
        "evidence_ids": [
            f"order:{ORDER_ID}",
            f"item:{ORDER_ID}:1",
            f"seller:{SELLER_ID}",
        ],
    }


def payment_facts(rows=1):
    return {
        "payment_total_brl": "115.00",
        "payment_row_count": rows,
        "is_reconciled": True,
        "payment_ids": [f"{ORDER_ID}:1"],
        "evidence_ids": [f"payment:{ORDER_ID}:1"],
    }


class DeliveryAgentTests(unittest.TestCase):
    def test_detects_late_seller_handoff(self):
        result = DeliveryAgent().run({"case_id": "EC_TEST", "order_facts": order_facts()})
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["facts"]["delivered_late"])
        self.assertTrue(result["facts"]["seller_handoff_late"])
        self.assertEqual(result["facts"]["delay_owner"], "seller")
        self.assertEqual(result["facts"]["late_seller_ids"], [SELLER_ID])

    def test_assigns_late_delivery_to_logistics_when_handoff_was_timely(self):
        facts = order_facts()
        facts["order_delivered_carrier_date"] = "2018-01-09 12:00:00"
        result = DeliveryAgent().run({"case_id": "EC_TEST", "order_facts": facts})
        self.assertEqual(result["facts"]["delay_owner"], "logistics_provider")


class PolicyAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = PolicyAgent()

    def decide(self, order, payment, delivery):
        return self.agent.run(
            {
                "case_id": "EC_TEST",
                "policy_version": "EC_POLICY_V1",
                "order_facts": order,
                "payment_facts": payment,
                "delivery_facts": delivery,
            }
        )

    def test_canceled_has_priority_over_split_payment(self):
        result = self.decide(
            order_facts("canceled"), payment_facts(rows=2), {"delivered_late": True, "seller_handoff_late": True, "late_seller_ids": [SELLER_ID]}
        )
        proposal = result["proposal"]
        self.assertEqual(proposal["assessment"]["primary_issue"], "canceled_order_paid")
        self.assertEqual(proposal["financial_resolution"]["recommended_refund_brl"], 115.0)
        self.assertEqual(proposal["resolution_actions"], ["issue_full_refund"])

    def test_late_seller_refunds_freight(self):
        delivery = DeliveryAgent().run({"case_id": "EC_TEST", "order_facts": order_facts()})
        result = self.decide(order_facts(), payment_facts(), delivery)
        proposal = result["proposal"]
        self.assertEqual(proposal["assessment"]["primary_issue"], "late_delivery_seller")
        self.assertEqual(proposal["financial_resolution"]["recommended_refund_brl"], 15.0)
        self.assertEqual(
            proposal["root_cause_analysis"]["responsible_parties"],
            [{"party_type": "seller", "party_id": SELLER_ID}],
        )

    def test_valid_split_payment_has_no_refund(self):
        order = order_facts()
        order["order_delivered_customer_date"] = "2018-01-18 12:00:00"
        delivery = DeliveryAgent().run({"case_id": "EC_TEST", "order_facts": order})
        proposal = self.decide(order, payment_facts(rows=2), delivery)["proposal"]
        self.assertEqual(proposal["assessment"]["primary_issue"], "valid_split_payment")
        self.assertEqual(proposal["assessment"]["case_status"], "no_action")

    def test_preserves_envelope_entities_and_evidence(self):
        order = order_facts("canceled")
        order_envelope = {
            "status": "success",
            "facts": {
                key: value
                for key, value in order.items()
                if key not in {"order_ids", "item_ids", "seller_ids", "evidence_ids"}
            },
            "order_ids": order["order_ids"],
            "item_ids": order["item_ids"],
            "seller_ids": order["seller_ids"],
            "evidence_ids": order["evidence_ids"],
        }
        payment = payment_facts()
        payment_envelope = {
            "status": "success",
            "facts": {
                key: value
                for key, value in payment.items()
                if key not in {"payment_ids", "evidence_ids"}
            },
            "payment_ids": payment["payment_ids"],
            "evidence_ids": payment["evidence_ids"],
        }
        result = self.decide(order_envelope, payment_envelope, {})
        proposal = result["proposal"]
        self.assertEqual(proposal["affected_entities"]["order_ids"], [ORDER_ID])
        self.assertIn(f"order:{ORDER_ID}", proposal["evidence_ids"])
        self.assertIn(f"payment:{ORDER_ID}:1", proposal["evidence_ids"])


class VerifierAgentTests(unittest.TestCase):
    def valid_proposal(self):
        delivery = DeliveryAgent().run({"case_id": "EC_TEST", "order_facts": order_facts()})
        return PolicyAgent().run(
            {
                "case_id": "EC_TEST",
                "order_facts": order_facts(),
                "payment_facts": payment_facts(),
                "delivery_facts": delivery,
            }
        )["proposal"]

    def test_accepts_consistent_proposal(self):
        result = VerifierAgent(verify_dataset=False).run(
            {"case_id": "EC_TEST", "proposal": self.valid_proposal()}
        )
        self.assertTrue(result["valid"], result["errors"])

    def test_rejects_wrong_refund_and_fake_evidence(self):
        proposal = self.valid_proposal()
        proposal["financial_resolution"]["recommended_refund_brl"] = 100.0
        proposal["evidence_ids"].append("tracking:not-supported")
        result = VerifierAgent(verify_dataset=False).run(
            {"case_id": "EC_TEST", "proposal": proposal}
        )
        codes = {error["code"] for error in result["errors"]}
        self.assertIn("INVALID_REFUND", codes)
        self.assertIn("INVALID_EVIDENCE_FORMAT", codes)


if __name__ == "__main__":
    unittest.main()
