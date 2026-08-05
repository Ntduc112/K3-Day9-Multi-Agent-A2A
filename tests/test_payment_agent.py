import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.agents import PolicyAgent, VerifierAgent
from src.agents.payment_agent import PaymentAgent, PaymentIndex
from src.agents.verifier_agent import EVIDENCE_PATTERN

ORDER_SINGLE = "order-single"
ORDER_SPLIT = "order-split"
ORDER_TRIPLE = "order-triple"
ORDER_ZERO_VALUE = "order-zero-value"
ORDER_UNSORTED = "order-unsorted"
ORDER_MISMATCH = "order-mismatch"
ORDER_NONE = "order-none"

ROWS = [
    {
        "order_id": ORDER_SINGLE,
        "payment_sequential": "1",
        "payment_type": "credit_card",
        "payment_installments": "8",
        "payment_value": "115.00",
    },
    {
        "order_id": ORDER_SPLIT,
        "payment_sequential": "1",
        "payment_type": "voucher",
        "payment_installments": "1",
        "payment_value": "50.00",
    },
    {
        "order_id": ORDER_SPLIT,
        "payment_sequential": "2",
        "payment_type": "credit_card",
        "payment_installments": "3",
        "payment_value": "65.00",
    },
    {
        "order_id": ORDER_TRIPLE,
        "payment_sequential": "1",
        "payment_type": "voucher",
        "payment_installments": "1",
        "payment_value": "30.00",
    },
    {
        "order_id": ORDER_TRIPLE,
        "payment_sequential": "2",
        "payment_type": "voucher",
        "payment_installments": "1",
        "payment_value": "30.00",
    },
    {
        "order_id": ORDER_TRIPLE,
        "payment_sequential": "3",
        "payment_type": "credit_card",
        "payment_installments": "5",
        "payment_value": "55.00",
    },
    {
        "order_id": ORDER_ZERO_VALUE,
        "payment_sequential": "1",
        "payment_type": "voucher",
        "payment_installments": "1",
        "payment_value": "0.00",
    },
    {
        "order_id": ORDER_ZERO_VALUE,
        "payment_sequential": "2",
        "payment_type": "credit_card",
        "payment_installments": "1",
        "payment_value": "40.00",
    },
    # Written out of sequential order on purpose: sequential "2" appears before "1".
    {
        "order_id": ORDER_UNSORTED,
        "payment_sequential": "2",
        "payment_type": "credit_card",
        "payment_installments": "1",
        "payment_value": "30.00",
    },
    {
        "order_id": ORDER_UNSORTED,
        "payment_sequential": "1",
        "payment_type": "voucher",
        "payment_installments": "1",
        "payment_value": "20.00",
    },
    {
        "order_id": ORDER_MISMATCH,
        "payment_sequential": "1",
        "payment_type": "credit_card",
        "payment_installments": "1",
        "payment_value": "50.00",
    },
]

FIELDNAMES = ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"]


def write_fixture_csv(data_dir: Path) -> None:
    path = data_dir / "olist_order_payments_dataset.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(ROWS)


class PaymentAgentTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data_dir = Path(self._tmp.name)
        write_fixture_csv(self.data_dir)
        self.agent = PaymentAgent(index=PaymentIndex(self.data_dir))

    def request(self, order_id, item_total="100.00", freight_total="15.00"):
        return {
            "case_id": "EC_TEST",
            "order_id": order_id,
            "policy_version": "EC_POLICY_V1",
            "item_total_brl": item_total,
            "freight_total_brl": freight_total,
        }

    def test_single_payment_reconciles(self):
        result = self.agent.run(self.request(ORDER_SINGLE))
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["facts"]["payment_total_brl"], "115.00")
        self.assertEqual(result["facts"]["payment_row_count"], 1)
        self.assertTrue(result["facts"]["is_reconciled"])
        self.assertFalse(result["facts"]["valid_split_payment"])
        self.assertEqual(result["payment_ids"], [f"{ORDER_SINGLE}:1"])
        self.assertEqual(result["evidence_ids"], [f"payment:{ORDER_SINGLE}:1"])

    def test_installments_are_not_multiplied_into_total(self):
        # payment_installments=8 must NOT scale payment_value (115.00 * 8)
        result = self.agent.run(self.request(ORDER_SINGLE))
        self.assertEqual(result["facts"]["payment_total_brl"], "115.00")

    def test_split_payment_reconciles(self):
        result = self.agent.run(self.request(ORDER_SPLIT))
        self.assertEqual(result["facts"]["payment_total_brl"], "115.00")
        self.assertEqual(result["facts"]["payment_row_count"], 2)
        self.assertTrue(result["facts"]["is_reconciled"])
        self.assertTrue(result["facts"]["valid_split_payment"])
        self.assertEqual(result["payment_ids"], [f"{ORDER_SPLIT}:1", f"{ORDER_SPLIT}:2"])
        self.assertEqual(
            result["evidence_ids"], [f"payment:{ORDER_SPLIT}:1", f"payment:{ORDER_SPLIT}:2"]
        )

    def test_three_or_more_payment_rows_is_valid_split_payment(self):
        result = self.agent.run(self.request(ORDER_TRIPLE))
        self.assertEqual(result["facts"]["payment_total_brl"], "115.00")
        self.assertEqual(result["facts"]["payment_row_count"], 3)
        self.assertTrue(result["facts"]["is_reconciled"])
        self.assertTrue(result["facts"]["valid_split_payment"])
        self.assertEqual(
            result["payment_ids"], [f"{ORDER_TRIPLE}:1", f"{ORDER_TRIPLE}:2", f"{ORDER_TRIPLE}:3"]
        )

    def test_zero_value_row_still_counts_toward_row_count_and_total(self):
        result = self.agent.run(self.request(ORDER_ZERO_VALUE, item_total="40.00", freight_total="0.00"))
        self.assertEqual(result["facts"]["payment_total_brl"], "40.00")
        self.assertEqual(result["facts"]["payment_row_count"], 2)
        self.assertTrue(result["facts"]["is_reconciled"])
        self.assertTrue(result["facts"]["valid_split_payment"])
        self.assertEqual(result["payment_ids"], [f"{ORDER_ZERO_VALUE}:1", f"{ORDER_ZERO_VALUE}:2"])

    def test_rows_are_ordered_by_payment_sequential_regardless_of_csv_order(self):
        # Fixture writes sequential "2" before "1" in the CSV file on purpose.
        result = self.agent.run(self.request(ORDER_UNSORTED, item_total="50.00", freight_total="0.00"))
        self.assertEqual(result["facts"]["payment_total_brl"], "50.00")
        self.assertEqual(result["payment_ids"], [f"{ORDER_UNSORTED}:1", f"{ORDER_UNSORTED}:2"])
        self.assertEqual(
            result["evidence_ids"], [f"payment:{ORDER_UNSORTED}:1", f"payment:{ORDER_UNSORTED}:2"]
        )

    def test_mismatched_payment_is_not_reconciled(self):
        # payment_total=50.00 vs expected item+freight=115.00 -> off by far more than 0.10
        result = self.agent.run(self.request(ORDER_MISMATCH))
        self.assertFalse(result["facts"]["is_reconciled"])
        self.assertFalse(result["facts"]["valid_split_payment"])

    def test_tolerance_boundary_of_0_10_still_reconciles(self):
        result = self.agent.run(self.request(ORDER_MISMATCH, item_total="49.90", freight_total="0.00"))
        # |50.00 - 49.90| == 0.10 <= tolerance -> reconciled
        self.assertTrue(result["facts"]["is_reconciled"])

    def test_just_outside_tolerance_is_not_reconciled(self):
        result = self.agent.run(self.request(ORDER_MISMATCH, item_total="49.89", freight_total="0.00"))
        # |50.00 - 49.89| == 0.11 > tolerance -> not reconciled
        self.assertFalse(result["facts"]["is_reconciled"])

    def test_no_payment_rows_is_not_an_error(self):
        result = self.agent.run(self.request(ORDER_NONE, item_total="0.00", freight_total="0.00"))
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["facts"]["payment_total_brl"], "0.00")
        self.assertEqual(result["facts"]["payment_row_count"], 0)
        self.assertEqual(result["payment_ids"], [])
        self.assertEqual(result["evidence_ids"], [])

    def test_missing_order_id_is_an_error(self):
        result = self.agent.run({"case_id": "EC_TEST", "item_total_brl": "0", "freight_total_brl": "0"})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["errors"][0]["code"], "INVALID_PAYMENT_REQUEST")

    def test_evidence_ids_match_verifier_agents_pattern(self):
        # Cross-checked against TV4's VerifierAgent regex so IDs are never rejected downstream.
        result = self.agent.run(self.request(ORDER_TRIPLE))
        self.assertTrue(result["evidence_ids"], "expected at least one evidence id")
        for evidence_id in result["evidence_ids"]:
            self.assertRegex(evidence_id, EVIDENCE_PATTERN)

    def test_index_reads_csv_file_only_once(self):
        open_calls = []
        original_open = Path.open

        def counting_open(path_self, *args, **kwargs):
            if path_self.name == "olist_order_payments_dataset.csv":
                open_calls.append(path_self)
            return original_open(path_self, *args, **kwargs)

        with mock.patch.object(Path, "open", counting_open):
            index = PaymentIndex(self.data_dir)
            index.rows_for(ORDER_SINGLE)
            index.rows_for(ORDER_SPLIT)
            index.rows_for(ORDER_MISMATCH)

        self.assertEqual(len(open_calls), 1)


