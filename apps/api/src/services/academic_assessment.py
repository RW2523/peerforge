"""
Academic Assessment Matrix
==========================
Generates a formative, ten-dimension assessment of the researcher's
preparedness, synthesised from everything a session knows:

  - the extracted research profile
  - practice Q&A answers and their evaluations
  - the panel discussion transcript
  - the session summary (when available)

Each dimension is rated 0-10 with a one-sentence examiner comment. The
assessment is regenerated on demand after any activity (practice answer,
panel discussion, voice session) so progress is visible over time.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from ..database import get_db_connection, get_cursor
from ..openrouter_client import OpenRouterClient
from .reasoning_modes import get_model, ReasoningMode
from ..utils.json_repair import parse_llm_json

# ── The ten assessment dimensions ────────────────────────────────────────────
# Keys are stable identifiers; labels are the user-facing academic wording.

ASSESSMENT_DIMENSIONS: List[Dict[str, str]] = [
    {"key": "research_readiness",      "label": "Research Readiness",
     "what": "Overall preparedness to present and justify this work before an academic panel."},
    {"key": "conceptual_clarity",      "label": "Conceptual Clarity",
     "what": "How clearly the research problem, claims, and key concepts are articulated."},
    {"key": "methodological_rigour",   "label": "Methodological Rigour",
     "what": "Soundness of research design, baselines, statistics, and reproducibility."},
    {"key": "evidence_grounding",      "label": "Evidence & Grounding",
     "what": "Whether claims are tied to concrete evidence from the materials, without overreach."},
    {"key": "critical_thinking",       "label": "Critical Thinking",
     "what": "Ability to reason about alternatives, confounds, and counter-arguments."},
    {"key": "communication",           "label": "Communication & Articulation",
     "what": "Clarity, structure, and accessibility of written and spoken explanations."},
    {"key": "originality_contribution","label": "Originality & Contribution",
     "what": "Strength and defensibility of the claimed novelty and its significance to the field."},
    {"key": "literature_awareness",    "label": "Literature & Context Awareness",
     "what": "Command of related work and honest positioning of the research within it."},
    {"key": "limitations_awareness",   "label": "Limitations & Self-Awareness",
     "what": "Honesty and completeness in acknowledging limitations and their implications."},
    {"key": "responsiveness",          "label": "Responsiveness to Questioning",
     "what": "Quality of answers under questioning: directness, depth, and composure."},
]

_DIMENSION_KEYS = [d["key"] for d in ASSESSMENT_DIMENSIONS]

_SYSTEM = """\
You are an experienced academic examiner producing a formative ten-dimension
assessment of a researcher's preparedness, based on evidence from their review
session (research profile, practice answers, panel discussion, summary).

Rating scale per dimension (0-10):
  0-3  Substantially under-prepared on this dimension
  4-5  Developing — clear gaps remain
  6-7  Competent — minor gaps
  8-10 Strong — would satisfy a rigorous panel

Rules:
- Rate ONLY from the evidence provided. If a dimension has little or no
  evidence (e.g. no practice answers yet), rate conservatively and say so
  in the comment.
- Each comment must be ONE specific sentence grounded in the evidence —
  reference what the researcher actually said, wrote, or omitted.
- Be fair but rigorous: this is formative assessment, not flattery.
- Vocabulary: say "formal review" or "review panel" — never "defense" or "viva".
- Return ONLY valid JSON — no markdown fences, no extra text.
"""

_USER_TEMPLATE = """\
## Research Profile
{profile}

## Practice Q&A ({answer_count} answers)
{answers}

## Panel Discussion ({message_count} contributions)
{transcript}

## Session Summary
{summary}

---

