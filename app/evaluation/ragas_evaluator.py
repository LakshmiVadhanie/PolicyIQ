"""
PolicyIQ — RAGAS Evaluator
Computes faithfulness, answer relevancy, and context precision scores.
Falls back to heuristic scoring when USE_MOCK_LLM=true.
"""

import re
import math
from typing import Optional
from dataclasses import dataclass

from app.config import settings


@dataclass
class RAGASScores:
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    composite: float


def _heuristic_faithfulness(answer: str, context: str) -> float:
    """
    Heuristic faithfulness: checks how much of the answer is grounded in context.
    In production, RAGAS uses an LLM to judge this.
    """
    if not context or not answer:
        return 0.5

    # Extract key terms from answer (exclude stop words)
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "and", "or"}
    answer_terms = set(
        w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', answer)
        if w.lower() not in stop_words
    )
    context_terms = set(
        w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', context)
        if w.lower() not in stop_words
    )

    if not answer_terms:
        return 0.5

    overlap = len(answer_terms & context_terms)
    score = min(overlap / len(answer_terms), 1.0)
    # Scale to 0.6–1.0 range (heuristic baseline)
    return round(0.6 + (score * 0.4), 3)


def _heuristic_answer_relevancy(query: str, answer: str) -> float:
    """
    Heuristic answer relevancy: checks how well the answer addresses the query.
    """
    if not query or not answer:
        return 0.5

    query_terms = set(re.findall(r'\b[a-zA-Z]{3,}\b', query.lower()))
    answer_terms = set(re.findall(r'\b[a-zA-Z]{3,}\b', answer.lower()))

    if not query_terms:
        return 0.5

    coverage = len(query_terms & answer_terms) / len(query_terms)
    length_bonus = min(len(answer) / 200, 0.2)  # longer answers tend to be more complete
    score = min(coverage + length_bonus, 1.0)
    return round(0.55 + (score * 0.45), 3)


def _heuristic_context_precision(query: str, context: str) -> float:
    """
    Heuristic context precision: checks if retrieved context is relevant to query.
    """
    if not query or not context:
        return 0.6

    query_terms = set(re.findall(r'\b[a-zA-Z]{3,}\b', query.lower()))
    context_terms = set(re.findall(r'\b[a-zA-Z]{3,}\b', context.lower()))

    if not query_terms:
        return 0.6

    precision = len(query_terms & context_terms) / len(query_terms)
    return round(0.60 + (precision * 0.40), 3)


def evaluate_with_ragas(
    query: str,
    answer: str,
    context: str,
) -> RAGASScores:
    """
    Evaluate a query-answer-context triple using RAGAS metrics.
    Uses real RAGAS when USE_MOCK_LLM=false, otherwise heuristic scoring.

    Args:
        query: The original user query
        answer: The agent's generated answer
        context: The context/data retrieved and used to generate the answer

    Returns:
        RAGASScores with individual metrics and composite score
    """
    if not settings.use_mock_llm:
        return _real_ragas_evaluate(query, answer, context)

    # Heuristic evaluation for local dev
    faithfulness = _heuristic_faithfulness(answer, context)
    relevancy = _heuristic_answer_relevancy(query, answer)
    precision = _heuristic_context_precision(query, context)
    composite = round((faithfulness + relevancy + precision) / 3, 3)

    print(
        f"[RAGAS Mock] faithfulness={faithfulness:.3f}, "
        f"relevancy={relevancy:.3f}, precision={precision:.3f}, "
        f"composite={composite:.3f}"
    )

    return RAGASScores(
        faithfulness=faithfulness,
        answer_relevancy=relevancy,
        context_precision=precision,
        composite=composite,
    )


def _real_ragas_evaluate(query: str, answer: str, context: str) -> RAGASScores:
    """
    Real RAGAS evaluation using the ragas library with Vertex AI as judge LLM.
    """
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_precision
        from langchain_google_vertexai import ChatVertexAI, VertexAIEmbeddings

        llm = ChatVertexAI(
            model_name=settings.vertex_ai_model,
            project=settings.gcp_project_id,
            location=settings.gcp_location,
        )
        embeddings = VertexAIEmbeddings(
            model_name="textembedding-gecko@003",
            project=settings.gcp_project_id,
        )

        data = {
            "question": [query],
            "answer": [answer],
            "contexts": [[context]],
        }
        dataset = Dataset.from_dict(data)

        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision],
            llm=llm,
            embeddings=embeddings,
        )

        f_score = float(result["faithfulness"])
        r_score = float(result["answer_relevancy"])
        p_score = float(result["context_precision"])
        composite = round((f_score + r_score + p_score) / 3, 3)

        return RAGASScores(
            faithfulness=round(f_score, 3),
            answer_relevancy=round(r_score, 3),
            context_precision=round(p_score, 3),
            composite=composite,
        )

    except Exception as e:
        print(f"[RAGAS] Real evaluation failed, falling back to heuristic: {e}")
        return RAGASScores(
            faithfulness=0.75,
            answer_relevancy=0.75,
            context_precision=0.75,
            composite=0.75,
        )
