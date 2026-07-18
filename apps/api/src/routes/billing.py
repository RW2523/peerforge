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
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..auth import get_current_user, require_auth, require_role
from ..config import settings
import logging

from ..services.plans import (
    PLAN_ORDER,
    all_plans,
    billing_state,
    find_workspace_by_customer,
    find_workspace_by_subscription,
    get_plan,
    plan_for_price_id,
    set_workspace_plan,
    stored_subscription_id,
    usage_summary,
)

logger = logging.getLogger(__name__)

# Stripe subscription statuses that mean "no longer entitled" → downgrade.
_DEAD_SUB_STATUSES = {"canceled", "unpaid", "incomplete_expired"}
# Statuses that DO entitle the paid plan (allowlist — everything else, e.g.
# 'incomplete' / 'paused', does not grant access).
_ENTITLING_STATUSES = {"active", "trialing"}

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
        "subscription": billing_state(workspace_id) if workspace_id else None,
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
        "subscription": billing_state(workspace_id),
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
        success_url=request.success_url or f"{settings.public_base_url}/billing?upgraded=1",
        cancel_url=request.cancel_url or f"{settings.public_base_url}/billing",
        client_reference_id=workspace_id,
        metadata={"workspace_id": workspace_id, "plan": target},
        # Propagate to the subscription so later subscription.* events (cancel,
        # plan change, payment failure) also carry the workspace_id + plan.
        subscription_data={"metadata": {"workspace_id": workspace_id, "plan": target}},
    )
    return {"checkout_url": session.url}


@router.post("/workspaces/{workspace_id}/billing/portal")
async def create_portal(
    workspace_id: str,
    owner: Dict[str, Any] = Depends(require_role("owner")),
):
    """Open the Stripe billing portal so an owner can update their card, change
    plan, or cancel — self-service. Requires a linked Stripe customer (set on
    the first checkout). Cancellation there fires the subscription.* webhooks."""
    if workspace_id != owner["workspace_id"]:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")
    if not _stripe_enabled():
        raise HTTPException(status_code=501, detail="Payment is not configured on this deployment.")

    from ..database import get_db_connection, get_cursor
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("SELECT stripe_customer_id FROM workspaces WHERE workspace_id = %s", (workspace_id,))
        row = cur.fetchone()
    customer_id = row["stripe_customer_id"] if row else None
    if not customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer on file — subscribe first.")

    try:
        import stripe
    except ImportError:
        raise HTTPException(status_code=501, detail="stripe library not installed")
    stripe.api_key = settings.stripe_secret_key
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{settings.public_base_url}/billing",
    )
    return {"portal_url": session.url}


# ── Webhook event handlers (module-level for testability) ───────────────────

def _extract_workspace(obj: dict) -> Optional[str]:
    """Resolve the workspace an event belongs to: prefer the workspace_id we
    stamped into metadata, else the stored Stripe subscription/customer link."""
    ws = (obj.get("metadata") or {}).get("workspace_id") or obj.get("client_reference_id")
    if ws:
        return ws
    sub_id = obj.get("id") if obj.get("object") == "subscription" else obj.get("subscription")
    ws = find_workspace_by_subscription(sub_id) if sub_id else None
    if ws:
        return ws
    return find_workspace_by_customer(obj.get("customer"))


def _subscription_price_id(sub: dict) -> Optional[str]:
    items = ((sub.get("items") or {}).get("data")) or []
    return (items[0].get("price") or {}).get("id") if items else None


def _period_end_dt(sub: dict):
    ts = sub.get("current_period_end")
    if not ts:
        return None
    from datetime import datetime, timezone
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def _handle_checkout_completed(obj: dict) -> None:
    ws = _extract_workspace(obj)
    plan = (obj.get("metadata") or {}).get("plan")
    if ws and plan:
        set_workspace_plan(
            ws, plan, source="stripe",
            customer_id=obj.get("customer"),
            subscription_id=obj.get("subscription"),
            status="active",
        )


