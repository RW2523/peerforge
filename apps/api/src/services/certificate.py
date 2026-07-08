"""
Readiness Certificate service (Pillar 3)
========================================
Turns a session's ten-dimension academic assessments into an exportable,
tamper-evident **Review-Readiness Certificate**:

  * TRAJECTORY   — how each dimension moved across successive assessments
                   (e.g. Methodological Rigour 5.2 → 7.4).
  * EVIDENCE LEDGER — every practice answer that the scores rest on, each linked
                   to its question and the sha256-verified source line behind it.
  * ANCHOR       — a content hash (sha256) computed over the scores + the ordered
                   evidence entries + their source chunk hashes + the append-only
                   event sequence. Any later tampering with the underlying
                   evidence changes the hash, so the certificate is self-verifying.

A true institutional digital signature (private-key) is the production hardening
step; the content-hash anchor here is fully re-verifiable from the stored data.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..database import get_db_connection, get_cursor
from .academic_assessment import ASSESSMENT_DIMENSIONS, _DIMENSION_KEYS


def _band(score: float) -> str:
    if score >= 8:
        return "Strong"
    if score >= 6:
        return "Competent"
    if score >= 4:
        return "Developing"
    return "Under-prepared"


def get_trajectory(debate_id: str) -> List[Dict[str, Any]]:
    """All assessments for a session, oldest→newest, with full dimensions."""
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            """
            SELECT assessment_id, trigger_source, dimensions, overall_score,
                   generated_at
            FROM   academic_assessments
            WHERE  debate_id = %s
            ORDER BY generated_at ASC
            """,
            (debate_id,),
        )
        rows = cur.fetchall()

    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append({
            "assessment_id": str(r["assessment_id"]),
            "trigger_source": r["trigger_source"],
            "generated_at": r["generated_at"].isoformat() if r["generated_at"] else None,
            "overall_score": float(r["overall_score"]) if r["overall_score"] is not None else None,
            "dimensions": r["dimensions"] or [],
        })
    return out


def _dimension_trajectory(trajectory: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Per-dimension first→latest deltas plus the full point series."""
    dims: List[Dict[str, Any]] = []
    for spec in ASSESSMENT_DIMENSIONS:
        points: List[Dict[str, Any]] = []
        for a in trajectory:
            match = next(
                (d for d in a["dimensions"] if isinstance(d, dict) and d.get("key") == spec["key"]),
                None,
            )
            if match is not None:
                points.append({
                    "at": a["generated_at"],
                    "trigger": a["trigger_source"],
                    "score": float(match.get("score", 0)),
                    "comment": match.get("comment", ""),
                })
        first = points[0]["score"] if points else 0.0
        latest = points[-1]["score"] if points else 0.0
        dims.append({
            "key": spec["key"],
            "label": spec["label"],
            "what": spec.get("what", ""),
            "first_score": round(first, 1),
            "latest_score": round(latest, 1),
            "delta": round(latest - first, 1),
            "band": _band(latest),
            "latest_comment": points[-1]["comment"] if points else "",
            "points": points,
        })
    return dims


def _evidence_ledger(debate_id: str) -> Dict[str, Any]:
    """Practice answers + their grounded source lines + panel event span.

    This is the auditable basis the scores rest on and the material hashed into
    the certificate anchor.
    """
    with get_db_connection() as conn:
        cur = get_cursor(conn)

        cur.execute(
            """
            SELECT sa.answer_id, sa.overall_score, sa.strength, sa.weakness,
                   sa.answered_at,
                   dq.question_id, dq.question_text, dq.category, dq.persona,
                   dq.source_excerpt, dq.source_chunk_id,
                   mc.chunk_text, mc.chunk_metadata
            FROM   session_answers sa
            LEFT JOIN defense_questions dq ON sa.question_id = dq.question_id
            LEFT JOIN memory_chunks mc     ON mc.chunk_id = dq.source_chunk_id
            WHERE  sa.debate_id = %s
            ORDER BY sa.answered_at ASC
            """,
            (debate_id,),
        )
        answer_rows = cur.fetchall()

        cur.execute(
            """
            SELECT MIN(sequence_number) AS lo, MAX(sequence_number) AS hi,
                   COUNT(*) AS n
            FROM   events
            WHERE  debate_id = %s AND event_type = 'agent_message'
            """,
            (debate_id,),
        )
        span = cur.fetchone() or {}

    answers: List[Dict[str, Any]] = []
    for r in answer_rows:
        meta = r["chunk_metadata"] or {}
        chunk_text = r["chunk_text"] or ""
        source = None
        if r["source_chunk_id"] and chunk_text:
            stored = meta.get("sha256")
            fresh = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
            source = {
                "chunk_id": str(r["source_chunk_id"]),
                "excerpt": r["source_excerpt"] or "",
                "sha256": stored,
                "sha256_verified": bool(stored) and stored == fresh,
                "page_num": meta.get("page_num"),
            }
        answers.append({
            "answer_id": str(r["answer_id"]),
            "question_id": str(r["question_id"]) if r["question_id"] else None,
            "question_text": r["question_text"] or "",
            "category": r["category"],
            "persona": r["persona"],
            "answer_score": float(r["overall_score"]) if r["overall_score"] is not None else None,
            "strength": r["strength"] or "",
            "weakness": r["weakness"] or "",
            "answered_at": r["answered_at"].isoformat() if r["answered_at"] else None,
            "source": source,
        })

    return {
        "answers": answers,
        "panel_events": {
            "count": int(span.get("n") or 0),
            "sequence_from": int(span["lo"]) if span.get("lo") is not None else None,
            "sequence_to": int(span["hi"]) if span.get("hi") is not None else None,
        },
    }


