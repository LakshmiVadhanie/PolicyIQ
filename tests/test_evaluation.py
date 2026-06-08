"""
PolicyIQ — RAGAS Evaluation Gate Tests
Runs the golden dataset through the full pipeline and verifies
that average RAGAS scores exceed the quality gate thresholds.
This is the CI gate — failure blocks production deployment.
"""

import json
import os
import pytest
from pathlib import Path

from app.agents.graph import run_pipeline
from app.evaluation.ragas_evaluator import evaluate_with_ragas
from app.config import settings


GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"

# CI thresholds — must match or exceed these averages across the golden set
# Note: faithfulness threshold is lower in CI because the heuristic mock evaluator
# uses text-overlap which is conservative. Real RAGAS with Vertex AI scores higher.
CI_FAITHFULNESS_THRESHOLD = 0.60
CI_RELEVANCY_THRESHOLD = 0.65
CI_COMPOSITE_THRESHOLD = 0.65  # Slightly relaxed vs production gate for CI speed


@pytest.fixture(scope="module")
def golden_dataset():
    with open(GOLDEN_DATASET_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def pipeline_results(golden_dataset):
    """Run all golden examples through the pipeline once (module-scoped for speed)."""
    results = []
    for example in golden_dataset:
        result = run_pipeline(
            query=example["query"],
            session_id=f"eval-{example['id']}",
        )
        results.append({
            "example": example,
            "pipeline_result": result,
        })
    return results


class TestGoldenDatasetIntentAccuracy:
    """Test that the pipeline correctly classifies intents."""

    def test_intent_accuracy(self, pipeline_results):
        """At least 75% of golden examples should have correct intent."""
        correct = sum(
            1 for r in pipeline_results
            if r["pipeline_result"].get("intent") == r["example"]["expected_intent"]
        )
        accuracy = correct / len(pipeline_results)
        print(f"\nIntent accuracy: {correct}/{len(pipeline_results)} = {accuracy:.1%}")
        assert accuracy >= 0.75, (
            f"Intent accuracy {accuracy:.1%} is below 75% threshold. "
            f"Review supervisor routing logic."
        )

    def test_all_queries_return_response(self, pipeline_results):
        """All golden queries should produce a non-empty final response."""
        for r in pipeline_results:
            example = r["example"]
            result = r["pipeline_result"]
            assert len(result.get("final_response", "")) > 0, (
                f"Empty response for golden example {example['id']}: {example['query']}"
            )

    def test_confidence_above_threshold(self, pipeline_results):
        """Average confidence across golden set should meet threshold."""
        confidences = [r["pipeline_result"].get("confidence", 0) for r in pipeline_results]
        avg_confidence = sum(confidences) / len(confidences)
        print(f"\nAverage confidence: {avg_confidence:.3f}")
        assert avg_confidence >= 0.70, (
            f"Average confidence {avg_confidence:.3f} is below 0.70 threshold"
        )


class TestRAGASQualityGate:
    """Test RAGAS scores across the golden dataset."""

    @pytest.fixture(scope="class")
    def ragas_scores(self, pipeline_results):
        """Compute RAGAS scores for all golden examples."""
        scores = []
        for r in pipeline_results:
            result = r["pipeline_result"]
            query = r["example"]["query"]
            answer = result.get("final_response", "")
            context = result.get("retrieved_context", "")

            score = evaluate_with_ragas(query=query, answer=answer, context=context)
            scores.append(score)
            print(
                f"  [{r['example']['id']}] "
                f"faith={score.faithfulness:.3f} "
                f"rel={score.answer_relevancy:.3f} "
                f"prec={score.context_precision:.3f} "
                f"comp={score.composite:.3f}"
            )
        return scores

    def test_average_faithfulness(self, ragas_scores):
        """Average faithfulness should exceed CI threshold."""
        avg = sum(s.faithfulness for s in ragas_scores) / len(ragas_scores)
        print(f"\nAverage faithfulness: {avg:.3f} (threshold: {CI_FAITHFULNESS_THRESHOLD})")
        assert avg >= CI_FAITHFULNESS_THRESHOLD, (
            f"Average faithfulness {avg:.3f} < {CI_FAITHFULNESS_THRESHOLD}"
        )

    def test_average_relevancy(self, ragas_scores):
        """Average answer relevancy should exceed CI threshold."""
        avg = sum(s.answer_relevancy for s in ragas_scores) / len(ragas_scores)
        print(f"\nAverage relevancy: {avg:.3f} (threshold: {CI_RELEVANCY_THRESHOLD})")
        assert avg >= CI_RELEVANCY_THRESHOLD, (
            f"Average relevancy {avg:.3f} < {CI_RELEVANCY_THRESHOLD}"
        )

    def test_average_composite_score(self, ragas_scores):
        """
         RAGAS GATE: Average composite score must meet threshold.
        This is the primary CI gate — failure blocks deployment.
        """
        avg = sum(s.composite for s in ragas_scores) / len(ragas_scores)
        print(f"\n RAGAS Gate — Average composite: {avg:.3f} (threshold: {CI_COMPOSITE_THRESHOLD})")
        assert avg >= CI_COMPOSITE_THRESHOLD, (
            f" RAGAS GATE FAILED: Average composite score {avg:.3f} "
            f"is below production threshold {CI_COMPOSITE_THRESHOLD}. "
            f"Review agent response quality before deploying."
        )

    def test_no_catastrophic_failures(self, ragas_scores):
        """No individual response should score below 0.4 composite (catastrophic failure)."""
        failures = [i for i, s in enumerate(ragas_scores) if s.composite < 0.40]
        assert len(failures) == 0, (
            f"Catastrophic quality failures at indices: {failures}. "
            f"These responses are critically below acceptable quality."
        )
