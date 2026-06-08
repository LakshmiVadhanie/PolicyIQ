"""
PolicyIQ — Premium Estimation Specialist Agent
Handles premium calculation, quote generation, and pricing queries.
"""

import json
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from app.agents.state import PolicyIQState
from app.config import settings


# ── Premium Estimation Tools ───────────────────────────────────────────────────

@tool
def estimate_auto_premium(
    driver_age: int,
    vehicle_year: int,
    vehicle_make: str,
    coverage_level: str,
    annual_mileage: int = 12000,
    clean_record: bool = True,
) -> dict:
    """
    Estimate monthly premium for auto insurance.

    Args:
        driver_age: Age of primary driver
        vehicle_year: Year of the vehicle
        vehicle_make: Make of the vehicle (e.g., Toyota, BMW)
        coverage_level: Coverage level (basic|standard|comprehensive)
        annual_mileage: Annual mileage driven
        clean_record: Whether driver has clean driving record

    Returns:
        Premium estimate with breakdown
    """
    base = 80.0

    # Age factor
    if driver_age < 25:
        base *= 1.8
    elif driver_age > 65:
        base *= 1.2

    # Vehicle age factor
    vehicle_age = 2024 - vehicle_year
    if vehicle_age < 3:
        base *= 1.3
    elif vehicle_age > 10:
        base *= 0.85

    # Coverage factor
    coverage_multipliers = {"basic": 0.7, "standard": 1.0, "comprehensive": 1.5}
    base *= coverage_multipliers.get(coverage_level.lower(), 1.0)

    # Mileage factor
    if annual_mileage > 15000:
        base *= 1.15
    elif annual_mileage < 8000:
        base *= 0.9

    # Record discount
    if clean_record:
        base *= 0.85

    monthly_premium = round(base, 2)

    return {
        "insurance_type": "Auto",
        "estimated_monthly_premium": monthly_premium,
        "estimated_annual_premium": round(monthly_premium * 12, 2),
        "coverage_level": coverage_level,
        "deductible_options": {"low": 250, "standard": 500, "high": 1000},
        "factors_applied": {
            "driver_age": driver_age,
            "vehicle_year": vehicle_year,
            "vehicle_make": vehicle_make,
            "coverage_level": coverage_level,
            "clean_record_discount": clean_record,
        },
        "disclaimer": "This is an estimate only. Final premium depends on full underwriting review.",
    }


@tool
def estimate_home_premium(
    property_value: float,
    property_age_years: int,
    zip_code: str,
    coverage_level: str = "standard",
    has_security_system: bool = False,
) -> dict:
    """
    Estimate monthly premium for home insurance.

    Args:
        property_value: Estimated value of the property in USD
        property_age_years: Age of the property in years
        zip_code: Property ZIP code (affects risk zone)
        coverage_level: Coverage level (basic|standard|premium)
        has_security_system: Whether home has a monitored security system

    Returns:
        Premium estimate with breakdown
    """
    # Base rate: ~0.5% of property value annually
    annual_base = property_value * 0.005

    # Property age factor
    if property_age_years > 30:
        annual_base *= 1.25
    elif property_age_years < 5:
        annual_base *= 0.9

    # Coverage multiplier
    coverage_multipliers = {"basic": 0.75, "standard": 1.0, "premium": 1.4}
    annual_base *= coverage_multipliers.get(coverage_level.lower(), 1.0)

    # Security discount
    if has_security_system:
        annual_base *= 0.9

    monthly_premium = round(annual_base / 12, 2)

    return {
        "insurance_type": "Home",
        "estimated_monthly_premium": monthly_premium,
        "estimated_annual_premium": round(annual_base, 2),
        "coverage_level": coverage_level,
        "coverage_amount": property_value,
        "deductible_options": {"low": 500, "standard": 1000, "high": 2500},
        "factors_applied": {
            "property_value": property_value,
            "property_age_years": property_age_years,
            "coverage_level": coverage_level,
            "security_discount": has_security_system,
        },
        "disclaimer": "This is an estimate only. Final premium depends on full property inspection.",
    }


