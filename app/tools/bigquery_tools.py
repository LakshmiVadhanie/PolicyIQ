"""
PolicyIQ — BigQuery Tools
Read/write helpers for BigQuery interaction logging and analytics.
Falls back to console logging when USE_MOCK_BIGQUERY=true.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Optional
from langchain_core.tools import tool

from app.config import settings


#  BigQuery Client (lazy init) 

_bq_client = None


def _get_bq_client():
    """Lazily initialize BigQuery client."""
    global _bq_client
    if _bq_client is None and not settings.use_mock_bigquery:
        from google.cloud import bigquery
        _bq_client = bigquery.Client(project=settings.gcp_project_id)
    return _bq_client


#  Mock Storage 

_mock_interactions: list[dict] = []
_mock_metrics: list[dict] = []


#  Write Helpers 

def log_interaction(
    session_id: str,
    request_id: str,
    user_query: str,
    intent: str,
    agent_response: str,
    retrieved_context: str,
    confidence: float,
    latency_ms: int,
) -> None:
    """Log a query-response interaction to BigQuery (or mock store)."""
    row = {
        "request_id": request_id,
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "user_query": user_query,
        "intent": intent,
        "agent_response": agent_response,
        "retrieved_context": retrieved_context[:2000],  # truncate for BQ
        "confidence": confidence,
        "latency_ms": latency_ms,
    }

    if settings.use_mock_bigquery:
        _mock_interactions.append(row)
        print(f"[BigQuery Mock] Interaction logged: {request_id}")
        return

    client = _get_bq_client()
    table_id = f"{settings.bigquery_full_dataset}.{settings.bigquery_interactions_table}"
    errors = client.insert_rows_json(table_id, [row])
    if errors:
        print(f"[BigQuery] Insert errors: {errors}")


def log_evaluation_metrics(
    request_id: str,
    session_id: str,
    faithfulness: float,
    answer_relevancy: float,
    context_precision: float,
    composite: float,
    passed_gate: bool,
) -> None:
    """Log RAGAS evaluation scores to BigQuery."""
    row = {
        "request_id": request_id,
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "faithfulness": faithfulness,
        "answer_relevancy": answer_relevancy,
        "context_precision": context_precision,
        "composite_score": composite,
        "passed_gate": passed_gate,
    }

    if settings.use_mock_bigquery:
        _mock_metrics.append(row)
        print(f"[BigQuery Mock] Metrics logged: request={request_id}, composite={composite:.3f}")
        return

    client = _get_bq_client()
    table_id = f"{settings.bigquery_full_dataset}.{settings.bigquery_metrics_table}"
    errors = client.insert_rows_json(table_id, [row])
    if errors:
        print(f"[BigQuery] Metrics insert errors: {errors}")


def log_agent_routing(
    request_id: str,
    session_id: str,
    intent: str,
    routed_agent: str,
    confidence: float,
    iteration: int,
) -> None:
    """Log each agent routing decision to BigQuery."""
    row = {
        "request_id": request_id,
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "intent": intent,
        "routed_agent": routed_agent,
        "confidence": confidence,
        "iteration": iteration,
    }

    if settings.use_mock_bigquery:
        print(f"[BigQuery Mock] Routing logged: {routed_agent} (intent={intent}, conf={confidence:.2f})")
        return

    client = _get_bq_client()
    table_id = f"{settings.bigquery_full_dataset}.{settings.bigquery_routing_table}"
    client.insert_rows_json(table_id, [row])


#  Read / Analytics 

def get_aggregate_metrics() -> dict:
    """Fetch aggregate evaluation metrics from BigQuery (or mock)."""
    if settings.use_mock_bigquery:
        if not _mock_metrics:
            return {
                "total_queries": 0,
                "avg_faithfulness": 0.0,
                "avg_relevancy": 0.0,
                "avg_composite": 0.0,
                "gate_pass_rate": 0.0,
            }
        n = len(_mock_metrics)
        return {
            "total_queries": len(_mock_interactions),
            "avg_faithfulness": sum(m["faithfulness"] for m in _mock_metrics) / n,
            "avg_relevancy": sum(m["answer_relevancy"] for m in _mock_metrics) / n,
            "avg_composite": sum(m["composite_score"] for m in _mock_metrics) / n,
            "gate_pass_rate": sum(1 for m in _mock_metrics if m["passed_gate"]) / n,
        }

    client = _get_bq_client()
    query = f"""
        SELECT
            COUNT(*) as total_queries,
            AVG(faithfulness) as avg_faithfulness,
            AVG(answer_relevancy) as avg_relevancy,
            AVG(composite_score) as avg_composite,
            COUNTIF(passed_gate) / COUNT(*) as gate_pass_rate
        FROM `{settings.bigquery_full_dataset}.{settings.bigquery_metrics_table}`
        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
    """
    results = client.query(query).result()
    row = list(results)[0]
    return dict(row)
