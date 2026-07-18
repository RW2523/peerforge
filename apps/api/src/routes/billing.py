"""Billing scaffold (B4): expose the active plan and its gates.
No payment processor — PLAN comes from the environment. See services/plans.py
and docs/INSTITUTIONAL.md for activation."""
from fastapi import APIRouter, Depends

from ..auth import require_auth
from ..services.plans import get_plan

router = APIRouter(tags=["billing"])


@router.get("/billing/plan")
async def current_plan(_workspace_id: str = Depends(require_auth)):
    """The active plan with its feature flags and (advisory) limits."""
    return get_plan()
