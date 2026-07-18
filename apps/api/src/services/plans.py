"""Plan configuration and feature gates (billing scaffold, B4)
================================================================
No payment processor is wired in — the operator sets PLAN in the environment
and these gates enforce it. When billing goes live, a checkout flow only has
to flip the same value per tenant. Docs: docs/INSTITUTIONAL.md.
"""
from fastapi import HTTPException

from ..config import settings

PLANS = {
    "community": {
        "label": "Community",
        "features": {
            "advisor_console": True, "certificates": True, "presentation_coach": True,
            "departments": False, "invites": False, "sso": False,
        },
        "limits": {"active_sessions": 5, "materials_per_session": 10},
        "price_hint": "Free — single researcher, personal workspace",
    },
    "professional": {
        "label": "Professional",
        "features": {
            "advisor_console": True, "certificates": True, "presentation_coach": True,
            "departments": False, "invites": False, "sso": False,
        },
        "limits": {"active_sessions": 25, "materials_per_session": 30},
        "price_hint": "Per-seat — heavy individual use",
    },
    "institution": {
        "label": "Institution",
        "features": {
            "advisor_console": True, "certificates": True, "presentation_coach": True,
            "departments": True, "invites": True, "sso": True,
        },
        "limits": {"active_sessions": None, "materials_per_session": None},
        "price_hint": "Site licence — departments, invites, SSO, cohort analytics",
    },
}


def get_plan_key() -> str:
    """Resolve the active plan. Unknown values fail closed to 'community' so a
    typo in PLAN never silently unlocks paid features."""
    key = (settings.plan or "").strip().lower()
    return key if key in PLANS else "community"


def get_plan() -> dict:
    key = get_plan_key()
    return {"plan": key, **PLANS[key]}


def plan_allows(feature: str) -> bool:
    return bool(PLANS[get_plan_key()]["features"].get(feature))


def require_feature(feature: str) -> None:
    """Raise 402 when the active plan lacks *feature*. Limits in PLANS are
    advisory (surfaced via GET /billing/plan) and not yet enforced."""
    if not plan_allows(feature):
        plan = get_plan_key()
        raise HTTPException(
            status_code=402,
            detail=(
                f"'{feature}' requires the Institution plan (current plan: {plan}). "
                "Set PLAN=institution or see docs/INSTITUTIONAL.md."
            ),
        )
