"""
PolicyIQ — Pydantic API Models
Request/response schemas for all FastAPI endpoints.
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid
from datetime import datetime


# ── Enums ─────────────────────────────────────────────────────────────────────

class IntentType(str, Enum):
    POLICY_LOOKUP = "PolicyLookup"
    CLAIMS_TRIAGE = "ClaimsTriage"
    PREMIUM_ESTIMATION = "PremiumEstimation"
    UNKNOWN = "Unknown"


class AgentName(str, Enum):
    SUPERVISOR = "supervisor"
    POLICY_AGENT = "policy_agent"
    CLAIMS_AGENT = "claims_agent"
    PREMIUM_AGENT = "premium_agent"


# ── Chat Request / Response ────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=2000)
    policy_number: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentStep(BaseModel):
    agent: AgentName
    confidence: float
    reasoning: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EvaluationScores(BaseModel):
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    composite: float
    passed_gate: bool


class ChatResponse(BaseModel):
    session_id: str
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intent: IntentType
    response: str
    confidence: float
    agent_chain: list[AgentStep]
    evaluation: Optional[EvaluationScores] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Dialogflow CX Webhook ──────────────────────────────────────────────────────

class DialogflowQueryInput(BaseModel):
    text: Optional[dict] = None
    intent: Optional[dict] = None
    event: Optional[dict] = None
    language_code: str = "en"


class DialogflowSessionInfo(BaseModel):
    session: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class DialogflowWebhookRequest(BaseModel):
    """Dialogflow CX webhook fulfillment request schema."""
    detect_intent_response_id: Optional[str] = None
    intent_info: Optional[dict] = None
    page_info: Optional[dict] = None
    session_info: Optional[DialogflowSessionInfo] = None
    fulfillment_info: Optional[dict] = None
    messages: list[dict] = Field(default_factory=list)
    text: Optional[str] = None
    language_code: str = "en"

    model_config = {"populate_by_name": True}


class DialogflowMessage(BaseModel):
    text: dict[str, list[str]]


class DialogflowWebhookResponse(BaseModel):
    """Dialogflow CX webhook fulfillment response schema."""
    fulfillment_response: dict[str, Any]
    session_info: Optional[dict] = None
    page_info: Optional[dict] = None


# ── Health / Metrics ───────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MetricsResponse(BaseModel):
    total_queries: int
    avg_faithfulness: float
    avg_relevancy: float
    avg_composite: float
    gate_pass_rate: float
    intent_distribution: dict[str, int]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
