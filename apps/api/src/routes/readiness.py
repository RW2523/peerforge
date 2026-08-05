"""
Deployment readiness
====================
GET /readiness — what is configured, what is not, and what each gap costs.

Nothing else answers "is this safe to put in front of real users". Checks are
grouped by whether they block a public launch or merely degrade a feature, so
the answer is actionable rather than a wall of booleans.
"""
from typing import Any, Dict, List

from fastapi import APIRouter

from ..config import settings
from ..database import get_cursor, get_db_connection, pool_stats

router = APIRouter(tags=["readiness"])

PLACEHOLDER_JWT_SECRET = "your-jwt-secret-here"


def _check(name: str, ok: bool, blocking: bool, detail: str, fix: str = "") -> Dict[str, Any]:
    """
    One readiness line.

    `detail` describes the FAILURE, and it was printed regardless of `ok` — so a
    passing check read as a problem beside "ok": true, and an operator scanning
    the page could not tell which lines needed action. A passing check says so.
    """
    return {
        "name": name,
        "ok": ok,
        "severity": ("blocking" if blocking else "degraded") if not ok else "ok",
        "detail": detail if not ok else "OK",
        "fix": fix if not ok else "",
    }


@router.get("/readiness")
async def readiness() -> Dict[str, Any]:
    """Configuration and infrastructure readiness for a public deployment."""
    checks: List[Dict[str, Any]] = []

    # ── Authentication ──────────────────────────────────────────────────
    checks.append(_check(
        "authentication",
        settings.require_auth,
        blocking=True,
        detail="Auth is disabled: every visitor is the same user and shares one workspace.",
        fix="Set REQUIRE_AUTH=true and a real SUPABASE_JWT_SECRET.",
    ))

    secret_ok = settings.supabase_jwt_secret != PLACEHOLDER_JWT_SECRET and len(
        settings.supabase_jwt_secret or ""
    ) >= 32
    checks.append(_check(
        "jwt_secret",
        secret_ok,
        blocking=True,
        detail="The JWT secret is the placeholder or too short to be safe.",
        fix="Set SUPABASE_JWT_SECRET to the value from your Supabase project.",
    ))

    cors_locked = "*" not in [o.strip() for o in settings.cors_allow_origins.split(",")]
    checks.append(_check(
        "cors",
        cors_locked,
        blocking=False,
        detail="CORS allows any origin. Credentialed requests are disabled as a result.",
        fix="Set CORS_ALLOW_ORIGINS to your frontend's URL.",
    ))

    checks.append(_check(
        "key_encryption",
        bool(settings.key_encryption_secret),
        blocking=False,
        detail="Users cannot save an API key to their account; keys are refused rather than stored unencrypted.",
        fix="Set KEY_ENCRYPTION_SECRET to a Fernet key.",
    ))

    # ── Delivery ────────────────────────────────────────────────────────
    has_mail = bool(settings.smtp_host) or bool(
        settings.supabase_service_role_key and settings.supabase_url
    )
    checks.append(_check(
        "invitation_email",
        has_mail,
        blocking=False,
        detail="Invitations are created but not sent; links must be shared by hand.",
        fix="Set SMTP_HOST, or SUPABASE_SERVICE_ROLE_KEY to use Supabase invites.",
    ))

    # ── Infrastructure ──────────────────────────────────────────────────
    db_ok, db_detail = _database_reachable()
    checks.append(_check(
        "database", db_ok, blocking=True,
        detail=db_detail, fix="Check DATABASE_URL and that Postgres is running.",
    ))

    worker_ok, worker_detail = _worker_running()
    checks.append(_check(
        "background_worker", worker_ok, blocking=False,
        detail=worker_detail,
        fix="Start a Celery worker with -Q celery,materials,preflight, or set CELERY_TASK_ALWAYS_EAGER=true.",
    ))

    embed_ok, embed_detail = _embeddings_healthy()
    checks.append(_check(
        "embeddings", embed_ok, blocking=False,
        detail=embed_detail,
        fix=(
            # Told the operator to set a key that was already set. When one is
            # configured, an unembedded chunk means the job did not run or
            # failed, and the worker log is where the answer is.
            "Check the Celery worker is running with -Q celery,materials and read "
            "celery.log: material was accepted but its embedding job did not "
            "complete."
            if (settings.openrouter_api_key or "").strip()
            else "Set OPENROUTER_API_KEY so uploaded material can be embedded."
        ),
    ))

    blocking = [c for c in checks if c["severity"] == "blocking"]
    degraded = [c for c in checks if c["severity"] == "degraded"]

    return {
        "ready_for_public_launch": not blocking,
        "summary": {
            "passing": sum(1 for c in checks if c["ok"]),
            "blocking": len(blocking),
            "degraded": len(degraded),
        },
        "checks": checks,
        "connection_pool": pool_stats(),
    }


def _database_reachable():
    try:
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute("SELECT 1 AS ok")
            cursor.fetchone()
        return True, "Reachable."
    except Exception as exc:
        return False, f"Unreachable: {exc}"


def _worker_running():
    """Ask the broker which workers have checked in."""
    try:
        from ..celery_app import celery_app

        replies = celery_app.control.ping(timeout=1.0)
        if replies:
            return True, f"{len(replies)} worker(s) responding."
        return False, "No worker responded: uploads are never processed and stay queued."
    except Exception as exc:
        return False, f"Could not reach the broker: {exc}"


def _embeddings_healthy():
    """Chunks stuck at not_started mean retrieval falls back to keywords."""
    try:
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute(
                """SELECT embedding_status, COUNT(*) AS n
                   FROM memory_chunks GROUP BY embedding_status"""
            )
            counts = {r["embedding_status"]: r["n"] for r in cursor.fetchall()}
    except Exception as exc:
        return False, f"Could not check: {exc}"

    total = sum(counts.values())
    if total == 0:
        return True, "No material uploaded yet."

    complete = counts.get("complete", 0)
    if complete == total:
        return True, f"All {total} chunks embedded."
    return False, (
        f"{total - complete} of {total} chunks are not embedded "
        f"({', '.join(f'{k}: {v}' for k, v in sorted(counts.items()))}). "
        "Retrieval falls back to keyword matching."
    )
