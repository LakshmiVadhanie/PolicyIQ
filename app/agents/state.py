"""
PolicyIQ — LangGraph Agent State
Defines the typed state object passed between all graph nodes.
"""

from typing import Any, Optional
from typing_extensions import TypedDict


class PolicyIQState(TypedDict, total=False):
    """
    Shared state for the PolicyIQ LangGraph multi-agent pipeline.
    Flows through supervisor → specialist agent → quality gate → response.
    """

    #  Request identifiers 
    request_id: str          # Unique ID for this request
    session_id: str          # User session ID (for multi-turn context)
    user_id: Optional[str]   # Optional authenticated user ID

    #  Input 
    query: str               # Original user query text
    policy_number: Optional[str]   # Extracted or provided policy number
    metadata: dict[str, Any]       # Additional metadata from the request

    #  Routing / Supervisor 
    intent: str              # Classified intent (PolicyLookup|ClaimsTriage|PremiumEstimation)
    confidence: float        # Supervisor's routing confidence
    supervisor_reasoning: str
    extracted_entities: dict[str, Any]  # Named entities from query

    #  Agent Execution 
    iteration: int           # Current iteration count (for loop detection)
    agent_steps: list[dict]  # Audit trail of all agent invocations
    retrieved_context: str   # Context retrieved/used by specialist agent
    raw_response: str        # Raw LLM output from specialist agent

    #  Quality Gate 
    evaluation_scores: Optional[dict]   # RAGAS scores
    passed_quality_gate: bool           # Whether response cleared the gate
    fallback_triggered: bool            # Whether fallback response was used

    #  Final Output 
    final_response: str      # Response sent to user
    latency_ms: int          # Total pipeline latency
