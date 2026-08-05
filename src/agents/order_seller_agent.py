"""
src/agents/order_seller_agent.py
Order & Seller Agent for retrieving order facts, calculating financial totals,
checking seller handoff deadlines, and producing entity & evidence IDs.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional
from src.data_store import DataStore
from src.contracts import AgentResponse, OrderSellerFacts, OrderItemFact, EntityIDs


class OrderSellerAgent:
    """
    Agent responsible for Order, Items, and Seller domain analysis.
    """

    def __init__(self, data_store: Optional[DataStore] = None):
        self.data_store = data_store or DataStore.get_instance()

    def process(self, case_id: str, claimed_order_id: str) -> AgentResponse:
        order = self.data_store.get_order(claimed_order_id)
        if not order:
            return {
                "agent": "order_seller_agent",
                "case_id": case_id,
                "status": "error",
                "facts": {},
                "entity_ids": {
                    "order_ids": [],
                    "item_ids": [],
                    "seller_ids": [],
                    "payment_ids": []
                },
                "evidence_ids": [],
                "errors": [f"Order '{claimed_order_id}' not found in dataset"]
            }

        items_raw = self.data_store.get_order_items(claimed_order_id)
        
        carrier_date = order.get("order_delivered_carrier_date") or None
        
        item_total = Decimal("0.00")
        freight_total = Decimal("0.00")
        
        item_facts: List[OrderItemFact] = []
        late_sellers_set = set()
        seller_ids_set = set()
        item_ids_list: List[str] = []
        evidence_ids: List[str] = []

        # Order evidence
        evidence_ids.append(f"order:{claimed_order_id}")

        for item in items_raw:
            item_id = item.get("order_item_id", "1")
            price_dec = Decimal(item.get("price", "0.00"))
            freight_dec = Decimal(item.get("freight_value", "0.00"))
            
            item_total += price_dec
            freight_total += freight_dec
            
            seller_id = item.get("seller_id", "")
            shipping_limit = item.get("shipping_limit_date") or None
            
            if seller_id:
                seller_ids_set.add(seller_id)

            # Check if seller delivered late to carrier
            is_seller_late = False
            if carrier_date and shipping_limit:
                if carrier_date > shipping_limit:
                    is_seller_late = True
                    if seller_id:
                        late_sellers_set.add(seller_id)

            formatted_item_id = f"{claimed_order_id}:{item_id}"
            item_ids_list.append(formatted_item_id)
            evidence_ids.append(f"item:{formatted_item_id}")

            item_facts.append({
                "order_item_id": int(item_id) if item_id.isdigit() else 1,
                "product_id": item.get("product_id", ""),
                "seller_id": seller_id,
                "shipping_limit_date": shipping_limit,
                "price": str(price_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "freight_value": str(freight_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "is_seller_late_handoff": is_seller_late
            })

        seller_ids_list = list(seller_ids_set)
        for s_id in seller_ids_list:
            evidence_ids.append(f"seller:{s_id}")

        item_total_str = str(item_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        freight_total_str = str(freight_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

        facts: OrderSellerFacts = {
            "order_id": claimed_order_id,
            "customer_id": order.get("customer_id", ""),
            "order_status": order.get("order_status", ""),
            "order_purchase_timestamp": order.get("order_purchase_timestamp") or None,
            "order_approved_at": order.get("order_approved_at") or None,
            "order_delivered_carrier_date": carrier_date,
            "order_delivered_customer_date": order.get("order_delivered_customer_date") or None,
            "order_estimated_delivery_date": order.get("order_estimated_delivery_date") or None,
            "item_total_brl": item_total_str,
            "freight_total_brl": freight_total_str,
            "items": item_facts,
            "late_sellers": list(late_sellers_set)
        }

        entity_ids: EntityIDs = {
            "order_ids": [claimed_order_id],
            "item_ids": item_ids_list,
            "seller_ids": seller_ids_list,
            "payment_ids": []
        }

        return {
            "agent": "order_seller_agent",
            "case_id": case_id,
            "status": "success",
            "facts": facts,
            "entity_ids": entity_ids,
            "evidence_ids": evidence_ids,
            "errors": []
        }
