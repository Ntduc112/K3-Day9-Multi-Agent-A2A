"""EC_POLICY_V1 constants shared by the policy and verifier agents."""

POLICY_VERSION = "EC_POLICY_V1"
PLATFORM_ID = "OLIST_PLATFORM"
LOGISTICS_PROVIDER_ID = "LOGISTICS_PROVIDER"

ISSUE_RULES = {
    "canceled_order_paid": {
        "cause": "ORDER_CANCELED_AFTER_PAYMENT",
        "party_type": "platform",
        "party_id": PLATFORM_ID,
        "action": "issue_full_refund",
        "refund_source": "payment",
    },
    "unavailable_order_paid": {
        "cause": "ORDER_UNAVAILABLE_AFTER_PAYMENT",
        "party_type": "platform",
        "party_id": PLATFORM_ID,
        "action": "issue_full_refund",
        "refund_source": "payment",
    },
    "late_delivery_seller": {
        "cause": "SELLER_HANDOFF_AFTER_LIMIT",
        "party_type": "seller",
        "party_id": None,
        "action": "refund_freight",
        "refund_source": "freight",
    },
    "late_delivery_logistics": {
        "cause": "CARRIER_DELIVERED_AFTER_ESTIMATE",
        "party_type": "logistics_provider",
        "party_id": LOGISTICS_PROVIDER_ID,
        "action": "refund_freight",
        "refund_source": "freight",
    },
    "valid_split_payment": {
        "cause": "MULTIPLE_PAYMENTS_RECONCILED",
        "party_type": None,
        "party_id": None,
        "action": "explain_valid_split_payment",
        "refund_source": "none",
    },
    "unsupported_late_claim": {
        "cause": "DELIVERY_WITHIN_ESTIMATE",
        "party_type": None,
        "party_id": None,
        "action": "reject_late_refund",
        "refund_source": "none",
    },
}

CAUSES = {rule["cause"] for rule in ISSUE_RULES.values()}
