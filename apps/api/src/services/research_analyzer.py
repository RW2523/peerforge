"""
Research Analyzer
=================
Extracts a structured research profile from a student's uploaded document
chunks. The output is grounded in retrieved text — the LLM is instructed to
use cautious, evidence-hedged language and to flag areas where evidence is
absent rather than inventing claims.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..database import get_db_connection, get_cursor
from ..openrouter_client import OpenRouterClient
from ..services.memory_retrieval import retrieve_allowed_chunks
from .reasoning_modes import get_model, mode_from_policy, ReasoningMode
from ..utils.json_repair import parse_llm_json


# ── System prompt ──────────────────────────────────────────────────────────
_SYSTEM = """\
You are an academic research analysis assistant.
You will be given excerpts from a student's uploaded research materials.
Your task is to extract a structured profile of the research.

Rules:
- Base every field ONLY on evidence present in the provided excerpts.
- If evidence for a field is missing, write exactly: "Insufficient evidence in uploaded materials."
- Do NOT invent citations, authors, or results.
- Use cautious wording: "appears to", "based on uploaded materials", "possibly", "the materials suggest".
- Never claim the research is definitely novel; write instead:
  "Based on uploaded materials, this may represent a contribution, but novelty should be verified against related literature."
- Return ONLY valid JSON — no markdown fences, no extra text.
"""

_USER_TEMPLATE = """\
## Uploaded Research Excerpts (total {n} chunks)

{chunks}

---

