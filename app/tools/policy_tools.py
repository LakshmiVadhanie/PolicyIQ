"""
PolicyIQ — Mock Policy Database Tools
Simulates a policy management system. In production, these
would call actual insurance policy APIs or databases.
"""

import random
from datetime import date, timedelta
from typing import Optional
from langchain_core.tools import tool


# ── Mock Policy Data ───────────────────────────────────────────────────────────

MOCK_POLICIES = {
    "POL-001": {
        "policy_number": "POL-001",
        "holder_name": "Alice Johnson",
        "policy_type": "Auto Insurance",
        "coverage_amount": 100000,
        "deductible": 500,
        "premium_monthly": 120.00,
        "start_date": "2023-01-15",
        "end_date": "2024-01-15",
        "status": "Active",
        "covered_drivers": ["Alice Johnson", "Bob Johnson"],
        "vehicles": [{"make": "Toyota", "model": "Camry", "year": 2020, "vin": "1HGBH41JXMN109186"}],
        "agent_contact": "sarah.miller@policyiq.com",
    },
    "POL-002": {
        "policy_number": "POL-002",
        "holder_name": "Marcus Chen",
        "policy_type": "Home Insurance",
        "coverage_amount": 500000,
        "deductible": 1000,
        "premium_monthly": 250.00,
        "start_date": "2022-06-01",
        "end_date": "2025-06-01",
        "status": "Active",
        "property_address": "123 Oak Street, Austin TX 78701",
        "property_value": 450000,
        "agent_contact": "james.wright@policyiq.com",
    },
    "POL-003": {
        "policy_number": "POL-003",
        "holder_name": "Priya Sharma",
        "policy_type": "Health Insurance",
        "coverage_amount": 250000,
        "deductible": 2000,
        "premium_monthly": 380.00,
        "start_date": "2024-01-01",
        "end_date": "2025-01-01",
        "status": "Active",
        "network": "BlueCross PPO",
        "covered_members": ["Priya Sharma", "Raj Sharma"],
        "agent_contact": "emily.davis@policyiq.com",
    },
}


# ── Tools ──────────────────────────────────────────────────────────────────────

@tool
def lookup_policy(policy_number: str) -> dict:
    """
    Retrieve full policy details by policy number.

    Args:
        policy_number: The unique policy identifier (e.g., POL-001)

    Returns:
        Policy details dictionary or error message
    """
    policy = MOCK_POLICIES.get(policy_number.upper())
    if not policy:
        return {
            "error": f"Policy {policy_number} not found",
            "available_policies": list(MOCK_POLICIES.keys()),
        }
    return policy


@tool
def check_coverage(policy_number: str, coverage_type: str) -> dict:
    """
    Check if a specific coverage type is included in the policy.

    Args:
        policy_number: The unique policy identifier
        coverage_type: Type of coverage to check (e.g., 'collision', 'liability')

    Returns:
        Coverage details and limits
    """
    policy = MOCK_POLICIES.get(policy_number.upper())
    if not policy:
        return {"error": f"Policy {policy_number} not found"}

    coverage_map = {
        "auto": ["collision", "comprehensive", "liability", "uninsured motorist", "medical payments"],
        "home": ["dwelling", "personal property", "liability", "additional living expenses", "flood (addon)"],
        "health": ["hospitalization", "outpatient", "prescription", "mental health", "preventive care"],
    }

    policy_type_key = policy["policy_type"].split()[0].lower()
    available_coverages = coverage_map.get(policy_type_key, [])
    is_covered = coverage_type.lower() in available_coverages

    return {
        "policy_number": policy_number,
        "policy_type": policy["policy_type"],
        "queried_coverage": coverage_type,
        "is_covered": is_covered,
        "coverage_amount": policy["coverage_amount"] if is_covered else 0,
        "deductible": policy["deductible"] if is_covered else None,
        "all_coverages": available_coverages,
    }


@tool
def get_policy_renewal_info(policy_number: str) -> dict:
    """
    Get renewal status and upcoming renewal date for a policy.

    Args:
        policy_number: The unique policy identifier

    Returns:
        Renewal information including days until expiry
    """
    policy = MOCK_POLICIES.get(policy_number.upper())
    if not policy:
        return {"error": f"Policy {policy_number} not found"}

    end_date = date.fromisoformat(policy["end_date"])
    today = date.today()
    days_until_renewal = (end_date - today).days

    return {
        "policy_number": policy_number,
        "end_date": policy["end_date"],
        "days_until_renewal": days_until_renewal,
        "renewal_status": "Expired" if days_until_renewal < 0 else (
            "Renewal Due Soon" if days_until_renewal <= 30 else "Active"
        ),
        "agent_contact": policy.get("agent_contact", "support@policyiq.com"),
    }


# Export all tools
POLICY_TOOLS = [lookup_policy, check_coverage, get_policy_renewal_info]
