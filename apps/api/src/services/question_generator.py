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
import uuid
from typing import Any, Dict, List, Optional

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
- Write "source_excerpt" as a SHORT direct quote (≤40 words) from the excerpts.
  If no direct quote fits, write: "Based on stated methodology in uploaded materials."
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
  "source_excerpt":  "<short quote or 'Based on stated methodology in uploaded materials.'>"
}}
"""


def generate_questions(
    debate_id: str,
    openrouter_key: str,
    model_id: str = "",
    n_questions: int = 15,
    mode: ReasoningMode = "medium",
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
    profile = dict(profile_row)
    profile_id = profile["profile_id"]

    # ── Fetch chunks for source grounding ─────────────────────────────────
    excerpts = _fetch_excerpts(debate_id, limit=12)

    if not model_id:
        model_id = get_model("question_generation", mode)

    # ── LLM call ──────────────────────────────────────────────────────────
    profile_summary = {
        k: profile.get(k)
        for k in (
            "research_problem", "research_gap", "research_questions",
            "main_claim", "methodology", "contribution",
            "limitations", "weak_areas",
        )
    }

    client = OpenRouterClient(api_key=openrouter_key)
    response = client.chat_completion(
        model=model_id,
        messages=[
            {"role": "system", "content": _SYSTEM},
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
            cur.execute("""
                INSERT INTO defense_questions (
                    question_id, debate_id, profile_id,
                    question_text, category, difficulty, persona,
                    expected_answer, follow_up_rule, follow_up_q,
                    source_excerpt, seq_order, created_at
                ) VALUES (%s,%s,%s, %s,%s,%s,%s, %s,%s,%s, %s,%s,NOW())
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
                i,
            ))
            saved.append({**q, "question_id": question_id, "seq_order": i})
        conn.commit()

    return saved


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

def _fetch_excerpts(debate_id: str, limit: int = 12) -> str:
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("""
            SELECT mc.chunk_text,
                   COALESCE(mm.title, 'uploaded document') AS doc_title
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

    if not rows:
        return "No document excerpts available."

    return "\n\n---\n\n".join(
        f"[{r['doc_title']}]\n{(r['chunk_text'] or '')[:600]}"
        for r in rows
    )
