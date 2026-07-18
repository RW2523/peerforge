"""
Answer Evaluator
================
Evaluates a student's answer to a review question on 6 axes (internal only — never shown as marks):
  relevance, evidence_support, clarity, completeness,
  methodology_understanding, critical_thinking

Returns structured feedback and optionally triggers a follow-up.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from ..database import get_db_connection, get_cursor
from ..openrouter_client import OpenRouterClient
from .reasoning_modes import get_model, ReasoningMode
from ..utils.json_repair import parse_llm_json

_SYSTEM = """\
You are an academic review panel evaluator.
Your task is to assess and critique a student's answer to one specific review question.
Your numeric assessments are used internally to decide follow-ups — the student only
sees your qualitative feedback, so make it specific and actionable.

Scoring scale: 0–10 for each axis.
- 0–3  : Poor   (major gaps, inaccurate, or off-topic)
- 4–6  : Fair   (partial understanding, missing key points)
- 7–8  : Good   (solid answer with minor gaps)
- 9–10 : Strong (complete, evidence-grounded, critical)

Rules:
- Be specific — quote the student's exact words when praising or criticising.
- Base your critique on the research profile and question context provided.
- If the student's answer does not address the question, score relevance ≤ 3.
- If the student invents data not in the research context, flag it under "weakness".
- Return ONLY valid JSON — no markdown fences, no extra text.
"""

_USER_TEMPLATE = """\
## Review Question
Category: {category}  |  Persona: {persona}  |  Difficulty: {difficulty}
Question: {question_text}
Expected answer direction: {expected_answer}

## Research Context (from uploaded materials)
{research_context}

## Student's Answer
\"{answer_text}\"

---

Return a JSON object with EXACTLY these keys:
{{
  "score_relevance":              <0-10>,
  "score_evidence":               <0-10>,
  "score_clarity":                <0-10>,
  "score_completeness":           <0-10>,
  "score_methodology":            <0-10>,
  "score_critical_thinking":      <0-10>,
  "strength":                     "<what the student did well>",
  "weakness":                     "<what was missing or wrong>",
  "missing_evidence":             "<what evidence would strengthen the answer, or 'None'>",
  "suggested_improvement":        "<one concrete suggestion>",
  "follow_up_needed":             <true|false>,
  "follow_up_question":           "<follow-up question, or null>"
}}
"""


def evaluate_answer(
    debate_id: str,
    question_id: str,
    answer_text: str,
    openrouter_key: str,
    model_id: str = "",
    mode: ReasoningMode = "medium",
    severity: str = "standard",
) -> Dict[str, Any]:
    """
    Evaluate *answer_text* against *question_id*, persist to ``session_answers``,
    mark the question as asked, and return the evaluation dict (with ``answer_id``).
    """
    # ── Load question + research profile ──────────────────────────────────
    with get_db_connection() as conn:
        cur = get_cursor(conn)

        cur.execute("SELECT * FROM defense_questions WHERE question_id = %s", (question_id,))
        q_row = cur.fetchone()
        if not q_row:
            raise ValueError(f"Question {question_id} not found")
        question = dict(q_row)

        cur.execute(
            "SELECT * FROM research_profiles WHERE debate_id = %s AND status = 'complete'",
            (debate_id,)
        )
        profile_row = cur.fetchone()
        profile = dict(profile_row) if profile_row else {}

    if not model_id:
        model_id = get_model("answer_evaluation", mode)

    research_context = _build_context(profile, question)

    # ── LLM evaluation ────────────────────────────────────────────────────
    from .challenge_levels import eval_directive
    client = OpenRouterClient(api_key=openrouter_key)
    response = client.chat_completion(
        model=model_id,
        messages=[
            {"role": "system", "content": _SYSTEM + "\n\n" + eval_directive(severity)},
            {"role": "user",   "content": _USER_TEMPLATE.format(
                category=question.get("category", ""),
                persona=question.get("persona", ""),
                difficulty=question.get("difficulty", "medium"),
                question_text=question.get("question_text", ""),
                expected_answer=question.get("expected_answer", ""),
                research_context=research_context,
                answer_text=answer_text,
            )},
        ],
        temperature=0.2,
        max_tokens=1200,
        _debate_id=debate_id,
        _stage="answer_evaluation",
    )

    raw = response["content"].strip()
    ev: Dict = parse_llm_json(raw, stage="answer_evaluation")

    # Compute overall as mean of 6 axes
    axes = [
        "score_relevance", "score_evidence", "score_clarity",
        "score_completeness", "score_methodology", "score_critical_thinking",
    ]
    scores = [float(ev.get(a, 0)) for a in axes]
    overall = round(sum(scores) / len(scores), 2)

    # ── Persist ────────────────────────────────────────────────────────────
    answer_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("""
            INSERT INTO session_answers (
                answer_id, debate_id, question_id, answer_text, answered_at,
                score_relevance, score_evidence, score_clarity,
                score_completeness, score_methodology, score_critical_thinking,
                overall_score, strength, weakness, missing_evidence,
                suggested_improvement, follow_up_needed, follow_up_question,
                evaluation_json, model_used, created_at
            ) VALUES (
                %s,%s,%s,%s,NOW(),
                %s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,
                %s,%s,NOW()
            )
        """, (
            answer_id, debate_id, question_id, answer_text,
            ev.get("score_relevance"), ev.get("score_evidence"),
            ev.get("score_clarity"),   ev.get("score_completeness"),
            ev.get("score_methodology"), ev.get("score_critical_thinking"),
            overall,
            ev.get("strength"),      ev.get("weakness"),
            ev.get("missing_evidence"), ev.get("suggested_improvement"),
            bool(ev.get("follow_up_needed", False)),
            ev.get("follow_up_question"),
            json.dumps(ev),
            response.get("model", model_id),
        ))

        # Mark question as asked
        cur.execute("""
            UPDATE defense_questions
            SET asked = TRUE, asked_at = NOW(), answer_id = %s
            WHERE question_id = %s
        """, (answer_id, question_id))
        conn.commit()

    return {
        **ev,
        "answer_id":    answer_id,
        "question_id":  question_id,
        "overall_score": overall,
    }


def get_answers(debate_id: str):
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("""
            SELECT sa.*, dq.question_text, dq.category, dq.persona
            FROM   session_answers sa
            LEFT JOIN defense_questions dq ON sa.question_id = dq.question_id
            WHERE  sa.debate_id = %s
            ORDER  BY sa.answered_at
        """, (debate_id,))
        return [dict(r) for r in cur.fetchall()]


# ── Helpers ────────────────────────────────────────────────────────────────

def _build_context(profile: Dict, question: Dict) -> str:
    parts = []
    if profile.get("research_problem"):
        parts.append(f"Research problem: {profile['research_problem']}")
    if profile.get("main_claim"):
        parts.append(f"Main claim: {profile['main_claim']}")
    if profile.get("methodology"):
        parts.append(f"Methodology: {profile['methodology']}")
    if profile.get("limitations"):
        parts.append(f"Limitations: {profile['limitations']}")
    if question.get("source_excerpt"):
        parts.append(f"Relevant excerpt: \"{question['source_excerpt']}\"")
    return "\n".join(parts) if parts else "No research context available."
