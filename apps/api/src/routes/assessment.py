"""
Academic Assessment Matrix — API routes
=======================================
POST /debates/{id}/assessment/generate  → build a fresh ten-dimension assessment
GET  /debates/{id}/assessment           → latest assessment
GET  /debates/{id}/assessment/history   → prior overall scores (progress over time)
"""
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from typing import Literal

from ..auth import require_auth
from ..services.academic_assessment import (
    generate_assessment,
    get_latest_assessment,
    get_assessment_history,
)
from ..services.certificate import build_certificate

router = APIRouter(tags=["assessment"])


class GenerateAssessmentRequest(BaseModel):
    mode: Literal["light", "medium", "heavy"] = "light"
    trigger_source: str = "manual"
    model_id: str = ""


@router.post("/debates/{debate_id}/assessment/generate")
async def create_assessment(
    debate_id: str,
    request: GenerateAssessmentRequest,
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
    _workspace_id: str = Depends(require_auth),
):
    """Generate the ten-dimension academic assessment from all session evidence."""
    if not x_openrouter_key:
        raise HTTPException(
            status_code=400,
            detail="X-OpenRouter-Key header is required for this operation",
        )
    try:
        return generate_assessment(
            debate_id=debate_id,
            openrouter_key=x_openrouter_key,
            mode=request.mode,
            trigger_source=request.trigger_source,
            model_id=request.model_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/debates/{debate_id}/assessment")
async def latest_assessment(
    debate_id: str,
    _workspace_id: str = Depends(require_auth),
):
    """Return the most recent assessment for this session."""
    result = get_latest_assessment(debate_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No assessment yet. Generate one via POST /debates/{id}/assessment/generate",
        )
    return result


@router.get("/debates/{debate_id}/assessment/history")
async def assessment_history(
    debate_id: str,
    _workspace_id: str = Depends(require_auth),
):
    """Return prior assessments (newest first) for progress tracking."""
    return {"debate_id": debate_id, "assessments": get_assessment_history(debate_id)}


@router.get("/debates/{debate_id}/certificate")
async def readiness_certificate(
    debate_id: str,
    _workspace_id: str = Depends(require_auth),
):
    """Assemble the tamper-evident Review-Readiness Certificate: per-dimension
    trajectory, the evidence ledger it rests on, and a sha256 ledger anchor."""
    try:
        cert = build_certificate(debate_id)
        cert.pop("_anchor_payload", None)
        # Surface the already-issued signed record, if any, so the UI can show
        # the share/verify link without re-issuing.
        from ..database import get_db_connection, get_cursor
        with get_db_connection() as conn:
            cur = get_cursor(conn)
            cur.execute(
                "SELECT certificate_id, issued_at FROM issued_certificates "
                "WHERE certificate_id = %s",
                (cert["anchor"]["certificate_id"],),
            )
            row = cur.fetchone()
        cert["issued"] = bool(row)
        return cert
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/debates/{debate_id}/certificate/issue")
async def issue_certificate(
    debate_id: str,
    _workspace_id: str = Depends(require_auth),
):
    """Issue a signed certificate: Ed25519 signature over the canonical anchor
    payload, persisted immutably so anyone can verify it at /verify/{id}.
    Idempotent — re-issuing the same evidence state returns the same record."""
    from ..services.certificate import canonicalize
    from ..services.cert_signing import sign_canonical
    from ..database import get_db_connection, get_cursor

    try:
        cert = build_certificate(debate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    payload = cert.pop("_anchor_payload")
    canonical = canonicalize(payload)
    key_id, signature, public_pem = sign_canonical(canonical)
    certificate_id = cert["anchor"]["certificate_id"]

    # Public summary snapshot: readiness only — no manuscript content, no
    # answer texts. This is what the public verify page displays.
    summary = {
        "title": cert["session"]["title"],
        "overall": cert["overall"],
        "dimensions": [
            {k: d[k] for k in ("key", "label", "first_score", "latest_score", "delta", "band")}
            for d in cert["dimensions"]
        ],
        "evidence_counts": {
            "answers": len(cert["evidence"]["answers"]),
            "panel_events": cert["evidence"]["panel_events"]["count"],
        },
    }

    import json as _json
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            """
            INSERT INTO issued_certificates (
                certificate_id, debate_id, workspace_id, anchor_hash,
                algorithm, signature, key_id, payload, summary
            ) VALUES (%s, %s, %s, %s, 'ed25519+sha256', %s, %s, %s, %s)
            ON CONFLICT (certificate_id) DO NOTHING
            """,
            (certificate_id, debate_id, cert["session"]["workspace_id"],
             cert["anchor"]["hash"], signature, key_id,
             _json.dumps(payload), _json.dumps(summary)),
        )
        conn.commit()
        cur.execute(
            "SELECT issued_at FROM issued_certificates WHERE certificate_id = %s",
            (certificate_id,),
        )
        row = cur.fetchone()

    return {
        "certificate_id": certificate_id,
        "issued_at": row["issued_at"].isoformat() if row else None,
        "anchor_hash": cert["anchor"]["hash"],
        "algorithm": "ed25519+sha256",
        "key_id": key_id,
        "verify_path": f"/verify/{certificate_id}",
    }


@router.get("/workspaces/{workspace_id}/readiness-overview")
async def readiness_overview(
    workspace_id: str,
    _workspace_id: str = Depends(require_auth),
):
    """Cohort view (Phase 3): every session with an assessment trajectory —
    first/latest overall score, band, evidence counts, and the issued
    certificate (if any) so an advisor or program can scan readiness at a
    glance and jump to verification."""
    if workspace_id != _workspace_id:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")

    from ..database import get_db_connection, get_cursor
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            """
            WITH ranked AS (
                SELECT debate_id, overall_score, generated_at,
                       ROW_NUMBER() OVER (PARTITION BY debate_id ORDER BY generated_at ASC)  AS rn_first,
                       ROW_NUMBER() OVER (PARTITION BY debate_id ORDER BY generated_at DESC) AS rn_last,
                       COUNT(*)     OVER (PARTITION BY debate_id) AS n
                FROM academic_assessments
                WHERE workspace_id = %s
            )
            SELECT d.debate_id, d.title, d.state, d.created_at,
                   f.overall_score  AS first_score,
                   l.overall_score  AS latest_score,
                   l.generated_at   AS last_assessed_at,
                   f.n              AS assessment_count,
                   (SELECT COUNT(*) FROM session_answers sa WHERE sa.debate_id = d.debate_id) AS answer_count,
                   ic.certificate_id, ic.issued_at
            FROM debates d
            JOIN ranked f ON f.debate_id = d.debate_id AND f.rn_first = 1
            JOIN ranked l ON l.debate_id = d.debate_id AND l.rn_last = 1
            LEFT JOIN LATERAL (
                SELECT certificate_id, issued_at FROM issued_certificates
                WHERE debate_id = d.debate_id ORDER BY issued_at DESC LIMIT 1
            ) ic ON TRUE
            WHERE d.workspace_id = %s
            ORDER BY l.generated_at DESC
            """,
            (workspace_id, workspace_id),
        )
        rows = cur.fetchall()

    def band(score):
        if score is None:
            return None
        if score >= 8:
            return "Strong"
        if score >= 6:
            return "Competent"
        if score >= 4:
            return "Developing"
        return "Under-prepared"

    sessions = []
    for r in rows:
        first = float(r["first_score"]) if r["first_score"] is not None else None
        latest = float(r["latest_score"]) if r["latest_score"] is not None else None
        sessions.append({
            "debate_id": str(r["debate_id"]),
            "title": r["title"],
            "state": r["state"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "first_score": first,
            "latest_score": latest,
            "delta": round(latest - first, 1) if (first is not None and latest is not None) else None,
            "band": band(latest),
            "assessment_count": int(r["assessment_count"]),
            "answer_count": int(r["answer_count"]),
            "last_assessed_at": r["last_assessed_at"].isoformat() if r["last_assessed_at"] else None,
            "certificate_id": r["certificate_id"],
            "certificate_issued_at": r["issued_at"].isoformat() if r["issued_at"] else None,
        })

    return {"workspace_id": workspace_id, "sessions": sessions, "total": len(sessions)}


@router.get("/verify/{certificate_id}")
async def verify_certificate(certificate_id: str):
    """PUBLIC verification — no auth. Recomputes everything a relying party
    needs: signature validity, hash integrity of the issued payload, and
    whether the session's live evidence still matches the anchored state."""
    from ..services.certificate import canonicalize, compute_live_anchor
    from ..services.cert_signing import verify_signature
    from ..database import get_db_connection, get_cursor
    import hashlib as _hashlib

    with get_db_connection() as conn:
        cur = get_cursor(conn)
        # Explicit column list — this endpoint is public, so never select more
        # than it returns (and never anything from signing_keys but the public key).
        cur.execute(
            """
            SELECT ic.certificate_id, ic.debate_id, ic.issued_at, ic.algorithm,
                   ic.anchor_hash, ic.key_id, ic.signature, ic.payload, ic.summary,
                   sk.public_key
            FROM issued_certificates ic
            JOIN signing_keys sk ON sk.key_id = ic.key_id
            WHERE ic.certificate_id = %s
            """,
            (certificate_id,),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Certificate not found")

    canonical = canonicalize(row["payload"])
    hash_ok = _hashlib.sha256(canonical.encode("utf-8")).hexdigest() == row["anchor_hash"]
    sig_ok = verify_signature(row["public_key"], canonical, row["signature"])

    live_available, evidence_unchanged = False, None
    try:
        live = compute_live_anchor(str(row["debate_id"]))
        if live is not None:
            live_available = True
            evidence_unchanged = live["anchor"]["hash"] == row["anchor_hash"]
    except Exception:
        pass

    return {
        "certificate_id": certificate_id,
        "issued_at": row["issued_at"].isoformat(),
        "algorithm": row["algorithm"],
        "anchor_hash": row["anchor_hash"],
        "key_id": row["key_id"],
        "public_key": row["public_key"],
        "summary": row["summary"],
        "checks": {
            "signature_valid": sig_ok,
            "hash_matches_payload": hash_ok,
            "live_check_available": live_available,
            "evidence_unchanged_since_issue": evidence_unchanged,
        },
        "verdict": "VALID" if (sig_ok and hash_ok) else "INVALID",
    }
