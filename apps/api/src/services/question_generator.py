"""
Review Question Generator
==========================
Generates a set of panel-style review questions grounded in the
student's research profile and uploaded document chunks.

Each question belongs to one of 10 categories, is assigned to a specific
reviewer persona, and includes:
- expected answer direction
- source chunk reference (no invented citations)
- follow-up rule and question
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ..database import get_db_connection, get_cursor
from ..openrouter_client import OpenRouterClient
from .reasoning_modes import get_model, ReasoningMode
from ..utils.json_repair import parse_llm_json

QUESTION_CATEGORIES = [
    "problem_statement",
    "research_gap",
    "methodology",
    "novelty",
    "evidence",
    "limitations",
    "results",
    "future_work",
    "practical_impact",
    "panel_challenge",
]

COMMITTEE_PERSONAS = [
    "Advisor",
    "Methodology Professor",
    "Domain Expert",
    "Skeptical Reviewer",
    "Friendly Professor",
    "Independent Reviewer",
]

_SYSTEM = """\
You are an academic review-panel question generator for graduate research preparation.
You generate rigorous, academically grounded questions.

Rules:
- Every question MUST reference specific content from the provided research profile
  or document excerpts.
- Write "source_excerpt" as a SHORT, VERBATIM direct quote (≤40 words) copied
  word-for-word from ONE of the labelled excerpts. Do not paraphrase the quote.
- Set "source_ref" to the label (e.g. "S3") of the excerpt you quoted from.
  If the question is grounded only in the research profile and NOT in any excerpt,
  set "source_excerpt" to "Based on stated methodology in uploaded materials."
  and "source_ref" to "".
- Do NOT invent authors, papers, or results.
- Distribute questions across all 10 categories.
- Each persona must ask only questions aligned with their role.
- Return ONLY valid JSON — no markdown, no explanation.
"""

_USER_TEMPLATE = """\
## Research Profile
{profile_json}

## Document Excerpts (for grounding)
{excerpts}

---

