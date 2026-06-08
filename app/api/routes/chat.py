"""
PolicyIQ — Chat Route
Direct chat endpoint for testing and integrations.
"""

import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from app.api.models import (
    ChatRequest,
    ChatResponse,
    AgentStep,
    EvaluationScores,
    IntentType,
    AgentName,
    MetricsResponse,
)
from app.agents.graph import run_pipeline
from app.tools.bigquery_tools import get_aggregate_metrics

router = APIRouter()


@router.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Direct chat endpoint — runs the full PolicyIQ multi-agent pipeline.

    Submit an insurance query and receive a structured response with:
    - Detected intent (PolicyLookup | ClaimsTriage | PremiumEstimation)
    - Agent response
    - Confidence score
    - Full agent execution chain audit trail
    - RAGAS quality evaluation scores
    """
    try:
        result = run_pipeline(
            query=request.message,
            session_id=request.session_id,
            user_id=request.user_id,
            policy_number=request.policy_number,
            metadata=request.metadata,
        )

        # Build agent chain
        agent_steps = [
            AgentStep(
                agent=AgentName(step["agent"]),
                confidence=step["confidence"],
                reasoning=step["reasoning"],
            )
            for step in result.get("agent_steps", [])
        ]

        # Build evaluation scores
        eval_scores = None
        if result.get("evaluation_scores"):
            ev = result["evaluation_scores"]
            eval_scores = EvaluationScores(
                faithfulness=ev["faithfulness"],
                answer_relevancy=ev["answer_relevancy"],
                context_precision=ev["context_precision"],
                composite=ev["composite"],
                passed_gate=ev["passed_gate"],
            )

        intent_str = result.get("intent", "Unknown")
        try:
            intent = IntentType(intent_str)
        except ValueError:
            intent = IntentType.UNKNOWN

        return ChatResponse(
            session_id=request.session_id,
            request_id=result["request_id"],
            intent=intent,
            response=result.get("final_response", ""),
            confidence=result.get("confidence", 0.0),
            agent_chain=agent_steps,
            evaluation=eval_scores,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")


@router.get("/metrics", response_model=MetricsResponse, tags=["Analytics"])
async def get_metrics():
    """
    Retrieve aggregate evaluation metrics from BigQuery.
    Shows quality gate pass rates, average RAGAS scores, and intent distribution.
    """
    try:
        agg = get_aggregate_metrics()
        return MetricsResponse(
            total_queries=agg.get("total_queries", 0),
            avg_faithfulness=agg.get("avg_faithfulness", 0.0),
            avg_relevancy=agg.get("avg_relevancy", 0.0),
            avg_composite=agg.get("avg_composite", 0.0),
            gate_pass_rate=agg.get("gate_pass_rate", 0.0),
            intent_distribution={
                "PolicyLookup": 0,
                "ClaimsTriage": 0,
                "PremiumEstimation": 0,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics error: {str(e)}")
