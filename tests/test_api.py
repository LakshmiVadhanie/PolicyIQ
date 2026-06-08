"""
PolicyIQ — FastAPI Endpoint Tests
Tests all HTTP endpoints with TestClient.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


#  Health Tests 

class TestHealthEndpoints:
    def test_root_endpoint(self):
        """Root endpoint should return service info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "PolicyIQ"
        assert "version" in data

    def test_health_endpoint(self):
        """Health endpoint should return healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data
        assert "timestamp" in data


#  Chat Tests 

class TestChatEndpoint:
    def test_policy_query(self):
        """Chat endpoint should handle policy lookup queries."""
        response = client.post("/chat", json={
            "message": "What does my auto insurance cover?",
            "session_id": "test-api-001",
        })
        assert response.status_code == 200
        data = response.json()
        assert "intent" in data
        assert "response" in data
        assert "confidence" in data
        assert "agent_chain" in data
        assert len(data["response"]) > 0
        assert 0.0 <= data["confidence"] <= 1.0

    def test_claims_query(self):
        """Chat endpoint should handle claims queries."""
        response = client.post("/chat", json={
            "message": "Check the status of claim CLM-2024-001",
            "session_id": "test-api-002",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] in ["ClaimsTriage", "PolicyLookup", "PremiumEstimation", "Unknown"]

    def test_premium_query(self):
        """Chat endpoint should handle premium estimation queries."""
        response = client.post("/chat", json={
            "message": "How much is car insurance per month?",
            "session_id": "test-api-003",
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["response"]) > 0

    def test_response_has_agent_chain(self):
        """Response should include agent execution audit trail."""
        response = client.post("/chat", json={
            "message": "What is my deductible?",
            "session_id": "test-api-004",
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["agent_chain"], list)
        assert len(data["agent_chain"]) >= 1
        # Each step should have agent, confidence, reasoning
        for step in data["agent_chain"]:
            assert "agent" in step
            assert "confidence" in step
            assert "reasoning" in step

    def test_response_has_evaluation(self):
        """Response should include RAGAS evaluation scores."""
        response = client.post("/chat", json={
            "message": "Tell me about home insurance coverage",
            "session_id": "test-api-005",
        })
        assert response.status_code == 200
        data = response.json()
        if data.get("evaluation"):
            ev = data["evaluation"]
            assert "faithfulness" in ev
            assert "answer_relevancy" in ev
            assert "composite" in ev
            assert "passed_gate" in ev

    def test_missing_message_returns_422(self):
        """Request without message should return validation error."""
        response = client.post("/chat", json={"session_id": "test-api-006"})
        assert response.status_code == 422

    def test_with_policy_number(self):
        """Request with explicit policy number should work."""
        response = client.post("/chat", json={
            "message": "What are my coverage details?",
            "session_id": "test-api-007",
            "policy_number": "POL-001",
        })
        assert response.status_code == 200

    def test_session_id_in_response(self):
        """Response should echo back the session_id."""
        response = client.post("/chat", json={
            "message": "Tell me about my policy",
            "session_id": "my-unique-session-xyz",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "my-unique-session-xyz"


#  Webhook Tests 

class TestWebhookEndpoint:
    def test_basic_webhook(self):
        """Webhook endpoint should handle Dialogflow CX requests."""
        response = client.post("/webhook", json={
            "text": "I need to file a claim for my car accident",
            "sessionInfo": {
                "session": "projects/test/sessions/webhook-test-001",
                "parameters": {}
            },
            "intentInfo": {
                "displayName": "ClaimsTriage"
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert "fulfillmentResponse" in data
        messages = data["fulfillmentResponse"]["messages"]
        assert len(messages) > 0

    def test_webhook_returns_session_params(self):
        """Webhook should return updated session parameters."""
        response = client.post("/webhook", json={
            "text": "What does my policy cover?",
            "sessionInfo": {
                "session": "projects/test/sessions/webhook-test-002",
                "parameters": {}
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert "sessionInfo" in data
        assert "parameters" in data["sessionInfo"]
        params = data["sessionInfo"]["parameters"]
        assert "intent" in params
        assert "confidence" in params

    def test_webhook_with_policy_number_param(self):
        """Webhook should extract policy number from Dialogflow parameters."""
        response = client.post("/webhook", json={
            "text": "Show me my policy coverage",
            "sessionInfo": {
                "session": "projects/test/sessions/webhook-test-003",
                "parameters": {"policy_number": "POL-001"}
            }
        })
        assert response.status_code == 200


#  Metrics Tests 

class TestMetricsEndpoint:
    def test_metrics_endpoint(self):
        """Metrics endpoint should return analytics summary."""
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "total_queries" in data
        assert "avg_faithfulness" in data
        assert "avg_relevancy" in data
        assert "avg_composite" in data
        assert "gate_pass_rate" in data
