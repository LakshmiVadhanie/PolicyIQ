"""
PolicyIQ — Test Configuration
Shared fixtures for all test modules.
"""

import os
import pytest

# Force mock mode for all tests
os.environ["USE_MOCK_LLM"] = "true"
os.environ["USE_MOCK_BIGQUERY"] = "true"
os.environ["APP_ENV"] = "development"
os.environ["GCP_PROJECT_ID"] = "mock-project-id"
os.environ["CONFIDENCE_THRESHOLD"] = "0.75"
os.environ["RAGAS_COMPOSITE_THRESHOLD"] = "0.70"


@pytest.fixture
def sample_policy_query():
    return "What does my auto insurance policy POL-001 cover?"


@pytest.fixture
def sample_claims_query():
    return "What is the status of my claim CLM-2024-002?"


@pytest.fixture
def sample_premium_query():
    return "How much would car insurance cost for a 28-year-old driver?"


@pytest.fixture
def base_state():
    import uuid
    return {
        "request_id": str(uuid.uuid4()),
        "session_id": "test-session-001",
        "user_id": None,
        "query": "test query",
        "policy_number": None,
        "metadata": {},
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
