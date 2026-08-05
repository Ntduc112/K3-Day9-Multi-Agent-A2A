from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

@dataclass
class CustomerRequest:
    language: str
    message: str
    claimed_order_id: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CustomerRequest":
        return cls(
            language=data.get("language", ""),
            message=data.get("message", ""),
            claimed_order_id=data.get("claimed_order_id", "")
        )

@dataclass
class CaseInput:
    case_id: str
    opened_at: str
    customer_request: CustomerRequest
    policy_version: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CaseInput":
        return cls(
            case_id=data.get("case_id", ""),
            opened_at=data.get("opened_at", ""),
            customer_request=CustomerRequest.from_dict(data.get("customer_request", {})),
            policy_version=data.get("policy_version", "")
        )

@dataclass
class AgentResponse:
    agent: str
    case_id: str
    status: str            # "success" or "error"
    facts: Dict[str, Any]  # domain-specific data
    evidence_ids: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class DisputeState:
    case_input: CaseInput
    
    # Store individual agent responses
    order_seller_response: Optional[AgentResponse] = None
    payment_response: Optional[AgentResponse] = None
    delivery_response: Optional[AgentResponse] = None
    policy_response: Optional[AgentResponse] = None
    verifier_response: Optional[AgentResponse] = None
    
    # Accumulated outputs
    assessment: Dict[str, Any] = field(default_factory=dict)
    affected_entities: Dict[str, List[str]] = field(default_factory=dict)
    root_cause_analysis: Dict[str, Any] = field(default_factory=dict)
    evidence_ids: List[str] = field(default_factory=list)
    financial_resolution: Dict[str, Any] = field(default_factory=dict)
    resolution_actions: List[str] = field(default_factory=list)

    def to_output_dict(self) -> Dict[str, Any]:
        """Convert state to the output JSON format required by the requirements."""
        return {
            "case_id": self.case_input.case_id,
            "assessment": self.assessment,
            "affected_entities": {
                "order_ids": self.affected_entities.get("order_ids", []),
                "item_ids": self.affected_entities.get("item_ids", []),
                "seller_ids": self.affected_entities.get("seller_ids", []),
                "payment_ids": self.affected_entities.get("payment_ids", [])
            },
            "root_cause_analysis": self.root_cause_analysis,
            "evidence_ids": self.evidence_ids,
            "financial_resolution": self.financial_resolution,
            "resolution_actions": self.resolution_actions
        }
