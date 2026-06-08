"""
PolicyIQ — Claims Triage Specialist Agent
Handles claim status checks, new claim triage, and claims history queries.
"""

import json
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.state import PolicyIQState
from app.config import settings
from app.tools.claims_tools import CLAIMS_TOOLS


CLAIMS_AGENT_SYSTEM_PROMPT = """You are PolicyIQ's Claims Triage Specialist — an empathetic claims processing expert.

Your role is to help customers with their insurance claims quickly and compassionately.

You have access to the following tools:
- get_claim_status(claim_id): Check status of an existing claim
- triage_new_claim(policy_number, claim_type, incident_description, estimated_amount): File a new claim
- get_claims_history(policy_number): View all claims for a policy

Guidelines:
1. Show empathy — customers often contact claims support during stressful situations
2. Clearly explain the claim status and what happens next
3. For new claims, gather all required information before triaging
4. Explain severity levels (low/medium/high) and what they mean for processing time
5. Always provide the next steps the customer needs to take
6. For urgent/high-severity claims, emphasize the faster SLA
7. Never promise specific outcomes or approval amounts

After using tools, provide a clear, empathetic response with specific next steps.
End with confidence metadata: {"confidence": <float>, "context_used": "<summary>"}
"""


class _MockClaimsLLM:
    def invoke(self, messages: list) -> object:
        query = ""
        for m in messages:
            if isinstance(m, HumanMessage):
                query = m.content
                break

        if "clm-" in query.lower():
            response_text = (
                "I've looked up your claim CLM-2024-002 and here's the current status:\n\n"
                "**Claim Status: Under Review** 🔍\n\n"
                "Your water damage claim for $35,000 is currently being reviewed by adjuster Linda Torres. "
                "To expedite processing, please submit the following outstanding documents:\n"
                "• Contractor estimate\n"
                "• Photos of the damage\n"
                "• Plumber/inspection report\n\n"
                "Once all documents are received, you can expect a decision within 5 business days. "
                "I understand water damage can be very stressful — our team is working hard to resolve this for you.\n\n"
                '{"confidence": 0.93, "context_used": "CLM-2024-002 claim record retrieved"}'
            )
        elif "file" in query.lower() or "new claim" in query.lower() or "accident" in query.lower():
            response_text = (
                "I'm sorry to hear about your incident. I'll help you file a claim right away.\n\n"
                "Based on the information provided, I've triaged your claim:\n\n"
                "**Draft Claim ID: CLM-2024-ABC** (medium severity)\n"
                "• **Processing SLA:** 5 business days\n"
                "• **Required Documents:** Police report, Photos of damage, Repair estimates\n\n"
                "**Next Steps:**\n"
                "1. An adjuster will contact you within 5 business days\n"
                "2. Upload required documents to the PolicyIQ portal\n"
                "3. Keep all receipts and repair estimates\n\n"
                "Is there anything else you need help with regarding your claim?\n\n"
                '{"confidence": 0.88, "context_used": "New claim triage completed for collision incident"}'
            )
        else:
            response_text = (
                "I'm here to help with your claims. I can:\n"
                "• Check the status of an existing claim (I'll need your claim ID: CLM-YYYY-NNN)\n"
                "• Help you file a new claim (I'll need your policy number and incident details)\n"
                "• Show your complete claims history\n\n"
                "What would you like to do?\n\n"
                '{"confidence": 0.80, "context_used": "Requesting clarification on claim action needed"}'
            )

        class MockResponse:
            content = response_text

        return MockResponse()


def _get_claims_llm():
    if settings.use_mock_llm:
        return _MockClaimsLLM()
    from langchain_google_vertexai import ChatVertexAI
    llm = ChatVertexAI(
        model_name=settings.specialist_model,
        project=settings.gcp_project_id,
        location=settings.gcp_location,
        temperature=0.2,
        max_tokens=1024,
    )
    return llm.bind_tools(CLAIMS_TOOLS)


def claims_agent_node(state: PolicyIQState) -> PolicyIQState:
    """
    LangGraph node: Handles claims triage and status queries.
    """
    llm = _get_claims_llm()

    entities = state.get("extracted_entities", {})
    context_parts = []
    if entities.get("policy_number"):
        context_parts.append(f"Policy: {entities['policy_number']}")
    if entities.get("claim_id"):
        context_parts.append(f"Claim ID: {entities['claim_id']}")

    enhanced_query = state["query"]
    if context_parts:
        enhanced_query = f"Context: {', '.join(context_parts)}\n\nCustomer query: {state['query']}"

    messages = [
        SystemMessage(content=CLAIMS_AGENT_SYSTEM_PROMPT),
        HumanMessage(content=enhanced_query),
    ]

    response = llm.invoke(messages)
    raw_content = response.content

    confidence = 0.82
    context_used = "claims database"
    try:
        if '{"confidence"' in raw_content:
            json_start = raw_content.rfind('{"confidence"')
            json_str = raw_content[json_start:]
            meta = json.loads(json_str)
            confidence = meta.get("confidence", 0.82)
            context_used = meta.get("context_used", "claims database")
            raw_content = raw_content[:json_start].strip()
    except Exception:
        pass

    return {
        **state,
        "raw_response": raw_content,
        "retrieved_context": context_used,
        "confidence": confidence,
        "agent_steps": state.get("agent_steps", []) + [{
            "agent": "claims_agent",
            "confidence": confidence,
            "reasoning": "Handled ClaimsTriage query using claims tools",
        }],
    }