Generate exactly {n_questions} review questions as a JSON array.
Each element must have EXACTLY these keys:
{{
  "question_text":   "<the question>",
  "category":        "<one of: {categories}>",
  "difficulty":      "<easy|medium|hard>",
  "persona":         "<one of: {personas}>",
  "expected_answer": "<what a strong answer would cover>",
  "follow_up_rule":  "<condition that triggers a follow-up>",
  "follow_up_q":     "<the follow-up question>",
  "source_excerpt":  "<verbatim quote or 'Based on stated methodology in uploaded materials.'>",
  "source_ref":      "<label of the quoted excerpt, e.g. 'S3', or '' if none>"
}}
"""


def generate_questions(
    debate_id: str,
    openrouter_key: str,
    model_id: str = "",
    n_questions: int = 15,
    mode: ReasoningMode = "medium",
    severity: str = "standard",
    practice_mode: str = "thesis_defense",
) -> List[Dict[str, Any]]:
    """
    Generate review questions for *debate_id* and persist to ``defense_questions``.
    Returns the list of generated question dicts (with ``question_id``).
    """
    # ── Load research profile ──────────────────────────────────────────────
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            "SELECT * FROM research_profiles WHERE debate_id = %s AND status = 'complete'",
            (debate_id,)
        )
        profile_row = cur.fetchone()

    if not profile_row:
        raise ValueError(
            f"No completed research profile found for debate {debate_id}. "
            "Run /analyze-research first."
        )
    from .research_analyzer import _merge_raw
    profile = _merge_raw(dict(profile_row))
    profile_id = profile["profile_id"]

    # ── Fetch chunks for source grounding ─────────────────────────────────
    chunks = _fetch_chunks(debate_id, limit=12)
    excerpts = _format_excerpts(chunks)

    if not model_id:
        model_id = get_model("question_generation", mode)

    # ── LLM call ──────────────────────────────────────────────────────────
    profile_summary = {
        k: profile.get(k)
        for k in (
            "research_problem", "research_gap", "research_questions",
            "hypothesis", "main_claim", "key_claims", "methodology",
            "results", "contribution", "limitations", "future_work",
            "contradictions", "weak_areas",
        )
        if profile.get(k)
    }

    from .challenge_levels import question_directive
    from .practice_modes import mode_focus, mode_emphasis
    _mode_block = (
        mode_focus(practice_mode)
        + "\nWeight questions toward these categories for this mode: "
        + ", ".join(mode_emphasis(practice_mode)) + "."
    )
    client = OpenRouterClient(api_key=openrouter_key)
    response = client.chat_completion(
        model=model_id,
        messages=[
            {"role": "system", "content": _SYSTEM + "\n\n" + _mode_block + "\n\n" + question_directive(severity)},
            {"role": "user",   "content": _USER_TEMPLATE.format(
                profile_json=json.dumps(profile_summary, indent=2),
                excerpts=excerpts,
                n_questions=n_questions,
                categories=", ".join(QUESTION_CATEGORIES),
                personas=", ".join(COMMITTEE_PERSONAS),
            )},
        ],
        temperature=0.4,
        max_tokens=4000,
        _debate_id=debate_id,
        _stage="question_generation",
    )

    raw = response["content"].strip()
    questions: List[Dict] = parse_llm_json(raw, stage="question_generation")
    if not isinstance(questions, list):
        questions = questions.get("questions", [])

    # ── Persist ────────────────────────────────────────────────────────────
    saved: List[Dict] = []
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        # Delete any previously generated questions for this debate
        cur.execute("DELETE FROM defense_questions WHERE debate_id = %s", (debate_id,))

        for i, q in enumerate(questions):
            question_id = str(uuid.uuid4())
            # Resolve a hard provenance link: which ingested chunk does this
            # question's quote actually come from? source_chunk_id stays NULL
            # (an "evidence gap") when the quote can't be matched to a chunk.
            grounding = _resolve_grounding(
                q.get("source_excerpt", ""), q.get("source_ref", ""), chunks
            )
            source_chunk_id = grounding["chunk_id"]
            source_document_id = grounding["material_id"]
            cur.execute("""
                INSERT INTO defense_questions (
                    question_id, debate_id, profile_id,
                    question_text, category, difficulty, persona,
                    expected_answer, follow_up_rule, follow_up_q,
                    source_excerpt, source_chunk_id, source_document_id,
                    seq_order, created_at
                ) VALUES (%s,%s,%s, %s,%s,%s,%s, %s,%s,%s, %s,%s,%s, %s,NOW())
            """, (
                question_id, debate_id, str(profile_id),
                q.get("question_text", ""),
                q.get("category", "panel_challenge"),
                q.get("difficulty", "medium"),
                q.get("persona", "Independent Reviewer"),
                q.get("expected_answer", ""),
                q.get("follow_up_rule", ""),
                q.get("follow_up_q", ""),
                q.get("source_excerpt", ""),
                source_chunk_id,
                source_document_id,
                i,
            ))
            saved.append({
                **q,
                "question_id": question_id,
                "seq_order": i,
                "source_chunk_id": source_chunk_id,
                "source_document_id": source_document_id,
                "grounded": grounding["grounded"],
                "match_method": grounding["method"],
            })
        conn.commit()

    return saved


def add_follow_up_question(
    debate_id: str,
    parent_question_id: str,
    question_text: str,
) -> Dict[str, Any]:
    """Persist a follow-up probe as a real question so the normal answer /
    evaluation pipeline can handle it — this is what closes the challenge loop.
    Inherits persona/category from the parent, bumps difficulty, links via
    follow_up_rule, and appends after the last question."""
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("SELECT * FROM defense_questions WHERE question_id = %s", (parent_question_id,))
        parent = cur.fetchone()
        if not parent:
            raise ValueError(f"Parent question {parent_question_id} not found")
        parent = dict(parent)

        cur.execute(
            "SELECT COALESCE(MAX(seq_order), 0) + 1 AS n FROM defense_questions WHERE debate_id = %s",
            (debate_id,),
        )
        seq = cur.fetchone()["n"]

        question_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO defense_questions (
                question_id, debate_id, profile_id,
                question_text, category, difficulty, persona,
                expected_answer, follow_up_rule, follow_up_q,
                source_excerpt, source_chunk_id, source_document_id,
                seq_order, created_at
            ) VALUES (%s,%s,%s, %s,%s,'hard',%s, %s,%s,%s, %s,%s,%s, %s,NOW())
        """, (
            question_id, debate_id, parent.get("profile_id"),
            question_text, parent.get("category", "panel_challenge"),
            parent.get("persona", "Skeptical Reviewer"),
            "", f"follow_up_of:{parent_question_id}", "",
            parent.get("source_excerpt", ""),
            parent.get("source_chunk_id"), parent.get("source_document_id"),
            seq,
        ))
        conn.commit()
        cur.execute("SELECT * FROM defense_questions WHERE question_id = %s", (question_id,))
        return dict(cur.fetchone())


def get_questions(
    debate_id: str,
    unanswered_only: bool = False,
) -> List[Dict[str, Any]]:
    """Return all (or unanswered) questions for a debate."""
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        if unanswered_only:
            cur.execute("""
                SELECT * FROM defense_questions
                WHERE debate_id = %s AND asked = FALSE
                ORDER BY seq_order
            """, (debate_id,))
        else:
            cur.execute("""
                SELECT * FROM defense_questions
                WHERE debate_id = %s
                ORDER BY seq_order
            """, (debate_id,))
        return [dict(r) for r in cur.fetchall()]