class PaymentPolicyIntegrationTests(unittest.TestCase):
    """Proves PaymentAgent's envelope plugs directly into TV4's PolicyAgent/VerifierAgent."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        data_dir = Path(self._tmp.name)
        write_fixture_csv(data_dir)
        self.payment_agent = PaymentAgent(index=PaymentIndex(data_dir))

    def test_split_payment_flows_through_policy_and_verifier(self):
        payment_result = self.payment_agent.run(
            {
                "case_id": "EC_TEST",
                "order_id": ORDER_SPLIT,
                "policy_version": "EC_POLICY_V1",
                "item_total_brl": "100.00",
                "freight_total_brl": "15.00",
            }
        )
        order_facts = {
            "order_status": "delivered",
            "order_ids": [ORDER_SPLIT],
            "item_ids": [f"{ORDER_SPLIT}:1"],
            "seller_ids": ["seller-1"],
            "item_total_brl": "100.00",
            "freight_total_brl": "15.00",
            "evidence_ids": [f"order:{ORDER_SPLIT}", f"item:{ORDER_SPLIT}:1", "seller:seller-1"],
        }
        delivery_facts = {
            "delivered_late": False,
            "seller_handoff_late": False,
            "delivered_within_estimate": True,
        }

        proposal = PolicyAgent().run(
            {
                "case_id": "EC_TEST",
                "policy_version": "EC_POLICY_V1",
                "order_facts": order_facts,
                "payment_facts": payment_result,
                "delivery_facts": delivery_facts,
            }
        )["proposal"]

        self.assertEqual(proposal["assessment"]["primary_issue"], "valid_split_payment")
        self.assertEqual(proposal["affected_entities"]["payment_ids"], [f"{ORDER_SPLIT}:1", f"{ORDER_SPLIT}:2"])
        self.assertIn(f"payment:{ORDER_SPLIT}:1", proposal["evidence_ids"])
        self.assertIn(f"payment:{ORDER_SPLIT}:2", proposal["evidence_ids"])

        verified = VerifierAgent(verify_dataset=False).run({"case_id": "EC_TEST", "proposal": proposal})
        self.assertTrue(verified["valid"], verified["errors"])


class PaymentAgentRealDatasetTests(unittest.TestCase):
    """Smoke test against the real Olist CSV and all 50 competition input cases."""

    @classmethod
    def setUpClass(cls):
        repo_root = Path(__file__).resolve().parents[1]
        cls.data_dir = repo_root / "data"
        cls.input_dir = repo_root / "input"
        if not (cls.data_dir / "olist_order_payments_dataset.csv").exists():
            raise unittest.SkipTest("real data/ dataset not present in this checkout")
        cls.agent = PaymentAgent(data_dir=cls.data_dir)

    def test_all_input_cases_resolve_without_error(self):
        input_files = sorted(self.input_dir.glob("EC_*.json"))
        if not input_files:
            self.skipTest("input/EC_*.json not present in this checkout")
        self.assertEqual(len(input_files), 50, "expected exactly 50 input cases")

        for path in input_files:
            case = json.loads(path.read_text(encoding="utf-8"))
            order_id = case["customer_request"]["claimed_order_id"]
            with self.subTest(case_id=case["case_id"]):
                result = self.agent.run(
                    {
                        "case_id": case["case_id"],
                        "order_id": order_id,
                        "policy_version": case["policy_version"],
                        "item_total_brl": "0",
                        "freight_total_brl": "0",
                    }
                )
                self.assertEqual(result["status"], "success")
                self.assertRegex(result["facts"]["payment_total_brl"], r"^\d+\.\d{2}$")
                self.assertEqual(len(result["payment_ids"]), result["facts"]["payment_row_count"])
                self.assertEqual(len(result["evidence_ids"]), result["facts"]["payment_row_count"])


if __name__ == "__main__":
    unittest.main()
