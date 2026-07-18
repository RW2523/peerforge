"""Stripe subscription → workspace mapping, shared by the webhook and the
nightly reconciler.
========================================================================
Both the webhook (routes/billing.py) and the reconciliation job must turn a
Stripe subscription object into a workspace's intended plan/status. That
mapping lives here so the two paths can never drift apart.

The reconciler (`reconcile_all`) pulls the LIVE subscription for every linked
workspace and repairs any state a missed/failed webhook left behind — Stripe
only retries a webhook for ~3 days, so a longer outage can leave a workspace
on the wrong tier until this sweep corrects it.
"""
import logging
from typing import Optional

from ..config import settings
from ..database import get_db_connection, get_cursor
from .plans import get_plan, plan_for_price_id, set_workspace_plan

logger = logging.getLogger(__name__)

# Stripe statuses that end entitlement → downgrade to the free tier.
DEAD_SUB_STATUSES = {"canceled", "unpaid", "incomplete_expired"}
# Statuses that DO grant the paid plan (allowlist — 'incomplete'/'paused'/etc.
# never entitle).
ENTITLING_STATUSES = {"active", "trialing"}

# Circuit breaker for the reconciler: a wrong/mismatched Stripe key (test key
# against live objects, wrong account) makes EVERY subscription look
# 'resource_missing'. Refuse to mass-downgrade on that signal — abort the run
# without applying anything if too many subscriptions report missing at once.
_MISSING_ABORT_ABS = 10        # absolute floor before the ratio is considered
_MISSING_ABORT_FRACTION = 0.5  # ...and >50% of the checked set reported missing


def subscription_price_id(sub: dict) -> Optional[str]:
    items = ((sub.get("items") or {}).get("data")) or []
    return (items[0].get("price") or {}).get("id") if items else None


def period_end_dt(sub: dict):
    ts = sub.get("current_period_end")
    if not ts:
        return None
    from datetime import datetime, timezone
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def map_subscription(sub: dict) -> dict:
    """Pure: a Stripe subscription object → the workspace's intended state.
    Returns {"kind": ...} where kind is one of:
      downgrade | canceling | active | past_due | unmapped | non_entitling.
    Prefers the LIVE price over stale checkout metadata."""
    status = sub.get("status")
    if status in DEAD_SUB_STATUSES:
        return {"kind": "downgrade"}
    price_id = subscription_price_id(sub)
    plan = plan_for_price_id(price_id) if price_id else (sub.get("metadata") or {}).get("plan")
    renews = period_end_dt(sub)
    if sub.get("cancel_at_period_end"):
        return {"kind": "canceling", "plan": plan, "renews": renews}
    if plan is None:
        return {"kind": "unmapped", "price_id": price_id}
    if status in ENTITLING_STATUSES:
        return {"kind": "active", "plan": plan, "renews": renews}
    if status == "past_due":
        return {"kind": "past_due", "plan": plan, "renews": renews}
    return {"kind": "non_entitling", "status": status}


def intended_state(workspace_id: str, dec: dict) -> tuple:
    """The (plan, status) a decision implies, or (None, None) when it means
    'leave unchanged'. Lets the reconciler detect drift without writing."""
    kind = dec["kind"]
    if kind == "downgrade":
        return ("community", "canceled")
    if kind == "canceling":
        return (dec["plan"] or get_plan(workspace_id)["plan"], "canceling")
    if kind == "active":
        return (dec["plan"], "active")
    if kind == "past_due":
        return (dec["plan"], "past_due")
    return (None, None)  # unmapped / non_entitling → no change


def apply_decision(workspace_id: str, sub_id: Optional[str], dec: dict, *, source: str = "stripe") -> None:
    """Write a mapping decision to the workspace. Shared by the webhook and the
    reconciler so both produce identical outcomes."""
    kind = dec["kind"]
    if kind == "downgrade":
        set_workspace_plan(workspace_id, "community", source=source, status="canceled", clear_subscription=True)
    elif kind == "canceling":
        keep = dec["plan"] or get_plan(workspace_id)["plan"]
        set_workspace_plan(workspace_id, keep, source=source, subscription_id=sub_id,
                           status="canceling", renews_at=dec["renews"])
    elif kind == "active":
        set_workspace_plan(workspace_id, dec["plan"], source=source, subscription_id=sub_id,
                           status="active", renews_at=dec["renews"])
    elif kind == "past_due":
        set_workspace_plan(workspace_id, dec["plan"], source=source, subscription_id=sub_id,
                           status="past_due", renews_at=dec["renews"])
    elif kind == "unmapped":
        logger.warning("Unmapped Stripe price %s; leaving workspace %s plan unchanged",
                       dec.get("price_id"), workspace_id)
    else:  # non_entitling
        logger.info("Non-entitling Stripe status %r; leaving workspace %s unchanged",
                    dec.get("status"), workspace_id)


