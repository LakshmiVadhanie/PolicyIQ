"""
PolicyIQ — Quality Gate
Blocks low-quality responses from reaching production users.
Implements the RAGAS-based evaluation gate described in the architecture.
"""

from app.agents.state import PolicyIQState
from app.config import settings
from app.evaluation.ragas_evaluator import evaluate_with_ragas
from app.tools.bigquery_tools import log_evaluation_metrics


FALLBACK_RESPONSE = (
    "I want to make sure I give you the most accurate information possible. "
    "Based on your question, I recommend speaking directly with one of our licensed "
    "insurance specialists who can provide personalized guidance. "
    "You can reach our team at support@policyiq.com or call 1-800-POLICY-IQ. "
    "Our team is available Monday–Friday, 8AM–8PM EST."
)


def quality_gate_node(state: PolicyIQState) -> PolicyIQState:
    """
    LangGraph node: Evaluates response quality using RAGAS metrics.
    If the composite score is below threshold, replaces with a safe fallback.
    """
    query = state.get("query", "")
    answer = state.get("raw_response", "")
    context = state.get("retrieved_context", "")

    # Run RAGAS evaluation
    scores = evaluate_with_ragas(query=query, answer=answer, context=context)

    passed = scores.composite >= settings.ragas_composite_threshold

    evaluation_dict = {
        "faithfulness": scores.faithfulness,
        "answer_relevancy": scores.answer_relevancy,
        "context_precision": scores.context_precision,
        "composite": scores.composite,
        "passed_gate": passed,
    }

    # Log to BigQuery
    log_evaluation_metrics(
        request_id=state["request_id"],
        session_id=state["session_id"],
        faithfulness=scores.faithfulness,
        answer_relevancy=scores.answer_relevancy,
        context_precision=scores.context_precision,
        composite=scores.composite,
        passed_gate=passed,
    )

    if passed:
        final_response = answer
        fallback_triggered = False
        print(
            f"[QualityGate]  PASSED — composite={scores.composite:.3f} "
            f"(threshold={settings.ragas_composite_threshold})"
        )
    else:
        final_response = FALLBACK_RESPONSE
        fallback_triggered = True
        print(
            f"[QualityGate]  BLOCKED — composite={scores.composite:.3f} "
            f"(threshold={settings.ragas_composite_threshold}). Fallback triggered."
        )

    return {
        **state,
        "evaluation_scores": evaluation_dict,
        "passed_quality_gate": passed,
        "fallback_triggered": fallback_triggered,
        "final_response": final_response,
    }
