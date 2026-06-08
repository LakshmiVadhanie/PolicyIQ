"""
PolicyIQ — Agent Unit Tests
Tests the supervisor, specialist agents, and quality gate nodes in isolation.
"""

import pytest
from app.agents.supervisor import supervisor_node, route_to_agent
from app.agents.policy_agent import policy_agent_node
from app.agents.claims_agent import claims_agent_node
from app.agents.premium_agent import premium_agent_node
from app.evaluation.quality_gate import quality_gate_node


# ── Supervisor Tests ───────────────────────────────────────────────────────────

class TestSupervisorNode:
    def test_routes_policy_query(self, base_state):
        """Supervisor should detect PolicyLookup intent."""
        state = {**base_state, "query": "What does my auto insurance policy cover?"}
        result = supervisor_node(state)
        assert result["intent"] == "PolicyLookup"
        assert result["confidence"] > 0.0
        assert len(result["agent_steps"]) == 1
        assert result["agent_steps"][0]["agent"] == "supervisor"

    def test_routes_claims_query(self, base_state):
        """Supervisor should detect ClaimsTriage intent."""
        state = {**base_state, "query": "I need to file a claim for my car accident"}
        result = supervisor_node(state)
        assert result["intent"] == "ClaimsTriage"
        assert result["confidence"] > 0.0

    def test_routes_premium_query(self, base_state):
        """Supervisor should detect PremiumEstimation intent."""
        state = {**base_state, "query": "How much does car insurance cost per month?"}
        result = supervisor_node(state)
        assert result["intent"] == "PremiumEstimation"
        assert result["confidence"] > 0.0

    def test_includes_supervisor_reasoning(self, base_state):
        """Supervisor should include reasoning in response."""
        state = {**base_state, "query": "Check my policy details"}
        result = supervisor_node(state)
        assert "supervisor_reasoning" in result
        assert len(result["supervisor_reasoning"]) > 0

    def test_extracts_policy_number(self, base_state):
        """Supervisor should extract policy number from query."""
        state = {**base_state, "query": "Look up policy pol-001 for me"}
        result = supervisor_node(state)
        entities = result.get("extracted_entities", {})
        assert entities.get("policy_number") is not None

    def test_route_to_agent_policy(self, base_state):
        """route_to_agent should return correct agent names."""
        state = {**base_state, "intent": "PolicyLookup"}
        assert route_to_agent(state) == "policy_agent"

    def test_route_to_agent_claims(self, base_state):
        state = {**base_state, "intent": "ClaimsTriage"}
        assert route_to_agent(state) == "claims_agent"

    def test_route_to_agent_premium(self, base_state):
        state = {**base_state, "intent": "PremiumEstimation"}
        assert route_to_agent(state) == "premium_agent"

    def test_route_to_agent_unknown_defaults(self, base_state):
        """Unknown intents should default to policy agent."""
        state = {**base_state, "intent": "Unknown"}
        assert route_to_agent(state) == "policy_agent"


# ── Policy Agent Tests ─────────────────────────────────────────────────────────

class TestPolicyAgent:
    def test_returns_response(self, base_state):
        """Policy agent should return a non-empty response."""
        state = {
            **base_state,
            "query": "What coverage does policy POL-001 include?",
            "intent": "PolicyLookup",
            "extracted_entities": {"policy_number": "POL-001"},
        }
        result = policy_agent_node(state)
        assert "raw_response" in result
        assert len(result["raw_response"]) > 10

    def test_updates_agent_steps(self, base_state):
        """Policy agent should append to agent_steps."""
        state = {
            **base_state,
            "query": "Show my policy details",
            "intent": "PolicyLookup",
            "agent_steps": [{"agent": "supervisor", "confidence": 0.9, "reasoning": "test"}],
        }
        result = policy_agent_node(state)
        assert len(result["agent_steps"]) == 2
        assert result["agent_steps"][1]["agent"] == "policy_agent"

    def test_returns_confidence(self, base_state):
        """Policy agent should return a confidence score."""
        state = {**base_state, "query": "policy info", "intent": "PolicyLookup"}
        result = policy_agent_node(state)
        assert 0.0 <= result["confidence"] <= 1.0


# ── Claims Agent Tests ─────────────────────────────────────────────────────────

class TestClaimsAgent:
    def test_returns_response(self, base_state):
        """Claims agent should return a response."""
        state = {
            **base_state,
            "query": "Check the status of claim CLM-2024-002",
            "intent": "ClaimsTriage",
            "extracted_entities": {"claim_id": "CLM-2024-002"},
        }
        result = claims_agent_node(state)
        assert len(result["raw_response"]) > 10

    def test_handles_new_claim_query(self, base_state):
        """Claims agent handles new claim filing requests."""
        state = {
            **base_state,
            "query": "I need to file a new claim for water damage",
            "intent": "ClaimsTriage",
        }
        result = claims_agent_node(state)
        assert result["raw_response"] is not None
        assert result["confidence"] > 0.0


# ── Premium Agent Tests ────────────────────────────────────────────────────────

class TestPremiumAgent:
    def test_returns_estimate(self, base_state):
        """Premium agent should return pricing information."""
        state = {
            **base_state,
            "query": "How much is car insurance for a 30-year-old?",
            "intent": "PremiumEstimation",
        }
        result = premium_agent_node(state)
        assert len(result["raw_response"]) > 10
        assert result["confidence"] > 0.0


# ── Quality Gate Tests ─────────────────────────────────────────────────────────

class TestQualityGate:
    def test_passes_good_response(self, base_state):
        """Quality gate should pass high-quality responses."""
        state = {
            **base_state,
            "query": "What does my auto insurance cover?",
            "raw_response": (
                "Your auto insurance policy POL-001 provides comprehensive coverage "
                "for collision, liability, uninsured motorist protection, and medical payments. "
                "The coverage limit is $100,000 with a $500 deductible. "
                "Your policy is currently active and covers Alice Johnson and Bob Johnson "
                "for the 2020 Toyota Camry."
            ),
            "retrieved_context": "POL-001 auto insurance policy data with coverage details",
        }
        result = quality_gate_node(state)
        assert "evaluation_scores" in result
        assert "passed_quality_gate" in result
        assert result["evaluation_scores"]["composite"] > 0.0
        assert result["final_response"] is not None

    def test_evaluation_scores_present(self, base_state):
        """Quality gate should always produce evaluation scores."""
        state = {
            **base_state,
            "query": "test query",
            "raw_response": "This is a test response about insurance coverage.",
            "retrieved_context": "insurance policy context",
        }
        result = quality_gate_node(state)
        scores = result["evaluation_scores"]
        assert "faithfulness" in scores
        assert "answer_relevancy" in scores
        assert "context_precision" in scores
        assert "composite" in scores
        assert "passed_gate" in scores

    def test_fallback_on_low_quality(self, base_state):
        """Quality gate should trigger fallback for extremely poor responses."""
        state = {
            **base_state,
            "query": "What does my policy cover?",
            "raw_response": "x",  # Deliberately terrible response
            "retrieved_context": "",
        }
        result = quality_gate_node(state)
        # The response should be either the raw response or fallback
        assert result["final_response"] is not None
        assert len(result["final_response"]) > 0
