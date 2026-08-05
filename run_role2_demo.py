"""
run_role2_demo.py
Demo runner script to test Role 2 (Order & Seller Agent).
Usage:
  python run_role2_demo.py           # Default runs EC_001.json
  python run_role2_demo.py 2         # Runs EC_002.json
  python run_role2_demo.py EC_015    # Runs EC_015.json
"""

import os
import sys
import json
from src.data_store import DataStore
from src.agents.order_seller_agent import OrderSellerAgent


def main():
    target_case = "1"
    if len(sys.argv) > 1:
        target_case = sys.argv[1].strip()

    # Normalize filename
    if target_case.isdigit():
        target_case = f"EC_{int(target_case):03d}.json"
    elif not target_case.endswith(".json"):
        target_case = f"{target_case}.json"

    file_path = os.path.join("input", target_case)
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist!")
        return

    print("=== Loading DataStore (CSV files) ===")
    store = DataStore.get_instance(data_dir="data")
    print(f"Loaded {len(store.orders)} orders, {len(store.order_items)} order item sets, {len(store.sellers)} sellers.")

    print(f"\n=== Reading {file_path} ===")
    with open(file_path, "r", encoding="utf-8") as f:
        input_data = json.load(f)

    case_id = input_data["case_id"]
    claimed_order_id = input_data["customer_request"]["claimed_order_id"]
    print(f"Case ID: {case_id}")
    print(f"Claimed Order ID: {claimed_order_id}")

    print(f"\n=== Running OrderSellerAgent for {case_id} ===")
    agent = OrderSellerAgent(data_store=store)
    response = agent.process(case_id=case_id, claimed_order_id=claimed_order_id)

    print("\n=== Response JSON ===")
    print(json.dumps(response, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
