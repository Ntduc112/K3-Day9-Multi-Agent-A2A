import os
import sys
import json
import time
import re

if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(100000)

from typing import Dict, Any, List, Optional
from src.trace import TraceLogger
from src.llm import call_llm

# Import real specialist agents
from src.agents.order_seller_agent import OrderSellerAgent
from src.agents.payment_agent import PaymentAgent
from src.agents.delivery_agent import DeliveryAgent
from src.agents.policy_agent import PolicyAgent
from src.agents.verifier_agent import VerifierAgent

class Coordinator:
    """Orchestrates the multi-agent pipeline dynamically using an LLM Supervisor."""
    
    def __init__(self, data_dir: str = "data", verify_dataset: bool = True):
        self.order_seller_agent = OrderSellerAgent()
        self.payment_agent = PaymentAgent(data_dir=data_dir)
        self.delivery_agent = DeliveryAgent()
        self.policy_agent = PolicyAgent()
        self.verifier_agent = VerifierAgent(data_dir=data_dir, verify_dataset=verify_dataset)

    def run_case(self, case_input: Dict[str, Any], logger: TraceLogger) -> Dict[str, Any]:
        """Runs a single dispute case dynamically using LLM coordination, with a deterministic fallback."""
        case_id = case_input.get("case_id", "")
        policy_version = case_input.get("policy_version", "EC_POLICY_V1")
        customer_req = case_input.get("customer_request", {})
        claimed_order_id = customer_req.get("claimed_order_id", "")

        # Default fallback structure
        fallback_resolution = {
            "case_id": case_id,
            "assessment": {
                "primary_issue": "unsupported_late_claim",
                "case_status": "no_action",
                "confidence": 0.0
            },
            "affected_entities": {
                "order_ids": [claimed_order_id] if claimed_order_id else [],
                "item_ids": [],
                "seller_ids": [],
                "payment_ids": []
            },
            "root_cause_analysis": {
                "ranked_causes": [],
                "responsible_parties": []
            },
            "evidence_ids": [],
            "financial_resolution": {
                "currency": "BRL",
                "item_total_brl": 0.0,
                "freight_total_brl": 0.0,
                "payment_total_brl": 0.0,
                "recommended_refund_brl": 0.0
            },
            "resolution_actions": ["reject_late_refund"]
        }

        # Track what agents have run and their outputs
        agent_responses = {}
        history = []
        proposal = None
        max_iterations = 8
        iteration = 0
        llm_failed = False

        # Define supervisor instructions
        supervisor_system_prompt = """You are the Supervisor Agent in an E-commerce Dispute Resolution Multi-Agent system.
Your job is to orchestrate the resolution of customer disputes dynamically by triggering the correct specialist agents (tools) in sequence.

You have access to the following 5 specialist agents (tools):
1. 'order_seller_agent': Retrieves order details, item totals, freight values, and checks seller delay. Needs no parameters.
2. 'payment_agent': Reconciles payments. Requires parameters: 'item_total_brl', 'freight_total_brl' (values gathered from order_seller_agent).
3. 'delivery_agent': Analyzes delivery lateness (carrier vs seller). Needs no parameters.
4. 'policy_agent': Generates the resolution proposal. Runs once you have gathered facts from order_seller, payment, and delivery agents.
5. 'verifier_agent': Verifies the final resolution proposal for format and evidence validity.

Workflow Guidelines:
- You must call order_seller_agent first to get the financial baselines.
- Call payment_agent and delivery_agent next. Note that payment_agent requires 'item_total_brl' and 'freight_total_brl' as parameters.
- Call policy_agent to get a proposal.
- Call verifier_agent to verify the proposal.
- If verifier_agent confirms the proposal is valid, return next_action = 'finish'.
- If verifier_agent finds errors, explain how to resolve them or output 'finish' with the best fallback.

You must respond ONLY with a JSON object in this format:
{
  "thought": "Your reasoning about the current case state and what agent to run next.",
  "next_action": "order_seller_agent" | "payment_agent" | "delivery_agent" | "policy_agent" | "verifier_agent" | "finish",
  "action_input": { ... key-value parameters if calling payment_agent ... }
}
"""

        # Dynamic loop orchestrated by LLM
        while iteration < max_iterations:
            iteration += 1
            
            # Format current state for LLM
            state_summary = {
                "case_id": case_id,
                "claimed_order_id": claimed_order_id,
                "policy_version": policy_version,
                "history_steps_taken": history,
                "agents_run_so_far": list(agent_responses.keys())
            }
            
            # Retrieve financials if OrderSeller ran
            if "order_seller_agent" in agent_responses:
                os_facts = agent_responses["order_seller_agent"].get("facts", {})
                state_summary["item_total_brl"] = os_facts.get("item_total_brl", "0.00")
                state_summary["freight_total_brl"] = os_facts.get("freight_total_brl", "0.00")

            user_prompt = f"Current Case State:\n{json.dumps(state_summary, indent=2)}\n\nWhat is your next action?"

            try:
                # Minimal pause for smooth network streaming
                time.sleep(0.05)
                # Ask LLM Coordinator for next step
                llm_response_text = call_llm(supervisor_system_prompt, user_prompt)
                
                decision = None
                try:
                    decision = json.loads(llm_response_text)
                except Exception:
                    pass

                # If LLM returned a float/str or text wrapped JSON, extract {...} with regex
                if not isinstance(decision, dict):
                    match = re.search(r"\{.*\}", llm_response_text, re.DOTALL)
                    if match:
                        try:
                            decision = json.loads(match.group(0))
                        except Exception:
                            pass

                # If still not a dict (e.g. LLM output "1.0"), retry once with explicit reminder
                if not isinstance(decision, dict):
                    reminder = user_prompt + "\n\nCRITICAL: Your previous response was NOT a JSON object. You MUST return ONLY a JSON dictionary: {\"thought\": \"...\", \"next_action\": \"...\"}"
                    llm_response_text = call_llm(supervisor_system_prompt, reminder)
                    try:
                        decision = json.loads(llm_response_text)
                    except Exception:
                        match = re.search(r"\{.*\}", llm_response_text, re.DOTALL)
                        if match:
                            try:
                                decision = json.loads(match.group(0))
                            except Exception:
                                pass

                if not isinstance(decision, dict):
                    raise ValueError(f"Expected JSON object, got: {type(decision).__name__}")
                
                thought = decision.get("thought", "")
                next_action = decision.get("next_action")
                action_input = decision.get("action_input", {})
                
                history.append(f"Thought: {thought} | Next Action: {next_action}")
            except Exception as e:
                # If LLM fails or fails parsing, trigger fallback
                print(f"LLM Supervisor failed at iteration {iteration}: {str(e)}. Triggering deterministic fallback.")
                llm_failed = True
                break

            if next_action == "finish":
                break

            # Execute the chosen agent
            try:
                if next_action == "order_seller_agent":
                    logger.log_handoff(case_id, "coordinator", "order_seller_agent", "started")
                    res = self.order_seller_agent.process(case_id, claimed_order_id)
                    agent_responses["order_seller_agent"] = res
                    logger.log_handoff(case_id, "order_seller_agent", "coordinator", res.get("status", "success"))
                    history.append(f"Result from order_seller_agent: status={res.get('status')}")
                    
                elif next_action == "payment_agent":
                    item_total = action_input.get("item_total_brl")
                    freight_total = action_input.get("freight_total_brl")
                    # Fallback to state if LLM failed to pass inputs
                    if not item_total or not freight_total:
                        os_facts = agent_responses.get("order_seller_agent", {}).get("facts", {})
                        item_total = os_facts.get("item_total_brl", "0.00")
                        freight_total = os_facts.get("freight_total_brl", "0.00")

                    logger.log_handoff(case_id, "coordinator", "payment_agent", "started")
                    req = {
                        "case_id": case_id,
                        "order_id": claimed_order_id,
                        "item_total_brl": item_total,
                        "freight_total_brl": freight_total
                    }
                    res = self.payment_agent.run(req)
                    agent_responses["payment_agent"] = res
                    logger.log_handoff(case_id, "payment_agent", "coordinator", res.get("status", "success"))
                    history.append(f"Result from payment_agent: status={res.get('status')}")
                    
                elif next_action == "delivery_agent":
                    logger.log_handoff(case_id, "coordinator", "delivery_agent", "started")
                    os_facts = agent_responses.get("order_seller_agent", {}).get("facts", {})
                    req = {
                        "case_id": case_id,
                        "facts": os_facts
                    }
                    res = self.delivery_agent.run(req)
                    agent_responses["delivery_agent"] = res
                    logger.log_handoff(case_id, "delivery_agent", "coordinator", res.get("status", "success"))
                    history.append(f"Result from delivery_agent: status={res.get('status')}")
                    
                elif next_action == "policy_agent":
                    logger.log_handoff(case_id, "coordinator", "policy_agent", "started")
                    
                    res_order = agent_responses.get("order_seller_agent", {"facts": {}})
                    # Flatten entity_ids into root of res_order so PolicyAgent extracts correctly
                    if "entity_ids" in res_order:
                        for field_name in ["order_ids", "item_ids", "seller_ids"]:
                            if field_name in res_order["entity_ids"]:
                                res_order[field_name] = res_order["entity_ids"][field_name]
                                
                    req = {
                        "case_id": case_id,
                        "policy_version": policy_version,
                        "order_facts": res_order,
                        "payment_facts": agent_responses.get("payment_agent", {"facts": {}}),
                        "delivery_facts": agent_responses.get("delivery_agent", {"facts": {}})
                    }
                    res = self.policy_agent.run(req)
                    agent_responses["policy_agent"] = res
                    proposal = res.get("proposal")
                    logger.log_handoff(case_id, "policy_agent", "coordinator", res.get("status", "success"))
                    history.append(f"Result from policy_agent: status={res.get('status')} | proposal_issue={proposal.get('assessment', {}).get('primary_issue') if proposal else 'None'}")
                    
                elif next_action == "verifier_agent":
                    logger.log_handoff(case_id, "coordinator", "verifier_agent", "started")
                    req = {
                        "case_id": case_id,
                        "proposal": proposal
                    }
                    res = self.verifier_agent.run(req)
                    agent_responses["verifier_agent"] = res
                    logger.log_handoff(case_id, "verifier_agent", "coordinator", res.get("status", "success"))
                    history.append(f"Result from verifier_agent: valid={res.get('valid')} | errors_count={len(res.get('errors', []))}")
                else:
                    # Invalid action received, trigger fallback
                    print(f"Unknown action: '{next_action}'. Fallback activated.")
                    llm_failed = True
                    break
            except Exception as e:
                print(f"Agent execution of '{next_action}' failed: {str(e)}. Fallback activated.")
                llm_failed = True
                break

        # DETERMINISTIC FALLBACK RUNNER
        # Evaluates what hasn't run yet and runs it sequentially to guarantee completion
        if llm_failed or iteration >= max_iterations:
            print(f"Executing deterministic sequential fallback for case {case_id}...")
            
            # 1. Run OrderSeller
            if "order_seller_agent" not in agent_responses:
                try:
                    logger.log_handoff(case_id, "coordinator", "order_seller_agent", "started")
                    res = self.order_seller_agent.process(case_id, claimed_order_id)
                    agent_responses["order_seller_agent"] = res
                    logger.log_handoff(case_id, "order_seller_agent", "coordinator", res.get("status", "success"))
                except Exception as e:
                    logger.log_handoff(case_id, "order_seller_agent", "coordinator", f"failed: {str(e)}")

            os_facts = agent_responses.get("order_seller_agent", {}).get("facts", {})
            item_total = os_facts.get("item_total_brl", "0.00")
            freight_total = os_facts.get("freight_total_brl", "0.00")

            # 2. Run Payment
            if "payment_agent" not in agent_responses:
                try:
                    logger.log_handoff(case_id, "coordinator", "payment_agent", "started")
                    res = self.payment_agent.run({
                        "case_id": case_id,
                        "order_id": claimed_order_id,
                        "item_total_brl": item_total,
                        "freight_total_brl": freight_total
                    })
                    agent_responses["payment_agent"] = res
                    logger.log_handoff(case_id, "payment_agent", "coordinator", res.get("status", "success"))
                except Exception as e:
                    logger.log_handoff(case_id, "payment_agent", "coordinator", f"failed: {str(e)}")

            # 3. Run Delivery
            if "delivery_agent" not in agent_responses:
                try:
                    logger.log_handoff(case_id, "coordinator", "delivery_agent", "started")
                    res = self.delivery_agent.run({
                        "case_id": case_id,
                        "facts": os_facts
                    })
                    agent_responses["delivery_agent"] = res
                    logger.log_handoff(case_id, "delivery_agent", "coordinator", res.get("status", "success"))
                except Exception as e:
                    logger.log_handoff(case_id, "delivery_agent", "coordinator", f"failed: {str(e)}")

            # 4. Run Policy
            if "policy_agent" not in agent_responses:
                try:
                    logger.log_handoff(case_id, "coordinator", "policy_agent", "started")
                    res_order = agent_responses.get("order_seller_agent", {"facts": {}})
                    if "entity_ids" in res_order:
                        for field_name in ["order_ids", "item_ids", "seller_ids"]:
                            if field_name in res_order["entity_ids"]:
                                res_order[field_name] = res_order["entity_ids"][field_name]

                    res = self.policy_agent.run({
                        "case_id": case_id,
                        "policy_version": policy_version,
                        "order_facts": res_order,
                        "payment_facts": agent_responses.get("payment_agent", {"facts": {}}),
                        "delivery_facts": agent_responses.get("delivery_agent", {"facts": {}})
                    })
                    agent_responses["policy_agent"] = res
                    proposal = res.get("proposal")
                    logger.log_handoff(case_id, "policy_agent", "coordinator", res.get("status", "success"))
                except Exception as e:
                    logger.log_handoff(case_id, "policy_agent", "coordinator", f"failed: {str(e)}")

            # 5. Run Verifier
            if "verifier_agent" not in agent_responses:
                try:
                    logger.log_handoff(case_id, "coordinator", "verifier_agent", "started")
                    res = self.verifier_agent.run({
                        "case_id": case_id,
                        "proposal": proposal
                    })
                    agent_responses["verifier_agent"] = res
                    logger.log_handoff(case_id, "verifier_agent", "coordinator", res.get("status", "success"))
                except Exception as e:
                    logger.log_handoff(case_id, "verifier_agent", "coordinator", f"failed: {str(e)}")

        # Return proposal if gathered, else fallback
        return proposal if proposal else fallback_resolution
