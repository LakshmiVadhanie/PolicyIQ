"""
PolicyIQ — Supervisor Agent
Routes incoming queries to specialist agents based on detected intent.
Uses Vertex AI Gemini (or mock LLM in dev mode).
"""

import json
from typing import Literal

from app.agents.state import PolicyIQState
from app.config import settings
from app.tools.bigquery_tools import log_agent_routing


#  System Prompt 

SUPERVISOR_SYSTEM_PROMPT = """You are the PolicyIQ Supervisor Agent — an expert insurance query router.

Your ONLY job is to analyze the user's query and classify it into exactly one of these intents:
- PolicyLookup: Questions about policy details, coverage, renewal, terms, or limits
- ClaimsTriage: Questions about filing claims, claim status, claim history, or incidents
- PremiumEstimation: Questions about pricing, cost estimation, premium calculation, or quotes

Return a JSON object with these exact fields:
{
  "intent": "<PolicyLookup|ClaimsTriage|PremiumEstimation>",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<brief explanation of why you chose this intent>",
  "extracted_entities": {
    "policy_number": "<if mentioned, else null>",
    "claim_id": "<if mentioned, else null>",
    "coverage_type": "<if mentioned, else null>",
    "insurance_type": "<auto|home|health|life|other|null>"
  }
}

Return ONLY the JSON object, nothing else.
"""


def _get_llm():
    """Get LLM instance — Vertex AI Gemini or mock."""
    if settings.use_mock_llm:
        return _MockSupervisorLLM()
    from langchain_google_vertexai import ChatVertexAI
    return ChatVertexAI(
        model_name=settings.supervisor_model,
        project=settings.gcp_project_id,
        location=settings.gcp_location,
        temperature=0.1,
        max_tokens=512,
    )


#  Mock LLM for dev 

class _MockSupervisorLLM:
    """Mock supervisor that does keyword-based intent classification."""

    def invoke(self, messages: list) -> object:
        from langchain_core.messages import HumanMessage as HM
        user_msg = ""
        for m in messages:
            if isinstance(m, HM):
                user_msg = m.content
                break
            elif isinstance(m, dict) and m.get("role") == "user":
                user_msg = m.get("content", "")
                break

        query = user_msg.lower()

        if any(kw in query for kw in ["claim", "incident", "accident", "damage", "triage", "file", "filed"]):
            intent = "ClaimsTriage"
            confidence = 0.92
        elif any(kw in query for kw in ["premium", "price", "cost", "quote", "estimate", "pay", "rate"]):
            intent = "PremiumEstimation"
            confidence = 0.89
        else:
            intent = "PolicyLookup"
            confidence = 0.85

        result = {
            "intent": intent,
            "confidence": confidence,
            "reasoning": f"Keyword-based mock classification for query: '{user_msg[:50]}...'",
            "extracted_entities": {
                "policy_number": next((w for w in query.split() if w.startswith("pol-")), None),
                "claim_id": next((w for w in query.split() if w.startswith("clm-")), None),
                "coverage_type": None,
                "insurance_type": next(
                    (t for t in ["auto", "home", "health", "life"] if t in query), None
                ),
            },
        }

        class MockResponse:
            content = json.dumps(result)

        return MockResponse()


#  Supervisor Node 

def supervisor_node(state: PolicyIQState) -> PolicyIQState:
    """
    LangGraph node: Classifies query intent and routes to specialist agent.
    Updates state with intent, confidence, and extracted entities.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = _get_llm()
    messages = [
        SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
        HumanMessage(content=state["query"]),
    ]

    response = llm.invoke(messages)

    try:
        parsed = json.loads(response.content)
    except json.JSONDecodeError:
        # Fallback: default to PolicyLookup
        parsed = {
            "intent": "PolicyLookup",
            "confidence": 0.5,
            "reasoning": "Failed to parse supervisor response, defaulting to PolicyLookup",
            "extracted_entities": {},
        }

    intent = parsed["intent"]
    confidence = parsed["confidence"]

    # Log routing decision
    log_agent_routing(
        request_id=state["request_id"],
        session_id=state["session_id"],
        intent=intent,
        routed_agent=f"{intent.lower()}_agent",
        confidence=confidence,
        iteration=state.get("iteration", 0),
    )

    return {
        **state,
        "intent": intent,
        "confidence": confidence,
        "supervisor_reasoning": parsed.get("reasoning", ""),
        "extracted_entities": parsed.get("extracted_entities", {}),
        "agent_steps": state.get("agent_steps", []) + [{
            "agent": "supervisor",
            "confidence": confidence,
            "reasoning": parsed.get("reasoning", ""),
        }],
    }


def route_to_agent(state: PolicyIQState) -> Literal["policy_agent", "claims_agent", "premium_agent"]:
    """
    LangGraph conditional edge: determines which specialist agent to call.
    """
    intent = state.get("intent", "PolicyLookup")
    routing_map = {
        "PolicyLookup": "policy_agent",
        "ClaimsTriage": "claims_agent",
        "PremiumEstimation": "premium_agent",
    }
    return routing_map.get(intent, "policy_agent")