# ── Helpers ────────────────────────────────────────────────────────────────

def _fetch_chunks(debate_id: str, limit: int = 12) -> List[Dict[str, Any]]:
    """Return the document chunks that ground question generation, each carrying
    its full provenance metadata (chunk_id, material, page, offsets, sha256)."""
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("""
            SELECT mc.chunk_id,
                   mc.chunk_text,
                   mc.chunk_metadata,
                   COALESCE(mm.title, 'uploaded document') AS doc_title,
                   (mc.chunk_metadata->>'material_id')      AS material_id
            FROM   memory_chunks mc
            LEFT JOIN meeting_materials mm
                   ON (mc.chunk_metadata->>'material_id')::uuid = mm.material_id
            WHERE  mc.source_debate_id = %s
              AND  mc.agent_id IS NULL
            ORDER BY CASE COALESCE(mc.chunk_metadata->>'category', 'supplementary')
                       WHEN 'main_research' THEN 0
                       WHEN 'research'      THEN 1
                       WHEN 'supplementary' THEN 2
                       ELSE 3
                     END,
                     mc.created_at
            LIMIT %s
        """, (debate_id, limit))
        rows = cur.fetchall()

    chunks: List[Dict[str, Any]] = []
    for idx, r in enumerate(rows):
        meta = r["chunk_metadata"] or {}
        chunks.append({
            "label":       f"S{idx + 1}",
            "chunk_id":    str(r["chunk_id"]),
            "chunk_text":  r["chunk_text"] or "",
            "doc_title":   r["doc_title"],
            "material_id": r["material_id"] or meta.get("material_id"),
            "page_num":    meta.get("page_num"),
            "sha256":      meta.get("sha256"),
        })
    return chunks


def _format_excerpts(chunks: List[Dict[str, Any]]) -> str:
    """Render fetched chunks into a labelled block the LLM can cite by label."""
    if not chunks:
        return "No document excerpts available."
    parts = []
    for c in chunks:
        page = f" p.{c['page_num']}" if c.get("page_num") else ""
        parts.append(f"[{c['label']} — {c['doc_title']}{page}]\n{c['chunk_text'][:600]}")
    return "\n\n---\n\n".join(parts)


# Generic fallbacks the model emits when nothing in the corpus fits — these are
# NOT quotes and must never be treated as grounded provenance.
_GENERIC_EXCERPTS = {
    "based on stated methodology in uploaded materials.",
    "based on stated methodology in uploaded materials",
    "insufficient evidence in uploaded materials.",
    "insufficient evidence in uploaded materials",
    "no document excerpts available.",
    "",
}

_WORD_RE = re.compile(r"[a-z0-9]+")


def _normalize(text: str) -> str:
    return " ".join(_WORD_RE.findall((text or "").lower()))


def _tokens(text: str) -> List[str]:
    return _WORD_RE.findall((text or "").lower())


def _containment(excerpt: str, chunk_text: str) -> float:
    """Fraction of the (short) excerpt's tokens that appear in the chunk."""
    ex = _tokens(excerpt)
    if not ex:
        return 0.0
    chunk_set = set(_tokens(chunk_text))
    hit = sum(1 for t in ex if t in chunk_set)
    return hit / len(ex)


def _resolve_grounding(
    excerpt: str, source_ref: str, chunks: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Deterministically link a question's quote to the chunk it came from.

    Returns {chunk_id, material_id, grounded, method, score}. When the quote is a
    generic fallback or matches no chunk, chunk_id is None (an *evidence gap*).
    """
    empty = {"chunk_id": None, "material_id": None, "grounded": False,
             "method": "none", "score": 0.0}
    if not chunks:
        return empty
    if _normalize(excerpt) in {_normalize(g) for g in _GENERIC_EXCERPTS}:
        return empty

    norm_excerpt = _normalize(excerpt)
    by_label = {c["label"].lower(): c for c in chunks}

    # 1) Exact verbatim substring — the strongest, sha256-verifiable link.
    for c in chunks:
        if norm_excerpt and norm_excerpt in _normalize(c["chunk_text"]):
            return {"chunk_id": c["chunk_id"], "material_id": c["material_id"],
                    "grounded": True, "method": "exact_substring", "score": 1.0}

    # 2) Token containment — best-matching chunk, biased toward the model's hint.
    hint = by_label.get((source_ref or "").strip().lower())
    best, best_score = None, 0.0
    for c in chunks:
        score = _containment(excerpt, c["chunk_text"])
        if c is hint:
            score += 0.05  # tie-break toward the model's declared source
        if score > best_score:
            best, best_score = c, score

    if best and best_score >= 0.6:
        return {"chunk_id": best["chunk_id"], "material_id": best["material_id"],
                "grounded": True, "method": "token_overlap", "score": round(best_score, 3)}

    return empty