def _is_missing_subscription(exc: Exception) -> bool:
    """True when Stripe reports the subscription no longer exists. Requires the
    InvalidRequestError class so an unrelated error whose message merely
    contains the phrase can't be mistaken for a cancellation."""
    if exc.__class__.__name__ != "InvalidRequestError":
        return False
    if getattr(exc, "code", None) == "resource_missing":
        return True
    return "No such subscription" in str(exc)


def reconcile_all(limit: Optional[int] = None) -> dict:
    """Nightly job: fetch the live subscription for every linked workspace and
    repair drift a missed webhook would leave. Idempotent and safe to run any
    time. No-op when Stripe isn't configured."""
    if not (settings.stripe_secret_key or "").strip():
        return {"skipped": "stripe_not_configured", "checked": 0, "corrected": 0, "errors": 0}
    try:
        import stripe
    except ImportError:
        return {"skipped": "stripe_lib_missing", "checked": 0, "corrected": 0, "errors": 0}
    stripe.api_key = settings.stripe_secret_key

    with get_db_connection() as conn:
        cur = get_cursor(conn)
        sql = ("SELECT workspace_id, stripe_subscription_id, plan, plan_status "
               "FROM workspaces WHERE stripe_subscription_id IS NOT NULL")
        if limit:
            sql += " LIMIT %s"
            cur.execute(sql, (limit,))
        else:
            cur.execute(sql)
        rows = cur.fetchall()

    # Pass 1 — classify every workspace against Stripe WITHOUT writing, so a
    # systemic auth/mode failure can be detected before any downgrade lands.
    checked = missing = errors = 0
    pending = []  # (ws, sub_id, decision, current) — corrections to apply
    for row in rows:
        ws = str(row["workspace_id"])
        sub_id = row["stripe_subscription_id"]
        current = (row["plan"], row["plan_status"])
        checked += 1
        try:
            sub = stripe.Subscription.retrieve(sub_id)
        except Exception as exc:  # noqa: BLE001 — Stripe raises many error types
            if _is_missing_subscription(exc):
                missing += 1
                if current != ("community", "canceled"):
                    pending.append((ws, sub_id, {"kind": "downgrade"}, current))
            else:
                errors += 1
                logger.warning("Reconcile: could not fetch subscription %s for workspace %s: %s", sub_id, ws, exc)
            continue

        dec = map_subscription(sub)
        want = intended_state(ws, dec)
        if want[0] is None:
            continue  # unmapped / non-entitling → leave as-is (logged elsewhere)
        if current != want:
            pending.append((ws, sub_id, dec, current))

    # Circuit breaker: if a large share of subscriptions report missing at once,
    # that is almost certainly a Stripe key/mode misconfiguration, not a wave of
    # real cancellations — abort without downgrading anyone.
    if missing >= _MISSING_ABORT_ABS and missing >= _MISSING_ABORT_FRACTION * max(checked, 1):
        logger.critical(
            "Billing reconcile ABORTED: %d/%d subscriptions reported missing — likely a Stripe "
            "key/mode misconfiguration. No changes applied.", missing, checked,
        )
        return {"aborted": True, "reason": "too_many_missing",
                "checked": checked, "missing": missing, "corrected": 0, "errors": errors}

    # Pass 2 — apply the corrections.
    corrected = 0
    for ws, sub_id, dec, current in pending:
        apply_decision(ws, sub_id, dec)
        corrected += 1
        logger.info("Reconcile: workspace %s %s/%s → %s", ws, current[0], current[1], dec["kind"])

    result = {"checked": checked, "corrected": corrected, "errors": errors, "missing": missing}
    logger.info("Billing reconcile complete: %s", result)
    return result