@tool
def estimate_health_premium(
    age: int,
    plan_type: str,
    number_of_members: int = 1,
    smoker: bool = False,
) -> dict:
    """
    Estimate monthly premium for health insurance.

    Args:
        age: Age of primary insured
        plan_type: Plan type (HMO|PPO|EPO|HDHP)
        number_of_members: Total number of members on the plan
        smoker: Whether primary insured is a smoker

    Returns:
        Premium estimate with breakdown
    """
    base_rates = {"HMO": 280, "PPO": 420, "EPO": 350, "HDHP": 220}
    base = base_rates.get(plan_type.upper(), 350)

    # Age factor
    if age > 50:
        base *= 1.6
    elif age > 40:
        base *= 1.3
    elif age < 30:
        base *= 0.85

    # Members
    if number_of_members == 2:
        base *= 1.8
    elif number_of_members >= 3:
        base *= 2.2

    # Smoker surcharge
    if smoker:
        base *= 1.5

    monthly_premium = round(base, 2)

    return {
        "insurance_type": "Health",
        "plan_type": plan_type,
        "estimated_monthly_premium": monthly_premium,
        "estimated_annual_premium": round(monthly_premium * 12, 2),
        "number_of_members": number_of_members,
        "deductible_options": {"HDHP": 3000, "PPO": 1500, "HMO": 1000, "EPO": 1250},
        "factors_applied": {
            "age": age,
            "plan_type": plan_type,
            "members": number_of_members,
            "smoker_surcharge": smoker,
        },
        "disclaimer": "Estimates are based on current rates. ACA subsidies may apply based on income.",
    }


PREMIUM_TOOLS = [estimate_auto_premium, estimate_home_premium, estimate_health_premium]


# ── Agent ──────────────────────────────────────────────────────────────────────

PREMIUM_AGENT_SYSTEM_PROMPT = """You are PolicyIQ's Premium Estimation Specialist — an expert insurance actuary.

Your role is to provide accurate, transparent premium estimates and help customers understand pricing.

You have access to:
- estimate_auto_premium(...): Calculate auto insurance premiums
- estimate_home_premium(...): Calculate home insurance premiums
- estimate_health_premium(...): Calculate health insurance premiums

Guidelines:
1. Always gather necessary information before estimating (age, property value, vehicle info, etc.)
2. Explain what factors affect the premium (good driving record, property age, etc.)
3. Show how to save money (discounts, higher deductibles, bundles)
4. Always include the disclaimer that these are estimates
5. Compare plan options when relevant
6. Be transparent about how premiums are calculated

End with confidence metadata: {"confidence": <float>, "context_used": "<summary>"}
"""


class _MockPremiumLLM:
    def invoke(self, messages: list) -> object:
        response_text = (
            "Great question about insurance pricing! Based on a typical profile, here's what you can expect:\n\n"
            "**Auto Insurance Estimate:**\n"
            "• Basic coverage: ~$67/month\n"
            "• Standard coverage: ~$96/month *(recommended)*\n"
            "• Comprehensive coverage: ~$144/month\n\n"
            "**Key factors that affect your premium:**\n"
            "✅ Clean driving record → saves ~15%\n"
            "✅ Low annual mileage (<8,000 mi) → saves ~10%\n"
            "✅ Anti-theft device → saves ~5%\n\n"
            "**Home Insurance Estimate** (for a $400,000 home):\n"
            "• Standard coverage: ~$167/month\n"
            "• Premium coverage: ~$233/month\n\n"
            "To get a personalized quote with exact pricing, I'll need a few details. "
            "What type of insurance are you most interested in — auto, home, or health?\n\n"
            '{"confidence": 0.87, "context_used": "Premium estimation tools applied with typical profile assumptions"}'
        )

        class MockResponse:
            content = response_text

        return MockResponse()


def _get_premium_llm():
    if settings.use_mock_llm:
        return _MockPremiumLLM()
    from langchain_google_vertexai import ChatVertexAI
    llm = ChatVertexAI(
        model_name=settings.specialist_model,
        project=settings.gcp_project_id,
        location=settings.gcp_location,
        temperature=0.3,
        max_tokens=1024,
    )
    return llm.bind_tools(PREMIUM_TOOLS)


def premium_agent_node(state: PolicyIQState) -> PolicyIQState:
    """
    LangGraph node: Handles premium estimation queries.
    """
    llm = _get_premium_llm()

    messages = [
        SystemMessage(content=PREMIUM_AGENT_SYSTEM_PROMPT),
        HumanMessage(content=state["query"]),
    ]

    response = llm.invoke(messages)
    raw_content = response.content

    confidence = 0.85
    context_used = "premium estimation models"
    try:
        if '{"confidence"' in raw_content:
            json_start = raw_content.rfind('{"confidence"')
            json_str = raw_content[json_start:]
            meta = json.loads(json_str)
            confidence = meta.get("confidence", 0.85)
            context_used = meta.get("context_used", "premium estimation models")
            raw_content = raw_content[:json_start].strip()
    except Exception:
        pass

    return {
        **state,
        "raw_response": raw_content,
        "retrieved_context": context_used,
        "confidence": confidence,
        "agent_steps": state.get("agent_steps", []) + [{
            "agent": "premium_agent",
            "confidence": confidence,
            "reasoning": "Handled PremiumEstimation query using actuarial tools",
        }],
    }
