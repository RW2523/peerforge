"""
Feedback Reporter
=================
Aggregates all session_answers for a debate and generates a structured
feedback report that tells the student:
- strong / weak answers (qualitative)
- repeated issues
- likely follow-up questions from a review panel
- a concrete improvement plan
(Numeric aggregates are kept internally and never shown as marks.)
"""
from __future__ import annotations

import json
import uuid
from collections import Counter
from typing import Any, Dict, List, Optional

from ..database import get_db_connection, get_cursor
from ..openrouter_client import OpenRouterClient
from .reasoning_modes import get_model, ReasoningMode
from ..utils.json_repair import parse_llm_json


_SYSTEM = """\
You are an academic review coach generating a structured feedback report.
You are given aggregated evaluations from a student's practice review session.

Rules:
- Be constructive, specific, and evidence-grounded.
- Cite specific questions/answers by category when pointing out patterns.
- Use cautious, qualitative language: "appears well prepared", "may need more work". Never mention marks or grades in text fields.
- Return ONLY valid JSON — no markdown, no extra text.
"""

_USER_TEMPLATE = """\
## Session Summary
Debate ID: {debate_id}
Total questions answered: {total_answers}

## Aggregate Scores (0-10 per axis, averaged across all answers)
- Relevance:               {avg_relevance:.1f}
- Evidence Support:        {avg_evidence:.1f}
- Clarity:                 {avg_clarity:.1f}
- Completeness:            {avg_completeness:.1f}
- Methodology Understanding: {avg_methodology:.1f}
- Critical Thinking:       {avg_critical:.1f}
- OVERALL:                 {overall:.1f}

## Per-Answer Breakdown
{answer_details}

## Research Profile (summary)
{profile_summary}

---

Return a JSON object with EXACTLY these keys:
{{
  "overall_readiness":  <0-100 percentage>,
  "research_clarity":   <0-100>,
  "methodology_score":  <0-100>,
  "evidence_score":     <0-100>,
  "critical_thinking":  <0-100>,
  "communication":      <0-100>,
  "strong_answers": [
    {{"question": "<question text>", "score": <overall_score>, "summary": "<why it was strong>"}}
  ],
  "weak_answers": [
    {{"question": "<question text>", "score": <overall_score>, "summary": "<what was missing>"}}
  ],
  "repeated_issues": [
    {{"issue": "<description>", "frequency": <count>}}
  ],
  "likely_questions": [
    "<question a review panel is likely to ask in a formal review>"
  ],
  "improvement_plan": [
    {{"area": "<area>", "action": "<what to do>", "priority": "high|medium|low"}}
  ],
  "model_answers": [
    {{"question": "<a weak question worth re-answering>",
      "improved_answer": "<a strong, concise model answer (3-5 sentences) the researcher can study — grounded in their stated methodology/evidence, not invented>",
      "why_stronger": "<one sentence on what this fixes>"}}
  ],
  "next_recommendation": "<one sentence on what to do next before the formal review>"
}}
Produce a "model_answers" entry for each weak answer (up to 5). Ground every
improved answer in the researcher's actual methodology and evidence — never
invent results or citations.
"""


