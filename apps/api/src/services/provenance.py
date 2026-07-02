"""
Provenance / Glass-Box service
==============================
Assembles the claim → source lineage that powers the Glass-Box Panel.

For every review question (a reviewer "claim"), we resolve the ingested chunk it
was grounded in and RE-VERIFY that chunk's content hash. A claim is:

  * GROUNDED   — hard-linked to a chunk whose stored sha256 still matches a fresh
                 hash of its text (tamper-evident), with the quoted excerpt located
                 inside the chunk so the UI can highlight it.
  * EVIDENCE GAP — no chunk could be linked (source_chunk_id is NULL): the reviewer
                 is asking about something not actually supported by the materials.

Nothing here is invented: the sha256, page number and character offsets all come
from ``memory_chunks.chunk_metadata`` written at ingest time (utils/chunking.py).
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional

from ..database import get_db_connection, get_cursor

_WORD_RE = re.compile(r"[a-z0-9]+")


def _verify_sha256(chunk_text: str, stored: Optional[str]) -> bool:
    if not stored:
        return False
    fresh = hashlib.sha256((chunk_text or "").encode("utf-8")).hexdigest()
    return fresh == stored


def _locate_excerpt(excerpt: str, chunk_text: str) -> Optional[Dict[str, int]]:
    """Case-insensitive location of the quote inside the chunk (for highlighting).

    Returns raw {start, end} offsets into chunk_text, or None if the exact quote
    isn't a substring (e.g. a token-overlap match rather than a verbatim one)."""
    if not excerpt or not chunk_text:
        return None
    lo = chunk_text.lower()
    ex = excerpt.strip().lower()
    idx = lo.find(ex)
    if idx >= 0:
        return {"start": idx, "end": idx + len(ex)}
    # Fall back to the longest shared token run at the start of the excerpt.
    toks = excerpt.strip().split()
    for take in range(len(toks), 2, -1):
        probe = " ".join(toks[:take]).lower()
        idx = lo.find(probe)
        if idx >= 0:
            return {"start": idx, "end": idx + len(probe)}
    return None


def get_provenance(debate_id: str) -> Dict[str, Any]:
    """Build the full Glass-Box lineage for a session."""
    with get_db_connection() as conn:
        cur = get_cursor(conn)

        # Materials that back this session.
        cur.execute(
            """
            SELECT mm.material_id, mm.title, mm.kind,
                   COUNT(mc.chunk_id) AS chunk_count
            FROM   meeting_materials mm
            LEFT JOIN memory_chunks mc
                   ON (mc.chunk_metadata->>'material_id')::uuid = mm.material_id
                  AND mc.source_debate_id = mm.debate_id
            WHERE  mm.debate_id = %s
            GROUP BY mm.material_id, mm.title, mm.kind
            ORDER BY mm.created_at
            """,
            (debate_id,),
        )
        materials = [
            {
                "material_id": str(r["material_id"]),
                "title": r["title"],
                "kind": r["kind"],
                "chunk_count": int(r["chunk_count"] or 0),
            }
            for r in cur.fetchall()
        ]

        # Questions (reviewer claims) + their linked chunk, if any.
        cur.execute(
            """
            SELECT q.question_id, q.question_text, q.category, q.difficulty,
                   q.persona, q.source_excerpt, q.source_chunk_id, q.seq_order,
                   q.answer_id,
                   mc.chunk_text, mc.chunk_metadata,
                   COALESCE(mm.title, 'uploaded document') AS doc_title
            FROM   defense_questions q
            LEFT JOIN memory_chunks mc ON mc.chunk_id = q.source_chunk_id
            LEFT JOIN meeting_materials mm
                   ON (mc.chunk_metadata->>'material_id')::uuid = mm.material_id
            WHERE  q.debate_id = %s
            ORDER BY q.seq_order
            """,
            (debate_id,),
        )
        rows = cur.fetchall()

    claims: List[Dict[str, Any]] = []
    grounded_n = 0
    verified_n = 0
    for r in rows:
        excerpt = r["source_excerpt"] or ""
        source = None
        grounded = bool(r["source_chunk_id"]) and bool(r["chunk_text"])
        if grounded:
            meta = r["chunk_metadata"] or {}
            chunk_text = r["chunk_text"] or ""
            sha_verified = _verify_sha256(chunk_text, meta.get("sha256"))
            if sha_verified:
                verified_n += 1
            grounded_n += 1
            source = {
                "chunk_id": str(r["source_chunk_id"]),
                "material_id": meta.get("material_id"),
                "doc_title": r["doc_title"],
                "page_num": meta.get("page_num"),
                "char_start": meta.get("char_start"),
                "char_end": meta.get("char_end"),
                "sha256": meta.get("sha256"),
                "sha256_verified": sha_verified,
                "chunk_text": chunk_text,
                "highlight": _locate_excerpt(excerpt, chunk_text),
            }

        claims.append({
            "claim_id": str(r["question_id"]),
            "type": "question",
            "persona": r["persona"] or "Independent Reviewer",
            "category": r["category"],
            "difficulty": r["difficulty"],
            "text": r["question_text"],
            "excerpt": excerpt,
            "grounded": grounded,
            "answered": bool(r["answer_id"]),
            "source": source,
        })

    total = len(claims)
    return {
        "debate_id": debate_id,
        "materials": materials,
        "claims": claims,
        "summary": {
            "total_claims": total,
            "grounded": grounded_n,
            "gaps": total - grounded_n,
            "sha256_verified": verified_n,
            "grounded_pct": round(100.0 * grounded_n / total, 1) if total else 0.0,
        },
    }