def _handle_subscription_updated(sub: dict) -> None:
    ws = _extract_workspace(sub)
    if not ws:
        return
    status = sub.get("status")
    if status in _DEAD_SUB_STATUSES:
        set_workspace_plan(ws, "community", source="stripe", status="canceled", clear_subscription=True)
        return

    # Reject stale / out-of-order updates. Stripe does NOT guarantee event
    # ordering and retries for days, so a late 'active' update could otherwise
    # resurrect a canceled subscription (the workspace_id survives in metadata
    # even after we unlink it) → permanent free entitlement.
    sub_id = sub.get("id")
    linked = stored_subscription_id(ws)
    if linked is None:
        # No active link: only checkout.session.completed may (re)grant a plan.
        # A bare 'updated' must not revive a workspace we already canceled.
        if billing_state(ws)["status"] == "canceled":
            return
    elif sub_id and sub_id != linked:
        # Update is for a subscription that is not this workspace's current one.
        return

    # Prefer the LIVE price over stale checkout metadata; only fall back to
    # metadata when the event carries no price at all.
    price_id = _subscription_price_id(sub)
    plan = plan_for_price_id(price_id) if price_id else (sub.get("metadata") or {}).get("plan")
    renews = _period_end_dt(sub)

    if sub.get("cancel_at_period_end"):
        # Keep the current paid tier until the period ends; deletion downgrades.
        keep = plan or get_plan(ws)["plan"]
        set_workspace_plan(ws, keep, source="stripe",
                           subscription_id=sub_id, status="canceling", renews_at=renews)
        return

    if plan is None:
        logger.warning(
            "Stripe subscription %s carries an unmapped price %s; leaving workspace %s plan unchanged",
            sub_id, price_id, ws,
        )
        return

    # Entitle only on an allowlist — never grant on 'incomplete'/'paused'/etc.
    if status in _ENTITLING_STATUSES:
        set_workspace_plan(ws, plan, source="stripe", subscription_id=sub_id,
                           status="active", renews_at=renews)
    elif status == "past_due":
        set_workspace_plan(ws, plan, source="stripe", subscription_id=sub_id,
                           status="past_due", renews_at=renews)
    else:
        logger.info(
            "Stripe subscription %s status %r is non-entitling; leaving workspace %s unchanged",
            sub_id, status, ws,
        )


def _handle_subscription_deleted(sub: dict) -> None:
    ws = _extract_workspace(sub)
    if ws:
        set_workspace_plan(ws, "community", source="stripe", status="canceled", clear_subscription=True)


@router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    """Stripe webhook — the source of truth for subscription state:
      checkout.session.completed    → activate the purchased plan + link IDs
      customer.subscription.updated → plan change / scheduled-cancel / past-due
      customer.subscription.deleted → downgrade to the free tier

    Signature-verified when STRIPE_WEBHOOK_SECRET is set; unsigned payloads are
    accepted only in local dev (auth disabled) and refused in production."""
    if not _stripe_enabled():
        raise HTTPException(status_code=501, detail="Payment not configured")

    payload = await request.body()
    secret = getattr(settings, "stripe_webhook_secret", "")

    if secret:
        try:
            import stripe
        except ImportError:
            raise HTTPException(status_code=501, detail="stripe library not installed")
        sig = request.headers.get("stripe-signature", "")
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
        # a forged checkout.session.completed could upgrade any workspace for
        # free. Refuse until the webhook secret is set.
        raise HTTPException(status_code=500, detail="STRIPE_WEBHOOK_SECRET is not configured")

    etype = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}
    if etype == "checkout.session.completed":
        _handle_checkout_completed(obj)
    elif etype == "customer.subscription.updated":
        _handle_subscription_updated(obj)
    elif etype == "customer.subscription.deleted":
        _handle_subscription_deleted(obj)
    return {"received": True}
