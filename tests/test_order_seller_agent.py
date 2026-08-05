"""
tests/test_order_seller_agent.py
Unit tests for OrderSellerAgent and DataStore.
"""

import unittest
from src.data_store import DataStore
from src.agents.order_seller_agent import OrderSellerAgent


class TestOrderSellerAgent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.data_store = DataStore.get_instance(data_dir="data")
        cls.agent = OrderSellerAgent(data_store=cls.data_store)

    def test_process_valid_order_ec001(self):
        case_id = "EC_001"
        claimed_order_id = "e2a03ccf5ea816036608b2d8c3ab8e60"
        
        response = self.agent.process(case_id=case_id, claimed_order_id=claimed_order_id)
        
        self.assertEqual(response["status"], "success")
        self.assertEqual(response["case_id"], case_id)
        
        facts = response["facts"]
        self.assertEqual(facts["order_id"], claimed_order_id)
        self.assertIn("item_total_brl", facts)
        self.assertIn("freight_total_brl", facts)
        
        # Verify decimal precision format (e.g. 0.00)
        self.assertRegex(facts["item_total_brl"], r"^\d+\.\d{2}$")
        self.assertRegex(facts["freight_total_brl"], r"^\d+\.\d{2}$")
        
        # Verify entity_ids structure
        entity_ids = response["entity_ids"]
        self.assertIn(claimed_order_id, entity_ids["order_ids"])
        
        # Verify evidence_ids formatting
        evidence_ids = response["evidence_ids"]
        self.assertIn(f"order:{claimed_order_id}", evidence_ids)
        for item_id in entity_ids["item_ids"]:
            self.assertIn(f"item:{item_id}", evidence_ids)
        for seller_id in entity_ids["seller_ids"]:
            self.assertIn(f"seller:{seller_id}", evidence_ids)

    def test_process_non_existent_order(self):
        case_id = "EC_999"
        claimed_order_id = "non_existent_order_id_12345"
        
        response = self.agent.process(case_id=case_id, claimed_order_id=claimed_order_id)
        
        self.assertEqual(response["status"], "error")
        self.assertTrue(len(response["errors"]) > 0)


if __name__ == "__main__":
    unittest.main()
