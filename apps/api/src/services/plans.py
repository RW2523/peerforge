"""Plan configuration, per-workspace resolution, and paywall gates (Track C)
=============================================================================
Each workspace holds a plan (workspaces.plan; NULL inherits the deployment
default from config PLAN). A plan decides:
  - which features unlock (departments, invites, SSO)
  - how many review sessions / materials the workspace may create

Gates fail closed: an unknown plan value resolves to 'community', and a
DB error resolves to the free tier rather than unlocking paid features.

Payment is optional. When STRIPE_SECRET_KEY is set, an owner upgrade creates a
Stripe Checkout session; without it, the owner switch changes the plan directly
(self-serve / trials / manual provisioning). See docs/INSTITUTIONAL.md.
"""
from typing import Optional

from fastapi import HTTPException

from ..config import settings
from ..database import get_db_connection, get_cursor

# order matters: index = tier rank (used for upgrade/downgrade UI)
PLAN_ORDER = ["community", "professional", "institution"]

PLANS = {
    "community": {
        "label": "Community",
        "price_hint": "Free",
        "blurb": "A single researcher rehearsing their own review.",
        "features": {
            "advisor_console": True, "certificates": True, "presentation_coach": True,
            "departments": False, "invites": False, "sso": False,
        },
        "limits": {"max_sessions": 5, "max_materials_per_session": 10},
    },
    "professional": {
        "label": "Professional",
        "price_hint": "$29 / researcher / mo",
        "blurb": "Heavy individual use — more sessions and materials.",
        "features": {
            "advisor_console": True, "certificates": True, "presentation_coach": True,
            "departments": False, "invites": False, "sso": False,
        },
        "limits": {"max_sessions": 25, "max_materials_per_session": 30},
    },
    "institution": {
        "label": "Institution",
        "price_hint": "Site licence — contact sales",
        "blurb": "Departments, invites, SSO, and unlimited cohort analytics.",
        "features": {
            "advisor_console": True, "certificates": True, "presentation_coach": True,
            "departments": True, "invites": True, "sso": True,
        },
        "limits": {"max_sessions": None, "max_materials_per_session": None},
    },
}

FEATURE_LABELS = {
    "departments": "Departments",
    "invites": "Member invites",
    "sso": "Single sign-on",
    "advisor_console": "Advisor console",
    "certificates": "Readiness certificates",
    "presentation_coach": "Presentation coach",
}


def _default_plan_key() -> str:
    key = (settings.plan or "").strip().lower()
    return key if key in PLANS else "community"


def get_plan_key_for_workspace(workspace_id: Optional[str]) -> str:
    """Resolve a workspace's plan key. NULL/absent inherits the deployment
    default; unknown values and DB errors fail closed to 'community'."""
    default = _default_plan_key()
    if not workspace_id:
        return default
    try:
        with get_db_connection() as conn:
            cur = get_cursor(conn)
            cur.execute("SELECT plan FROM workspaces WHERE workspace_id = %s", (workspace_id,))
            row = cur.fetchone()
    except Exception:
        return "community"
    if not row:
        return default
    plan = (row["plan"] or "").strip().lower() if row["plan"] else ""
    if not plan:
        return default
    return plan if plan in PLANS else "community"


def get_plan(workspace_id: Optional[str] = None) -> dict:
    key = get_plan_key_for_workspace(workspace_id)
    spec = PLANS[key]
    return {
        "plan": key,
        "rank": PLAN_ORDER.index(key),
        "label": spec["label"],
        "price_hint": spec["price_hint"],
        "blurb": spec["blurb"],
        "features": spec["features"],
        "limits": spec["limits"],
    }


def all_plans() -> list:
    """Every tier, cheapest first — for the pricing/upgrade UI."""
    out = []
    for key in PLAN_ORDER:
        spec = PLANS[key]
        out.append({
            "plan": key, "rank": PLAN_ORDER.index(key),
            "label": spec["label"], "price_hint": spec["price_hint"],
            "blurb": spec["blurb"], "features": spec["features"], "limits": spec["limits"],
        })
    return out


def plan_allows(feature: str, workspace_id: Optional[str] = None) -> bool:
    return bool(PLANS[get_plan_key_for_workspace(workspace_id)]["features"].get(feature))


def require_feature(feature: str, workspace_id: Optional[str] = None) -> None:
    """Raise 402 when the workspace's plan lacks *feature*."""
    if not plan_allows(feature, workspace_id):
        key = get_plan_key_for_workspace(workspace_id)
        label = FEATURE_LABELS.get(feature, feature)
        raise HTTPException(
            status_code=402,
            detail=(
                f"{label} requires the Institution plan (current plan: {key}). "
                f"Upgrade at /billing."
            ),
        )


# ── Usage quotas ────────────────────────────────────────────────────────────

def count_sessions(workspace_id: str) -> int:
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("SELECT COUNT(*) AS n FROM debates WHERE workspace_id = %s", (workspace_id,))
        return int(cur.fetchone()["n"])


def count_materials(debate_id: str) -> int:
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("SELECT COUNT(*) AS n FROM meeting_materials WHERE debate_id = %s", (debate_id,))
        return int(cur.fetchone()["n"])


