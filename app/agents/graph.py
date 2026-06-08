"""
PolicyIQ — LangGraph Pipeline
Defines the full StateGraph multi-agent pipeline:
  query → supervisor → [policy|claims|premium]_agent → quality_gate → response

The graph includes a confidence-check edge that loops back to the supervisor
if agent confidence is below the configured threshold.
"""

import time
import uuid
from typing import Literal

from langgraph.graph import StateGraph, END

from app.agents.state import PolicyIQState
from app.agents.supervisor import supervisor_node, route_to_agent
from app.agents.policy_agent import policy_agent_node
from app.agents.claims_agent import claims_agent_node
from app.agents.premium_agent import premium_agent_node
from app.evaluation.quality_gate import quality_gate_node
from app.config import settings
from app.tools.bigquery_tools import log_interaction


#  Confidence Router 

def check_confidence(state: PolicyIQState) -> Literal["quality_gate", "supervisor"]:
    """
    Conditional edge: if agent confidence is too low and iterations remain,
    loop back to supervisor for re-routing. Otherwise proceed to quality gate.
    """
    confidence = state.get("confidence", 0.0)
    iteration = state.get("iteration", 0)

    if confidence < settings.confidence_threshold and iteration < settings.max_agent_iterations:
        print(
            f"[Graph] Low confidence ({confidence:.2f}), re-routing. "
            f"Iteration {iteration + 1}/{settings.max_agent_iterations}"
        )
        return "supervisor"

    return "quality_gate"


def increment_iteration(state: PolicyIQState) -> PolicyIQState:
    """Increment the iteration counter on each supervisor revisit."""
    return {**state, "iteration": state.get("iteration", 0) + 1}


#  Graph Builder 

def build_graph() -> StateGraph:
    """
    Constructs and compiles the PolicyIQ LangGraph StateGraph.

    Graph structure:
        START
          
          
      supervisor 
           route_to_agent()                       (low confidence + iterations left)
           policy_agent  check_confidence 
           claims_agent  check_confidence 
           premium_agent  check_confidence 
                                                   (confidence OK or max iterations)
                                                  
                                           quality_gate
                                                  
                                                 END
    """
    graph = StateGraph(PolicyIQState)

    #  Add nodes 
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("policy_agent", policy_agent_node)
    graph.add_node("claims_agent", claims_agent_node)
    graph.add_node("premium_agent", premium_agent_node)
    graph.add_node("quality_gate", quality_gate_node)
    graph.add_node("increment_iteration", increment_iteration)

    #  Entry point 
    graph.set_entry_point("supervisor")

    #  Supervisor → specialist routing 
    graph.add_conditional_edges(
        "supervisor",
        route_to_agent,
        {
            "policy_agent": "policy_agent",
            "claims_agent": "claims_agent",
            "premium_agent": "premium_agent",
        },
    )

    #  Specialist → confidence check 
    for agent in ["policy_agent", "claims_agent", "premium_agent"]:
        graph.add_conditional_edges(
            agent,
            check_confidence,
            {
                "quality_gate": "quality_gate",
                "supervisor": "increment_iteration",
            },
        )

    #  Re-route loop: increment → back to supervisor 
    graph.add_edge("increment_iteration", "supervisor")

    #  Quality gate → END 
    graph.add_edge("quality_gate", END)

    return graph.compile()


#  Compiled graph (singleton) 
_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


#  Public API 

def run_pipeline(
    query: str,
    session_id: str,
    user_id: str | None = None,
    policy_number: str | None = None,
    metadata: dict | None = None,
) -> PolicyIQState:
    """
    Run the full PolicyIQ multi-agent pipeline for a given query.

    Args:
        query: The user's insurance question
        session_id: Session identifier for conversation continuity
        user_id: Optional authenticated user identifier
        policy_number: Optional pre-provided policy number
        metadata: Optional additional metadata

    Returns:
        Final pipeline state with response, evaluation scores, and audit trail
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()

    initial_state: PolicyIQState = {
        "request_id": request_id,
        "session_id": session_id,
        "user_id": user_id,
        "query": query,
        "policy_number": policy_number,
        "metadata": metadata or {},
        "intent": "",
        "confidence": 0.0,
        "supervisor_reasoning": "",
        "extracted_entities": {},
        "iteration": 0,
        "agent_steps": [],
        "retrieved_context": "",
        "raw_response": "",
        "evaluation_scores": None,
        "passed_quality_gate": False,
        "fallback_triggered": False,
        "final_response": "",
        "latency_ms": 0,
    }

    graph = get_graph()
    final_state = graph.invoke(initial_state)

    latency_ms = int((time.time() - start_time) * 1000)
    final_state["latency_ms"] = latency_ms

    # Log to BigQuery
    log_interaction(
        session_id=session_id,
        request_id=request_id,
        user_query=query,
        intent=final_state.get("intent", "Unknown"),
        agent_response=final_state.get("final_response", ""),
        retrieved_context=final_state.get("retrieved_context", ""),
        confidence=final_state.get("confidence", 0.0),
        latency_ms=latency_ms,
    )

    print(f"[Pipeline] Completed in {latency_ms}ms | intent={final_state.get('intent')} | "
          f"confidence={final_state.get('confidence', 0):.2f} | "
          f"gate={'' if final_state.get('passed_quality_gate') else ''}")

    return final_state
