"""Billing & identity (Track C — paywall)
==========================================
GET  /me                              → current user's workspace, role, plan
GET  /workspaces/{id}/billing         → current plan, all tiers, live usage
POST /workspaces/{id}/billing/plan    → owner switches the plan (self-serve)
POST /workspaces/{id}/billing/checkout→ Stripe Checkout (only if configured)
POST /billing/webhook                 → Stripe webhook (only if configured)

Plans live per workspace (workspaces.plan). Feature and usage gates are in
services/plans.py. Payment is optional: with STRIPE_SECRET_KEY the upgrade goes
through Stripe Checkout; without it the owner switch changes the plan directly.
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..auth import get_current_user, require_auth, require_role
from ..config import settings
from ..services.plans import (
    PLAN_ORDER,
    all_plans,
    get_plan,
    set_workspace_plan,
    usage_summary,
)

router = APIRouter(tags=["billing"])


class ChangePlanRequest(BaseModel):
    plan: str


class CheckoutRequest(BaseModel):
    plan: str
    success_url: str = ""
    cancel_url: str = ""


def _stripe_enabled() -> bool:
    return bool(getattr(settings, "stripe_secret_key", "").strip())


@router.get("/me")
async def me(user: Dict[str, Any] = Depends(get_current_user)):
    """Identity the frontend uses to resolve the active workspace, role, and
    plan — so pages stop hardcoding a workspace id."""
    workspace_id = user.get("workspace_id")
    from ..auth import get_role_for_user
    role = get_role_for_user(user.get("user_id", ""), workspace_id) if workspace_id else None
    if role is None and not settings.require_auth:
        role = "owner"
    return {
        "user_id": user.get("user_id"),
        "workspace_id": workspace_id,
        "role": role or "student",
        "email": user.get("email"),
        "plan": get_plan(workspace_id),
    }


@router.get("/workspaces/{workspace_id}/billing")
async def get_billing(
    workspace_id: str,
    _workspace_id: str = Depends(require_auth),
):
    """Current plan, all purchasable tiers, and live usage — for /billing."""
    if workspace_id != _workspace_id:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")
    return {
        "workspace_id": workspace_id,
        "current": get_plan(workspace_id),
        "plans": all_plans(),
        "usage": usage_summary(workspace_id),
        "payment_enabled": _stripe_enabled(),
    }


@router.post("/workspaces/{workspace_id}/billing/plan")
async def change_plan(
    workspace_id: str,
    request: ChangePlanRequest,
    owner: Dict[str, Any] = Depends(require_role("owner")),
):
    """Switch the workspace's plan. Owner-only.

    When Stripe is configured, a *paid* upgrade must go through Checkout
    (POST …/billing/checkout) — this direct switch is then limited to
    downgrades and to the free tier, so nobody unlocks paid tiers for free.
    Without Stripe, the switch is self-serve (trials / manual provisioning).
    """
    if workspace_id != owner["workspace_id"]:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")

    target = (request.plan or "").strip().lower()
    if target not in PLAN_ORDER:
        raise HTTPException(status_code=400, detail=f"Unknown plan '{request.plan}'")

    if _stripe_enabled():
        current_rank = get_plan(workspace_id)["rank"]
        if PLAN_ORDER.index(target) > current_rank and target != "community":
            raise HTTPException(
                status_code=400,
                detail="Paid upgrades must go through checkout (POST /billing/checkout).",
            )

    plan = set_workspace_plan(workspace_id, target, source="manual")
    return {"workspace_id": workspace_id, "current": plan}


@router.post("/workspaces/{workspace_id}/billing/checkout")
async def create_checkout(
    workspace_id: str,
    request: CheckoutRequest,
    owner: Dict[str, Any] = Depends(require_role("owner")),
):
    """Create a Stripe Checkout session for a paid upgrade. Returns the hosted
    checkout URL. Only available when STRIPE_SECRET_KEY (and the tier's price
    id) are configured; otherwise 501 tells the client to use the direct
    switch. The webhook flips the plan once payment completes."""
    if workspace_id != owner["workspace_id"]:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")
    if not _stripe_enabled():
        raise HTTPException(
            status_code=501,
            detail="Payment is not configured on this deployment. Use POST /billing/plan.",
        )

    target = (request.plan or "").strip().lower()
    price_id = settings.stripe_price_ids.get(target) if getattr(settings, "stripe_price_ids", None) else None
    if not price_id:
        raise HTTPException(status_code=400, detail=f"No Stripe price configured for plan '{target}'")

    try:
        import stripe  # lazy — not a hard dependency
    except ImportError:
        raise HTTPException(status_code=501, detail="stripe library not installed")

    stripe.api_key = settings.stripe_secret_key
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=request.success_url or "http://localhost:3000/billing?upgraded=1",
        cancel_url=request.cancel_url or "http://localhost:3000/billing",
        client_reference_id=workspace_id,
        metadata={"workspace_id": workspace_id, "plan": target},
    )
    return {"checkout_url": session.url}


@router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    """Stripe webhook: on checkout.session.completed, upgrade the workspace to
    the purchased plan. Signature-verified when STRIPE_WEBHOOK_SECRET is set."""
    if not _stripe_enabled():
        raise HTTPException(status_code=501, detail="Payment not configured")

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    secret = getattr(settings, "stripe_webhook_secret", "")

    try:
        import stripe
    except ImportError:
        raise HTTPException(status_code=501, detail="stripe library not installed")

    if secret:
        try:
            event = stripe.Webhook.construct_event(payload, sig, secret)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid webhook signature")
    elif not settings.require_auth:
        # Local dev only (auth disabled): accept unsigned webhooks for testing.
        import json
        event = json.loads(payload)
    else:
        # Never grant a plan from an unverified webhook in a real deployment —
        # an attacker could POST a fake checkout.session.completed and upgrade
        # any workspace for free. Refuse until the webhook secret is set.
        raise HTTPException(status_code=500, detail="STRIPE_WEBHOOK_SECRET is not configured")

    if event.get("type") == "checkout.session.completed":
        obj = event["data"]["object"]
        workspace_id = (obj.get("metadata") or {}).get("workspace_id") or obj.get("client_reference_id")
        plan = (obj.get("metadata") or {}).get("plan")
        if workspace_id and plan:
            set_workspace_plan(workspace_id, plan, source="stripe")
    return {"received": True}
