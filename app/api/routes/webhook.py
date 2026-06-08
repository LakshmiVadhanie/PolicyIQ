"""
PolicyIQ — Dialogflow CX Webhook Route
Handles fulfillment webhooks from Dialogflow CX intent nodes.
Each Dialogflow intent triggers this webhook, which runs the LangGraph pipeline
and returns structured fulfillment responses.
"""

import re
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from app.agents.graph import run_pipeline

router = APIRouter()


def _extract_text_from_webhook(body: dict) -> str:
    """
    Extract the user's message text from the Dialogflow CX webhook payload.
    Handles multiple payload structures.
    """
    # Try direct text field
    if "text" in body:
        return body["text"]

    # Try messages array
    messages = body.get("messages", [])
    for msg in messages:
        if isinstance(msg, dict):
            text_obj = msg.get("text", {})
            if isinstance(text_obj, dict):
                texts = text_obj.get("text", [])
                if texts:
                    return texts[0]

    # Try fulfillment_info
    if "fulfillmentInfo" in body:
        return body.get("fulfillmentInfo", {}).get("tag", "")

    return "Hello"


def _extract_session_id(body: dict) -> str:
    """Extract session ID from Dialogflow CX webhook request."""
    session_info = body.get("sessionInfo", {})
    session = session_info.get("session", "")
    # Format: projects/.../sessions/<session_id>
    parts = session.split("/sessions/")
    if len(parts) > 1:
        return parts[-1].split("/")[0]
    return session or "default-session"


def _extract_parameters(body: dict) -> dict:
    """Extract session parameters from Dialogflow CX request."""
    session_info = body.get("sessionInfo", {})
    return session_info.get("parameters", {})


@router.post("/webhook", tags=["Dialogflow CX"])
async def dialogflow_webhook(request: Request):
    """
    Dialogflow CX fulfillment webhook endpoint.

    Receives intent detection results from Dialogflow CX and routes them
    through the PolicyIQ LangGraph multi-agent pipeline. Returns structured
    fulfillment messages back to Dialogflow.

    Intent routing:
    - PolicyLookup → policy_agent
    - ClaimsTriage → claims_agent
    - PremiumEstimation → premium_agent
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON in webhook request")

    # Extract request data
    user_text = _extract_text_from_webhook(body)
    session_id = _extract_session_id(body)
    parameters = _extract_parameters(body)

    # Extract pre-detected intent from Dialogflow (if available)
    intent_info = body.get("intentInfo", {})
    dialogflow_intent = intent_info.get("displayName", "")

    # Map Dialogflow intent display names to our pipeline intents
    intent_hint_map = {
        "PolicyLookup": "policy lookup",
        "ClaimsTriage": "claims triage",
        "PremiumEstimation": "premium estimation",
    }

    # Augment query with Dialogflow context
    query = user_text
    if dialogflow_intent and dialogflow_intent in intent_hint_map:
        # Add intent context to help supervisor
        query = f"[Intent: {intent_hint_map[dialogflow_intent]}] {user_text}"

    # Extract policy number from parameters if available
    policy_number = parameters.get("policy_number") or parameters.get("policyNumber")

    # Run the LangGraph pipeline
    result = run_pipeline(
        query=query,
        session_id=session_id,
        policy_number=policy_number,
        metadata={
            "source": "dialogflow_cx",
            "dialogflow_intent": dialogflow_intent,
            "parameters": parameters,
        },
    )

    final_response = result.get("final_response", "I'm sorry, I couldn't process your request.")

    # Build Dialogflow CX fulfillment response
    fulfillment_response = {
        "fulfillmentResponse": {
            "messages": [
                {
                    "text": {
                        "text": [final_response]
                    }
                }
            ]
        },
        "sessionInfo": {
            "parameters": {
                "intent": result.get("intent", "Unknown"),
                "confidence": result.get("confidence", 0.0),
                "request_id": result.get("request_id", ""),
                "quality_gate_passed": result.get("passed_quality_gate", False),
            }
        },
        "pageInfo": {
            "currentPage": _map_intent_to_page(result.get("intent", "Unknown"))
        },
    }

    return JSONResponse(content=fulfillment_response)


def _map_intent_to_page(intent: str) -> str:
    """Map detected intent to Dialogflow CX page name."""
    page_map = {
        "PolicyLookup": "Policy Information Page",
        "ClaimsTriage": "Claims Processing Page",
        "PremiumEstimation": "Quote Estimation Page",
    }
    return page_map.get(intent, "Main Menu")
