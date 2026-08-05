"""
src/contracts.py
Standard contracts and data schemas for agent communications.
"""

from typing import TypedDict, List, Optional, Dict, Any, Literal


class CaseRequest(TypedDict):
    case_id: str
    claimed_order_id: str
    policy_version: str


class OrderItemFact(TypedDict):
    order_item_id: int
    product_id: str
    seller_id: str
    shipping_limit_date: Optional[str]
    price: str
    freight_value: str
    is_seller_late_handoff: bool


class OrderSellerFacts(TypedDict):
    order_id: str
    customer_id: str
    order_status: str
    order_purchase_timestamp: Optional[str]
    order_approved_at: Optional[str]
    order_delivered_carrier_date: Optional[str]
    order_delivered_customer_date: Optional[str]
    order_estimated_delivery_date: Optional[str]
    item_total_brl: str
    freight_total_brl: str
    items: List[OrderItemFact]
    late_sellers: List[str]


class EntityIDs(TypedDict):
    order_ids: List[str]
    item_ids: List[str]
    seller_ids: List[str]
    payment_ids: List[str]


class AgentResponse(TypedDict):
    agent: str
    case_id: str
    status: Literal["success", "error"]
    facts: Dict[str, Any]
    entity_ids: EntityIDs
    evidence_ids: List[str]
    errors: List[str]
