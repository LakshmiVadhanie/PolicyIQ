"""
PolicyIQ — Mock Claims Database Tools
Simulates a claims management system. In production, these
would call actual claims processing APIs.
"""

from datetime import date, datetime
from langchain_core.tools import tool


#  Mock Claims Data 

MOCK_CLAIMS = {
    "CLM-2024-001": {
        "claim_id": "CLM-2024-001",
        "policy_number": "POL-001",
        "claimant": "Alice Johnson",
        "incident_date": "2024-03-10",
        "filed_date": "2024-03-12",
        "claim_type": "Collision",
        "description": "Rear-end collision at intersection, vehicle damage to bumper and trunk",
        "claimed_amount": 8500.00,
        "approved_amount": 8000.00,
        "deductible_applied": 500.00,
        "status": "Approved",
        "adjuster": "David Kim",
        "resolution_date": "2024-03-25",
        "documents_required": [],
    },
    "CLM-2024-002": {
        "claim_id": "CLM-2024-002",
        "policy_number": "POL-002",
        "claimant": "Marcus Chen",
        "incident_date": "2024-04-05",
        "filed_date": "2024-04-06",
        "claim_type": "Water Damage",
        "description": "Burst pipe caused flooding in basement, damaged flooring and personal items",
        "claimed_amount": 35000.00,
        "approved_amount": None,
        "deductible_applied": None,
        "status": "Under Review",
        "adjuster": "Linda Torres",
        "resolution_date": None,
        "documents_required": ["Contractor estimate", "Photos", "Plumber report"],
    },
    "CLM-2024-003": {
        "claim_id": "CLM-2024-003",
        "policy_number": "POL-003",
        "claimant": "Priya Sharma",
        "incident_date": "2024-02-20",
        "filed_date": "2024-02-22",
        "claim_type": "Medical",
        "description": "Emergency room visit and follow-up specialist consultations",
        "claimed_amount": 12000.00,
        "approved_amount": 10000.00,
        "deductible_applied": 2000.00,
        "status": "Paid",
        "adjuster": "Robert Lee",
        "resolution_date": "2024-03-05",
        "documents_required": [],
    },
}

# Triage classification rules
CLAIM_SEVERITY = {
    "low": {"max_amount": 5000, "sla_days": 10},
    "medium": {"max_amount": 25000, "sla_days": 5},
    "high": {"max_amount": float("inf"), "sla_days": 2},
}


#  Tools 

@tool
def get_claim_status(claim_id: str) -> dict:
    """
    Retrieve the current status and details of an insurance claim.

    Args:
        claim_id: The unique claim identifier (e.g., CLM-2024-001)

    Returns:
        Full claim details including status, amounts, and required documents
    """
    claim = MOCK_CLAIMS.get(claim_id.upper())
    if not claim:
        return {
            "error": f"Claim {claim_id} not found",
            "tip": "Claim IDs follow the format CLM-YYYY-NNN",
        }
    return claim


@tool
def triage_new_claim(
    policy_number: str,
    claim_type: str,
    incident_description: str,
    estimated_amount: float,
) -> dict:
    """
    Triage a new insurance claim and return severity, SLA, and next steps.

    Args:
        policy_number: Policy number associated with the claim
        claim_type: Type of claim (e.g., Collision, Water Damage, Medical)
        incident_description: Brief description of the incident
        estimated_amount: Estimated loss/damage amount in USD

    Returns:
        Triage result with severity level, SLA, required documents, and claim ID
    """
    import uuid

    # Determine severity
    if estimated_amount <= 5000:
        severity = "low"
    elif estimated_amount <= 25000:
        severity = "medium"
    else:
        severity = "high"

    sla = CLAIM_SEVERITY[severity]

    # Required documents by claim type
    doc_requirements = {
        "collision": ["Police report", "Photos of damage", "Repair estimates"],
        "water damage": ["Contractor estimate", "Photos", "Plumber/inspection report"],
        "medical": ["EOB from provider", "Medical records", "Receipts"],
        "theft": ["Police report", "Inventory list", "Photos"],
        "fire": ["Fire department report", "Photos", "Contractor estimate"],
    }

    required_docs = doc_requirements.get(claim_type.lower(), ["Incident report", "Supporting documentation"])

    draft_claim_id = f"CLM-{datetime.now().year}-{str(uuid.uuid4())[:3].upper()}"

    return {
        "draft_claim_id": draft_claim_id,
        "policy_number": policy_number,
        "claim_type": claim_type,
        "estimated_amount": estimated_amount,
        "severity": severity,
        "priority_sla_days": sla["sla_days"],
        "required_documents": required_docs,
        "next_steps": [
            f"An adjuster will contact you within {sla['sla_days']} business days",
            "Upload required documents to the PolicyIQ portal",
            f"Reference your draft claim ID: {draft_claim_id}",
        ],
        "status": "Pending Submission",
    }


@tool
def get_claims_history(policy_number: str) -> dict:
    """
    Retrieve all claims history associated with a given policy number.

    Args:
        policy_number: The policy number to look up claims for

    Returns:
        List of all claims, total claimed, and summary statistics
    """
    policy_claims = [
        c for c in MOCK_CLAIMS.values()
        if c["policy_number"].upper() == policy_number.upper()
    ]

    if not policy_claims:
        return {
            "policy_number": policy_number,
            "total_claims": 0,
            "claims": [],
            "message": "No claims found for this policy",
        }

    total_claimed = sum(c["claimed_amount"] for c in policy_claims)
    total_approved = sum(c["approved_amount"] or 0 for c in policy_claims)

    return {
        "policy_number": policy_number,
        "total_claims": len(policy_claims),
        "total_claimed_amount": total_claimed,
        "total_approved_amount": total_approved,
        "claims": policy_claims,
    }


# Export all tools
CLAIMS_TOOLS = [get_claim_status, triage_new_claim, get_claims_history]