Assess all ten dimensions. Return a JSON object with EXACTLY these keys:
{{
  "dimensions": [
    {{"key": "<one of: {keys}>", "score": <0-10, one decimal allowed>, "comment": "<one specific sentence>"}}
  ],
  "overall_remarks": "<two to three sentences: overall standing and the single most important next step>"
}}
The "dimensions" array must contain EXACTLY ten entries — one per key, in order.
"""


def generate_assessment(
    debate_id: str,
    openrouter_key: str,
    mode: ReasoningMode = "light",
    trigger_source: str = "manual",
    model_id: str = "",
) -> Dict[str, Any]:
    """
    Build and persist a ten-dimension academic assessment for *debate_id*.
    Returns the stored assessment dict.
    """
    evidence = _gather_evidence(debate_id)
    if not evidence["has_any_evidence"]:
        raise ValueError(
            "Nothing to assess yet — run a practice answer, a panel discussion, "
            "or a voice session first."
        )

    if not model_id:
        model_id = get_model("readiness_report", mode)

    client = OpenRouterClient(api_key=openrouter_key)
    response = client.chat_completion(
        model=model_id,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _USER_TEMPLATE.format(
                profile=evidence["profile_text"],
                answer_count=evidence["answer_count"],
                answers=evidence["answers_text"],
                message_count=evidence["message_count"],
                transcript=evidence["transcript_text"],
                summary=evidence["summary_text"],
                keys=", ".join(_DIMENSION_KEYS),
            )},
        ],
        temperature=0.2,
        max_tokens=2200,
        _debate_id=debate_id,
        _stage="academic_assessment",
    )

    raw = response["content"].strip()
    data: Dict = parse_llm_json(raw, stage="academic_assessment")

    dimensions = _normalise_dimensions(data.get("dimensions", []))
    scores = [d["score"] for d in dimensions]
    overall = round(sum(scores) / len(scores), 1) if scores else 0.0
    overall_remarks = (data.get("overall_remarks") or "").strip()

    basis = {
        "has_profile": evidence["has_profile"],
        "answer_count": evidence["answer_count"],
        "message_count": evidence["message_count"],
        "has_summary": evidence["has_summary"],
    }

    assessment_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            "SELECT workspace_id FROM debates WHERE debate_id = %s", (debate_id,)
        )
        row = cur.fetchone()
        workspace_id = str(row["workspace_id"]) if row else None

        cur.execute("""
            INSERT INTO academic_assessments (
                assessment_id, debate_id, workspace_id, trigger_source,
                dimensions, overall_score, overall_remarks, basis,
                model_used, generated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            assessment_id, debate_id, workspace_id, trigger_source,
            json.dumps(dimensions), overall, overall_remarks,
            json.dumps(basis), response.get("model", model_id),
        ))
        conn.commit()

    return {
        "assessment_id": assessment_id,
        "debate_id": debate_id,
        "trigger_source": trigger_source,
        "dimensions": dimensions,
        "overall_score": overall,
        "overall_remarks": overall_remarks,
        "basis": basis,
        "model_used": response.get("model", model_id),
    }


def get_latest_assessment(debate_id: str) -> Optional[Dict[str, Any]]:
    """Return the most recent assessment for *debate_id*, or None."""
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("""
            SELECT assessment_id, debate_id, trigger_source, dimensions,
                   overall_score, overall_remarks, basis, model_used, generated_at
            FROM academic_assessments
            WHERE debate_id = %s
            ORDER BY generated_at DESC
            LIMIT 1
        """, (debate_id,))
        row = cur.fetchone()
        if not row:
            return None
        result = dict(row)
        result["assessment_id"] = str(result["assessment_id"])
        result["debate_id"] = str(result["debate_id"])
        if result.get("overall_score") is not None:
            result["overall_score"] = float(result["overall_score"])
        return result


