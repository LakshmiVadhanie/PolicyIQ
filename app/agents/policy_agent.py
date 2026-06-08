"""
PolicyIQ — Policy Lookup Specialist Agent
Handles all policy-related queries: coverage, renewal, policy details.
"""

import json
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import BaseTool

from app.agents.state import PolicyIQState
from app.config import settings
from app.tools.policy_tools import POLICY_TOOLS, lookup_policy, check_coverage, get_policy_renewal_info


POLICY_AGENT_SYSTEM_PROMPT = """You are PolicyIQ's Policy Lookup Specialist — an expert insurance policy analyst.

Your role is to help customers understand their insurance policies with clear, accurate, and empathetic answers.

You have access to the following tools:
- lookup_policy(policy_number): Retrieve full policy details
- check_coverage(policy_number, coverage_type): Check specific coverage
- get_policy_renewal_info(policy_number): Get renewal information

Guidelines:
1. Always verify policy details before answering
2. Be specific about coverage amounts, deductibles, and exclusions
3. If the customer doesn't have a policy number, ask for it politely
4. Explain complex insurance terms in plain language
5. Always mention the customer can contact their agent for complex questions
6. Respond in a professional but warm tone

After using tools, provide a comprehensive response that directly answers the customer's question.
End your response by noting your confidence level (0.0-1.0) in a JSON block:
{"confidence": <float>, "context_used": "<brief summary of data accessed>"}
"""


class _MockPolicyLLM:
    """Mock policy agent for local development."""

    def invoke(self, messages: list) -> object:
        query = ""
        for m in messages:
            if isinstance(m, HumanMessage):
                query = m.content
                break

        # Simulate tool calls and generate response
        if "pol-" in query.lower() or "policy" in query.lower():
            response_text = (
                "Based on your policy details, I can see you have an Active Auto Insurance policy (POL-001) "
                "covering Alice Johnson and Bob Johnson for a 2020 Toyota Camry. Your policy provides "
                "comprehensive coverage up to $100,000 with a $500 deductible and a monthly premium of $120.00. "
                "Your policy is currently active and in good standing. "
                "If you need to add a driver or vehicle, please contact your agent sarah.miller@policyiq.com.\n\n"
                '{"confidence": 0.91, "context_used": "POL-001 policy data retrieved from policy database"}'
            )
        else:
            response_text = (
                "I'd be happy to help you with your policy information! To look up your specific policy details, "
                "I'll need your policy number (format: POL-XXX). Could you please provide that? "
                "Alternatively, if you have a general question about what types of coverage we offer, "
                "I can explain that as well.\n\n"
                '{"confidence": 0.82, "context_used": "No policy number provided, requesting clarification"}'
            )

        class MockResponse:
            content = response_text

        return MockResponse()


def _get_policy_llm():
    if settings.use_mock_llm:
        return _MockPolicyLLM()
    from langchain_google_vertexai import ChatVertexAI
    llm = ChatVertexAI(
        model_name=settings.specialist_model,
        project=settings.gcp_project_id,
        location=settings.gcp_location,
        temperature=0.2,
        max_tokens=1024,
    )
    return llm.bind_tools(POLICY_TOOLS)


def policy_agent_node(state: PolicyIQState) -> PolicyIQState:
    """
    LangGraph node: Handles policy lookup queries.
    Uses Vertex AI Gemini with policy tools bound.
    """
    llm = _get_policy_llm()

    # Build context from extracted entities
    entities = state.get("extracted_entities", {})
    policy_num = state.get("policy_number") or entities.get("policy_number", "")

    enhanced_query = state["query"]
    if policy_num:
        enhanced_query = f"Policy number: {policy_num}\n\nCustomer query: {state['query']}"

    messages = [
        SystemMessage(content=POLICY_AGENT_SYSTEM_PROMPT),
        HumanMessage(content=enhanced_query),
    ]

    response = llm.invoke(messages)
    raw_content = response.content

    # Extract confidence from response
    confidence = 0.80
    context_used = "policy database"
    try:
        # Look for trailing JSON block
        if '{"confidence"' in raw_content:
            json_start = raw_content.rfind('{"confidence"')
            json_str = raw_content[json_start:]
            meta = json.loads(json_str)
            confidence = meta.get("confidence", 0.80)
            context_used = meta.get("context_used", "policy database")
            raw_content = raw_content[:json_start].strip()
    except Exception:
        pass

    return {
        **state,
        "raw_response": raw_content,
        "retrieved_context": context_used,
        "confidence": confidence,
        "agent_steps": state.get("agent_steps", []) + [{
            "agent": "policy_agent",
            "confidence": confidence,
            "reasoning": f"Handled PolicyLookup query using policy tools",
        }],
    }