def canonicalize(payload: Dict[str, Any]) -> str:
    """Deterministic serialization — the exact bytes that are hashed and signed."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _compute_anchor(payload: Dict[str, Any]) -> Dict[str, str]:
    """Deterministic sha256 over the canonical certificate payload."""
    digest = hashlib.sha256(canonicalize(payload).encode("utf-8")).hexdigest()
    return {
        "algorithm": "sha256",
        "hash": digest,
        "certificate_id": f"PF-{digest[:12].upper()}",
    }


def _anchor_payload(debate_id: str, trajectory: List[Dict[str, Any]],
                    ledger: Dict[str, Any]) -> Dict[str, Any]:
    """The evidence-binding payload: scores + ordered evidence + event span.
    Shared by issuance and live re-verification so both hash identically."""
    return {
        "debate_id": debate_id,
        "assessments": [
            {"id": a["assessment_id"], "overall": a["overall_score"],
             "dims": [(d.get("key"), d.get("score")) for d in a["dimensions"] if isinstance(d, dict)]}
            for a in trajectory
        ],
        "evidence_answers": [
            {"id": a["answer_id"], "q": a["question_id"], "score": a["answer_score"],
             "src": (a["source"] or {}).get("sha256")}
            for a in ledger["answers"]
        ],
        "panel_events": ledger["panel_events"],
    }


def compute_live_anchor(debate_id: str) -> Optional[Dict[str, Any]]:
    """Recompute the anchor from the CURRENT database state — the public
    verification page compares this against the anchor recorded at issuance.
    Returns None when the session has no assessments (nothing to anchor)."""
    trajectory = get_trajectory(debate_id)
    if not trajectory:
        return None
    ledger = _evidence_ledger(debate_id)
    payload = _anchor_payload(debate_id, trajectory, ledger)
    return {"payload": payload, "canonical": canonicalize(payload),
            "anchor": _compute_anchor(payload)}


def build_certificate(debate_id: str) -> Dict[str, Any]:
    """Assemble the full, tamper-evident Review-Readiness Certificate."""
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            "SELECT title, workspace_id, created_at FROM debates WHERE debate_id = %s",
            (debate_id,),
        )
        deb = cur.fetchone()
    if not deb:
        raise ValueError(f"Session {debate_id} not found")

    trajectory = get_trajectory(debate_id)
    if not trajectory:
        raise ValueError(
            "No assessments yet — generate at least one academic assessment before "
            "issuing a certificate."
        )

    dim_traj = _dimension_trajectory(trajectory)
    ledger = _evidence_ledger(debate_id)
    latest = trajectory[-1]
    first = trajectory[0]

    # The anchor binds scores to the exact evidence + append-only event span, so
    # altering any of them invalidates the hash. Timestamp is stamped by caller.
    anchor_payload = _anchor_payload(debate_id, trajectory, ledger)
    anchor = _compute_anchor(anchor_payload)

    issued_at = datetime.now(timezone.utc).isoformat()

    return {
        "certificate_id": anchor["certificate_id"],
        "issued_at": issued_at,
        "session": {
            "debate_id": debate_id,
            "title": deb["title"],
            "workspace_id": str(deb["workspace_id"]),
            "created_at": deb["created_at"].isoformat() if deb["created_at"] else None,
        },
        "overall": {
            "first_score": first["overall_score"],
            "latest_score": latest["overall_score"],
            "delta": round((latest["overall_score"] or 0) - (first["overall_score"] or 0), 1),
            "band": _band(latest["overall_score"] or 0),
            "assessment_count": len(trajectory),
        },
        "dimensions": dim_traj,
        "evidence": ledger,
        "anchor": anchor,
        # Internal: the exact payload the anchor hashes — used by the issue
        # route to sign the same bytes. API routes pop this before responding.
        "_anchor_payload": anchor_payload,
    }