def get_assessment_history(debate_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Return prior assessments (newest first) so progress is visible."""
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("""
            SELECT assessment_id, trigger_source, overall_score, generated_at
            FROM academic_assessments
            WHERE debate_id = %s
            ORDER BY generated_at DESC
            LIMIT %s
        """, (debate_id, limit))
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            r["assessment_id"] = str(r["assessment_id"])
            if r.get("overall_score") is not None:
                r["overall_score"] = float(r["overall_score"])
        return rows


# ── Helpers ──────────────────────────────────────────────────────────────────

def _normalise_dimensions(raw_dimensions: Any) -> List[Dict[str, Any]]:
    """Validate LLM output against the canonical dimension list.

    Guarantees exactly ten entries, in canonical order, scores clamped to
    [0, 10]. Missing dimensions get a conservative default so the matrix is
    always complete.
    """
    by_key: Dict[str, Dict] = {}
    if isinstance(raw_dimensions, list):
        for item in raw_dimensions:
            if isinstance(item, dict) and item.get("key") in _DIMENSION_KEYS:
                by_key[item["key"]] = item

    result: List[Dict[str, Any]] = []
    for spec in ASSESSMENT_DIMENSIONS:
        item = by_key.get(spec["key"], {})
        try:
            score = round(float(item.get("score", 0)), 1)
        except (TypeError, ValueError):
            score = 0.0
        score = max(0.0, min(10.0, score))
        comment = str(item.get("comment") or "Insufficient evidence to assess this dimension yet.").strip()
        result.append({
            "key": spec["key"],
            "label": spec["label"],
            "score": score,
            "comment": comment,
        })
    return result


def _gather_evidence(debate_id: str) -> Dict[str, Any]:
    """Collect everything assessable for this session."""
    with get_db_connection() as conn:
        cur = get_cursor(conn)

        # Research profile
        cur.execute(
            "SELECT * FROM research_profiles WHERE debate_id = %s AND status = 'complete'",
            (debate_id,),
        )
        profile_row = cur.fetchone()
        profile = dict(profile_row) if profile_row else {}

        # Practice answers + evaluations
        cur.execute("""
            SELECT sa.answer_text, sa.strength, sa.weakness,
                   sa.suggested_improvement, sa.overall_score,
                   dq.question_text, dq.category
            FROM session_answers sa
            LEFT JOIN defense_questions dq ON sa.question_id = dq.question_id
            WHERE sa.debate_id = %s
            ORDER BY sa.answered_at
            LIMIT 15
        """, (debate_id,))
        answers = [dict(r) for r in cur.fetchall()]

        # Panel discussion transcript (agent contributions)
        cur.execute("""
            SELECT content
            FROM events
            WHERE debate_id = %s AND event_type = 'agent_message'
            ORDER BY sequence_number
            LIMIT 20
        """, (debate_id,))
        messages = []
        for r in cur.fetchall():
            content = r["content"] or {}
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except Exception:
                    content = {}
            text = content.get("text") or content.get("message") or ""
            name = content.get("agent_name") or content.get("actor") or "Panelist"
            if text:
                messages.append(f"[{name}] {text[:450]}")

        # Session summary
        cur.execute("""
            SELECT summary
            FROM debate_outputs
            WHERE debate_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (debate_id,))
        summary_row = cur.fetchone()
        summary_text = (summary_row["summary"] or "")[:1200] if summary_row else ""

    profile_text = "\n".join(filter(None, [
        f"Problem: {profile.get('research_problem', '')}",
        f"Claim: {profile.get('main_claim', '')}",
        f"Methodology: {profile.get('methodology', '')}",
        f"Contribution: {profile.get('contribution', '')}",
        f"Limitations: {profile.get('limitations', '')}",
    ])) or "Not yet analysed."

    answers_text = "\n\n".join(
        f"Q ({a.get('category', '?')}): {(a.get('question_text') or '')[:160]}\n"
        f"Answer: {(a.get('answer_text') or '')[:400]}\n"
        f"Evaluator noted — strength: {(a.get('strength') or '-')[:160]} | "
        f"weakness: {(a.get('weakness') or '-')[:160]}"
        for a in answers
    ) or "No practice answers yet."

    transcript_text = "\n\n".join(messages) or "No panel discussion yet."

    return {
        "profile_text": profile_text,
        "answers_text": answers_text,
        "transcript_text": transcript_text,
        "summary_text": summary_text or "No summary yet.",
        "answer_count": len(answers),
        "message_count": len(messages),
        "has_profile": bool(profile),
        "has_summary": bool(summary_text),
        "has_any_evidence": bool(profile or answers or messages or summary_text),
    }