def generate_readiness_report(
    debate_id: str,
    openrouter_key: str,
    model_id: str = "",
    mode: ReasoningMode = "medium",
) -> Dict[str, Any]:
    """
    Build and persist a readiness report for *debate_id*.
    Returns the full report dict (with ``report_id``).
    """
    # ── Load answers ──────────────────────────────────────────────────────
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("""
            SELECT sa.*, dq.question_text, dq.category, dq.persona
            FROM   session_answers sa
            LEFT JOIN defense_questions dq ON sa.question_id = dq.question_id
            WHERE  sa.debate_id = %s
            ORDER  BY sa.answered_at
        """, (debate_id,))
        answers = [dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT * FROM research_profiles WHERE debate_id = %s AND status = 'complete'",
            (debate_id,)
        )
        profile_row = cur.fetchone()
        profile = dict(profile_row) if profile_row else {}

        cur.execute(
            "SELECT workspace_id FROM debates WHERE debate_id = %s", (debate_id,)
        )
        debate_row = cur.fetchone()
        workspace_id = str(debate_row["workspace_id"]) if debate_row else ""

    if not answers:
        raise ValueError("No answers found for this session. Complete at least one answer first.")

    # ── Aggregate scores ──────────────────────────────────────────────────
    def avg(field: str) -> float:
        vals = [float(a[field]) for a in answers if a.get(field) is not None]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    agg = {
        "avg_relevance":    avg("score_relevance"),
        "avg_evidence":     avg("score_evidence"),
        "avg_clarity":      avg("score_clarity"),
        "avg_completeness": avg("score_completeness"),
        "avg_methodology":  avg("score_methodology"),
        "avg_critical":     avg("score_critical_thinking"),
    }
    overall_raw = round(sum(agg.values()) / len(agg), 2)

    # ── Answer detail lines for prompt ────────────────────────────────────
    detail_lines = []
    for a in answers:
        detail_lines.append(
            f"Q ({a.get('category','?')}) [{a.get('persona','?')}]: "
            f"{(a.get('question_text') or 'unknown')[:80]}\n"
            f"  → Overall {a.get('overall_score', '?'):.1f} | "
            f"Weakness: {(a.get('weakness') or '-')[:80]}"
        )
    answer_details = "\n".join(detail_lines)

    profile_summary = "\n".join(filter(None, [
        f"Problem: {profile.get('research_problem', '')}",
        f"Claim:   {profile.get('main_claim', '')}",
        f"Method:  {profile.get('methodology', '')}",
    ]))

    # ── Upsert pending report ─────────────────────────────────────────────
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("""
            INSERT INTO readiness_reports
                (debate_id, workspace_id, status, answers_evaluated, created_at)
            VALUES (%s, %s, 'running', %s, NOW())
            ON CONFLICT (debate_id) DO UPDATE
              SET status = 'running', answers_evaluated = %s
            RETURNING report_id
        """, (debate_id, workspace_id, len(answers), len(answers)))
        report_id = cur.fetchone()["report_id"]
        conn.commit()

    if not model_id:
        model_id = get_model("readiness_report", mode)

    try:
        # ── LLM call ──────────────────────────────────────────────────────
        client = OpenRouterClient(api_key=openrouter_key)
        response = client.chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": _USER_TEMPLATE.format(
                    debate_id=debate_id,
                    total_answers=len(answers),
                    answer_details=answer_details,
                    profile_summary=profile_summary,
                    **agg,
                    overall=overall_raw,
                )},
            ],
            temperature=0.3,
            max_tokens=3000,
            _debate_id=debate_id,
            _stage="readiness_report",
        )

        raw = response["content"].strip()
        report_data: Dict = parse_llm_json(raw, stage="readiness_report")

        # ── Persist ───────────────────────────────────────────────────────
        with get_db_connection() as conn:
            cur = get_cursor(conn)
            cur.execute("""
                UPDATE readiness_reports SET
                    overall_readiness = %s,
                    research_clarity  = %s,
                    methodology_score = %s,
                    evidence_score    = %s,
                    critical_thinking = %s,
                    communication     = %s,
                    strong_answers    = %s,
                    weak_answers      = %s,
                    repeated_issues   = %s,
                    likely_questions  = %s,
                    improvement_plan  = %s,
                    next_recommendation = %s,
                    full_report_json  = %s,
                    model_used        = %s,
                    status            = 'complete',
                    generated_at      = NOW()
                WHERE report_id = %s
            """, (
                report_data.get("overall_readiness"),
                report_data.get("research_clarity"),
                report_data.get("methodology_score"),
                report_data.get("evidence_score"),
                report_data.get("critical_thinking"),
                report_data.get("communication"),
                json.dumps(report_data.get("strong_answers", [])),
                json.dumps(report_data.get("weak_answers", [])),
                json.dumps(report_data.get("repeated_issues", [])),
                json.dumps(report_data.get("likely_questions", [])),
                json.dumps(report_data.get("improvement_plan", [])),
                report_data.get("next_recommendation"),
                json.dumps(report_data),
                response.get("model", model_id),
                report_id,
            ))
            conn.commit()

            cur.execute("SELECT * FROM readiness_reports WHERE report_id = %s", (report_id,))
            return _merge_full_json(dict(cur.fetchone()))

    except Exception as exc:
        with get_db_connection() as conn:
            cur = get_cursor(conn)
            cur.execute("""
                UPDATE readiness_reports SET status = 'failed',
                    full_report_json = %s WHERE report_id = %s
            """, (json.dumps({"error": str(exc)}), report_id))
            conn.commit()
        raise


def _merge_full_json(row: Dict[str, Any]) -> Dict[str, Any]:
    """Surface extra keys stored only in full_report_json (e.g. model_answers)
    at the top level, so the API returns them alongside the column fields."""
    extra = row.get("full_report_json")
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except Exception:
            extra = None
    if isinstance(extra, dict):
        for k, v in extra.items():
            row.setdefault(k, v)
    return row


def get_readiness_report(debate_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            "SELECT * FROM readiness_reports WHERE debate_id = %s",
            (debate_id,)
        )
        row = cur.fetchone()
        return _merge_full_json(dict(row)) if row else None