def require_session_quota(workspace_id: str) -> None:
    """Raise 402 when creating another review session would exceed the plan."""
    limit = get_plan(workspace_id)["limits"]["max_sessions"]
    if limit is None:
        return
    if count_sessions(workspace_id) >= limit:
        key = get_plan_key_for_workspace(workspace_id)
        raise HTTPException(
            status_code=402,
            detail=(
                f"Your {key} plan allows {limit} review sessions. "
                f"Upgrade at /billing to create more."
            ),
        )


def require_material_quota(debate_id: str, workspace_id: str, adding: int = 1) -> None:
    """Raise 402 when adding *adding* materials would exceed the per-session cap."""
    limit = get_plan(workspace_id)["limits"]["max_materials_per_session"]
    if limit is None:
        return
    if count_materials(debate_id) + adding > limit:
        key = get_plan_key_for_workspace(workspace_id)
        raise HTTPException(
            status_code=402,
            detail=(
                f"Your {key} plan allows {limit} materials per session. "
                f"Upgrade at /billing to add more."
            ),
        )


def usage_summary(workspace_id: str) -> dict:
    """Current consumption vs the workspace's limits, for the billing page."""
    plan = get_plan(workspace_id)
    return {
        "sessions": {
            "used": count_sessions(workspace_id),
            "limit": plan["limits"]["max_sessions"],
        },
        "materials_per_session_limit": plan["limits"]["max_materials_per_session"],
    }


# ── Stripe subscription linkage ─────────────────────────────────────────────

def plan_for_price_id(price_id: str) -> Optional[str]:
    """Reverse the STRIPE_PRICE_IDS map (plan → price) so a subscription event
    that carries only a Stripe price can be mapped back to a plan tier."""
    if not price_id:
        return None
    for plan_key, pid in (getattr(settings, "stripe_price_ids", None) or {}).items():
        if pid == price_id and plan_key in PLANS:
            return plan_key
    return None


def find_workspace_by_subscription(subscription_id: str) -> Optional[str]:
    if not subscription_id:
        return None
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            "SELECT workspace_id FROM workspaces WHERE stripe_subscription_id = %s",
            (subscription_id,),
        )
        row = cur.fetchone()
    return str(row["workspace_id"]) if row else None


def find_workspace_by_customer(customer_id: str) -> Optional[str]:
    if not customer_id:
        return None
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            "SELECT workspace_id FROM workspaces WHERE stripe_customer_id = %s "
            "ORDER BY plan_updated_at DESC NULLS LAST LIMIT 1",
            (customer_id,),
        )
        row = cur.fetchone()
    return str(row["workspace_id"]) if row else None


def stored_subscription_id(workspace_id: str) -> Optional[str]:
    """The Stripe subscription currently linked to this workspace (or None).
    Used to reject webhook events for a stale/foreign subscription."""
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            "SELECT stripe_subscription_id FROM workspaces WHERE workspace_id = %s",
            (workspace_id,),
        )
        row = cur.fetchone()
    return (row["stripe_subscription_id"] if row and row["stripe_subscription_id"] else None)


def billing_state(workspace_id: str) -> dict:
    """Subscription health for the billing UI: status, renewal date, and
    whether a Stripe subscription is linked (so 'Manage subscription' shows)."""
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            "SELECT plan_status, plan_renews_at, plan_source, stripe_subscription_id "
            "FROM workspaces WHERE workspace_id = %s",
            (workspace_id,),
        )
        row = cur.fetchone()
    if not row:
        return {"status": None, "renews_at": None, "has_subscription": False, "source": None}
    return {
        "status": row["plan_status"],
        "renews_at": row["plan_renews_at"].isoformat() if row["plan_renews_at"] else None,
        "has_subscription": bool(row["stripe_subscription_id"]),
        "source": row["plan_source"],
    }


# ── Plan mutation (owner action + webhook) ──────────────────────────────────

def set_workspace_plan(
    workspace_id: str,
    plan_key: str,
    source: str = "manual",
    *,
    customer_id: Optional[str] = None,
    subscription_id: Optional[str] = None,
    status: Optional[str] = None,
    renews_at=None,
    clear_subscription: bool = False,
) -> dict:
    """Persist a workspace's plan and, optionally, its Stripe linkage.

    Only the Stripe fields that are provided are updated (so a plain plan
    switch doesn't wipe an existing subscription link). `clear_subscription`
    nulls the subscription id — used when a subscription is deleted.
    Callers enforce authz; the webhook calls this directly.
    """
    key = (plan_key or "").strip().lower()
    if key not in PLANS:
        raise HTTPException(status_code=400, detail=f"Unknown plan '{plan_key}'")

    sets = ["plan = %s", "plan_updated_at = now()", "plan_source = %s"]
    params: list = [key, source]
    if customer_id is not None:
        sets.append("stripe_customer_id = %s"); params.append(customer_id)
    if clear_subscription:
        sets.append("stripe_subscription_id = NULL")
    elif subscription_id is not None:
        sets.append("stripe_subscription_id = %s"); params.append(subscription_id)
    if status is not None:
        sets.append("plan_status = %s"); params.append(status)
    if renews_at is not None:
        sets.append("plan_renews_at = %s"); params.append(renews_at)
    params.append(workspace_id)

    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("SELECT 1 FROM workspaces WHERE workspace_id = %s", (workspace_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Workspace not found")
        cur.execute(f"UPDATE workspaces SET {', '.join(sets)} WHERE workspace_id = %s", tuple(params))
        conn.commit()
    return get_plan(workspace_id)
