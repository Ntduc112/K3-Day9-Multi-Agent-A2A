"""
src/data_store.py
In-memory data store for Olist dataset CSV files.
"""

import os
import csv
from typing import Dict, List, Optional, Any


class DataStore:
    """
    DataStore loads Olist CSV files into memory once and provides
    fast O(1) indexed lookups for orders, items, and sellers.
    """
    _instance: Optional['DataStore'] = None

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.orders: Dict[str, Dict[str, str]] = {}
        self.order_items: Dict[str, List[Dict[str, str]]] = {}
        self.sellers: Dict[str, Dict[str, str]] = {}
        self._is_loaded = False

    @classmethod
    def get_instance(cls, data_dir: str = "data") -> 'DataStore':
        if cls._instance is None:
            cls._instance = cls(data_dir=data_dir)
            cls._instance.load_all()
        return cls._instance

    def load_all(self) -> None:
        if self._is_loaded:
            return

        orders_path = os.path.join(self.data_dir, "olist_orders_dataset.csv")
        items_path = os.path.join(self.data_dir, "olist_order_items_dataset.csv")
        sellers_path = os.path.join(self.data_dir, "olist_sellers_dataset.csv")

        # Load Orders
        if os.path.exists(orders_path):
            with open(orders_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    order_id = row["order_id"].strip('"').strip()
                    self.orders[order_id] = {k: v.strip('"').strip() if v else "" for k, v in row.items()}

        # Load Order Items
        if os.path.exists(items_path):
            with open(items_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    order_id = row["order_id"].strip('"').strip()
                    cleaned_row = {k: v.strip('"').strip() if v else "" for k, v in row.items()}
                    if order_id not in self.order_items:
                        self.order_items[order_id] = []
                    self.order_items[order_id].append(cleaned_row)

        # Load Sellers
        if os.path.exists(sellers_path):
            with open(sellers_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    seller_id = row["seller_id"].strip('"').strip()
                    self.sellers[seller_id] = {k: v.strip('"').strip() if v else "" for k, v in row.items()}

        self._is_loaded = True

    def get_order(self, order_id: str) -> Optional[Dict[str, str]]:
        return self.orders.get(order_id)

    def get_order_items(self, order_id: str) -> List[Dict[str, str]]:
        return self.order_items.get(order_id, [])

    def get_seller(self, seller_id: str) -> Optional[Dict[str, str]]:
        return self.sellers.get(seller_id)