Return a JSON object with EXACTLY these keys:
{{
  "research_problem":   "<one sentence>",
  "research_gap":       "<gap or insufficiency in current knowledge>",
  "research_questions": ["<RQ1>", "<RQ2>", ...],
  "main_claim":         "<central thesis or contribution>",
  "methodology":        "<methods, approach, experimental design>",
  "dataset_details":    "<datasets, corpora, or sources used>",
  "contribution":       "<what the work may add — use cautious wording>",
  "evidence_summary":   "<what empirical or theoretical evidence supports the claim>",
  "limitations":        "<stated or apparent limitations>",
  "weak_areas": [
    {{"area": "<topic>", "reason": "<why it appears weak>"}}
  ],
  "possible_questions": [
    "<question a committee member might ask>"
  ]
}}
"""


def analyze_research(
    debate_id: str,
    openrouter_key: str,
    model_id: str = "",
    max_chunks: int = 20,
    mode: ReasoningMode = "medium",
) -> Dict[str, Any]:
    """
    Analyse uploaded research materials for *debate_id* and store the
    structured profile in ``research_profiles``.

    Returns the full profile dict (including ``profile_id``).
    """
    with get_db_connection() as conn:
        cur = get_cursor(conn)

        # ── Upsert a 'running' record so callers can poll status ──────────
        cur.execute("""
            INSERT INTO research_profiles (debate_id, workspace_id, status, created_at, updated_at)
            SELECT debate_id, workspace_id, 'running', NOW(), NOW()
            FROM   debates WHERE debate_id = %s
            ON CONFLICT (debate_id) DO UPDATE
              SET status = 'running', updated_at = NOW(), error_message = NULL
            RETURNING profile_id, workspace_id
        """, (debate_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Debate {debate_id} not found")
        profile_id = row["profile_id"]
        conn.commit()

    # Resolve model: explicit > mode-based default
    if not model_id:
        model_id = get_model("analysis", mode)

    try:
        # ── Retrieve document chunks via existing RAG service ─────────────
        try:
            retrieval_resp = retrieve_allowed_chunks(
                debate_id=debate_id,
                participant_id=None,   # no specific participant — all materials
                query="research problem methodology contribution evidence limitations",
                top_k=max_chunks,
            )
            raw_chunks = retrieval_resp.chunks if retrieval_resp else []
        except Exception:
            raw_chunks = []

        if not raw_chunks:
            # Fall back: pull raw chunks directly from DB
            raw_chunks = _fetch_raw_chunks(debate_id, max_chunks)

        chunk_ids = [str(c.chunk_id) for c in raw_chunks]
        chunk_text = "\n\n---\n\n".join(
            f"[Chunk {i+1} | {getattr(c, 'source_document_title', None) or 'uploaded doc'}]\n{c.chunk_text[:800]}"
            for i, c in enumerate(raw_chunks)
        )

        # ── LLM call ──────────────────────────────────────────────────────
        client = OpenRouterClient(api_key=openrouter_key)
        response = client.chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": _USER_TEMPLATE.format(
                    n=len(raw_chunks), chunks=chunk_text
                )},
            ],
            temperature=0.2,
            max_tokens=2000,
            _debate_id=debate_id,
            _stage="research_analysis",
        )

        raw = response["content"].strip()
        profile_data: Dict = parse_llm_json(raw, stage="research_analysis")

        # ── Persist ───────────────────────────────────────────────────────
        with get_db_connection() as conn:
            cur = get_cursor(conn)
            cur.execute("""
                UPDATE research_profiles SET
                    research_problem   = %s,
                    research_gap       = %s,
                    research_questions = %s,
                    main_claim         = %s,
                    methodology        = %s,
                    dataset_details    = %s,
                    contribution       = %s,
                    evidence_summary   = %s,
                    limitations        = %s,
                    weak_areas         = %s,
                    possible_questions = %s,
                    raw_analysis       = %s,
                    chunks_used        = %s::uuid[],
                    chunk_count        = %s,
                    model_used         = %s,
                    status             = 'complete',
                    updated_at         = NOW()
                WHERE profile_id = %s
            """, (
                profile_data.get("research_problem"),
                profile_data.get("research_gap"),
                json.dumps(profile_data.get("research_questions", [])),
                profile_data.get("main_claim"),
                profile_data.get("methodology"),
                profile_data.get("dataset_details"),
                profile_data.get("contribution"),
                profile_data.get("evidence_summary"),
                profile_data.get("limitations"),
                json.dumps(profile_data.get("weak_areas", [])),
                json.dumps(profile_data.get("possible_questions", [])),
                json.dumps(profile_data),
                chunk_ids,
                len(raw_chunks),
                response.get("model", model_id),
                profile_id,
            ))
            conn.commit()

            cur.execute("SELECT * FROM research_profiles WHERE profile_id = %s", (profile_id,))
            return dict(cur.fetchone())

    except Exception as exc:
        with get_db_connection() as conn:
            cur = get_cursor(conn)
            cur.execute("""
                UPDATE research_profiles
                SET status = 'failed', error_message = %s, updated_at = NOW()
                WHERE profile_id = %s
            """, (str(exc)[:500], profile_id))
            conn.commit()
        raise


def get_research_profile(debate_id: str) -> Optional[Dict[str, Any]]:
    """Return the stored research profile for a debate, or None."""
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            "SELECT * FROM research_profiles WHERE debate_id = %s",
            (debate_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None


# ── Helpers ────────────────────────────────────────────────────────────────

def _fetch_raw_chunks(debate_id: str, limit: int) -> List[Any]:
    """Fallback: pull chunks directly from memory_chunks table."""
    from dataclasses import dataclass

    @dataclass
    class _Chunk:
        chunk_id: str
        chunk_text: str
        source_document_title: Optional[str] = None

    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("""
            SELECT mc.chunk_id, mc.chunk_text,
                   mm.title AS source_document_title
            FROM   memory_chunks mc
            LEFT JOIN meeting_materials mm
                   ON (mc.chunk_metadata->>'material_id')::uuid = mm.material_id
            WHERE  mc.source_debate_id = %s
              AND  mc.agent_id IS NULL
            ORDER BY mc.created_at
            LIMIT  %s
        """, (debate_id, limit))
        return [
            _Chunk(
                chunk_id=str(r["chunk_id"]),
                chunk_text=r["chunk_text"] or "",
                source_document_title=r.get("source_document_title"),
            )
            for r in cur.fetchall()
        ]
