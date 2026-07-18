"""
Presentation Coach (concept 7.6)
================================
Turns an uploaded slide deck into coaching:

  * deck_data()  — deterministic, LLM-free: per-slide structure metrics with
                   honest flags (walls of text, bullet overload, missing notes,
                   no conclusion, deck too long for the slot).
  * coach_deck() — LLM narrative grounded ONLY in the extracted slide text:
                   structure/flow/clarity feedback, per-slide suggestions, and
                   likely audience questions.

The deck is re-extracted from object storage on demand (python-pptx is fast),
so the coach always reflects the latest uploaded file.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..database import get_db_connection, get_cursor
from ..openrouter_client import OpenRouterClient
from .reasoning_modes import get_model, ReasoningMode
from ..utils.json_repair import parse_llm_json

_PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

# Structure heuristics (conference-talk conventions).
MAX_BODY_WORDS = 80      # beyond this a slide reads as a wall of text
MAX_BULLETS = 7
SECONDS_PER_SLIDE = (60, 120)   # healthy pacing band


def _find_deck_material(debate_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            """
            SELECT material_id, title, file_key
            FROM meeting_materials
            WHERE debate_id = %s AND file_mime_type = %s
            ORDER BY created_at DESC LIMIT 1
            """,
            (debate_id, _PPTX_MIME),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def deck_data(debate_id: str) -> Dict[str, Any]:
    """Deterministic deck structure + per-slide flags. No LLM call."""
    mat = _find_deck_material(debate_id)
    if not mat or not mat.get("file_key"):
        raise ValueError("No slide deck (.pptx) uploaded for this session yet.")

    from ..utils.storage import get_storage_client
    from ..utils.text_extraction import TextExtractor

    file_data = get_storage_client().download_file(mat["file_key"])
    extraction = TextExtractor.extract_from_pptx(file_data)

    slides: List[Dict[str, Any]] = []
    for meta, page in zip(extraction["slides"], extraction["pages"]):
        flags: List[str] = []
        if meta["body_words"] > MAX_BODY_WORDS:
            flags.append("wall_of_text")
        if meta["bullet_count"] > MAX_BULLETS:
            flags.append("bullet_overload")
        if meta["notes_words"] == 0:
            flags.append("no_speaker_notes")
        if meta["body_words"] == 0 and meta["notes_words"] == 0:
            flags.append("empty_slide")
        slides.append({**meta, "text": page["text"], "flags": flags})

    n = len(slides)
    last_title = (slides[-1]["title"] if slides else "").lower()
    has_conclusion = any(
        k in last_title for k in ("conclusion", "summary", "takeaway", "thank", "future")
    ) or any(
        k in (s["title"] or "").lower() for s in slides[-2:] for k in ("conclusion", "summary", "takeaway")
    )

    deck_flags: List[str] = []
    if not has_conclusion:
        deck_flags.append("no_conclusion_slide")
    if n > 0 and sum(1 for s in slides if "no_speaker_notes" in s["flags"]) > n // 2:
        deck_flags.append("mostly_missing_notes")

    return {
        "material_id": str(mat["material_id"]),
        "deck_title": mat["title"],
        "slide_count": n,
        "estimated_minutes": round(n * 1.5, 1),  # ~90s/slide rule of thumb
        "deck_flags": deck_flags,
        "slides": slides,
    }


_COACH_SYSTEM = """\
You are an academic presentation coach reviewing a conference/defense slide deck.
Base every observation ONLY on the provided slide text and speaker notes — never
invent slide content. Be specific and constructive; reference slides by number.
Return ONLY valid JSON — no markdown fences.
"""

_COACH_TEMPLATE = """\
## Deck ({slide_count} slides)

{deck_text}

---

Return a JSON object with EXACTLY these keys:
{{
  "overall_impression": "<2-3 sentences on how this deck lands as a talk>",
  "structure_feedback": "<does the narrative arc work: opening, problem, method, results, close?>",
  "clarity_feedback":   "<where the story is hard to follow or overloaded>",
  "slide_suggestions": [
    {{"slide_num": <n>, "suggestion": "<one concrete improvement for this slide>"}}
  ],
  "strongest_slide": {{"slide_num": <n>, "why": "<one sentence>"}},
  "likely_audience_questions": ["<question an informed audience member would ask>", "..."]
}}
Give slide_suggestions for the 3-6 slides that most need work.
"""


def coach_deck(
    debate_id: str,
    openrouter_key: str,
    model_id: str = "",
    mode: ReasoningMode = "light",
) -> Dict[str, Any]:
    """Deterministic metrics + LLM coaching narrative for the session's deck."""
    data = deck_data(debate_id)

    deck_text = "\n\n".join(s["text"][:700] for s in data["slides"])
    if not model_id:
        model_id = get_model("readiness_report", mode)

    client = OpenRouterClient(api_key=openrouter_key)
    response = client.chat_completion(
        model=model_id,
        messages=[
            {"role": "system", "content": _COACH_SYSTEM},
            {"role": "user", "content": _COACH_TEMPLATE.format(
                slide_count=data["slide_count"], deck_text=deck_text)},
        ],
        temperature=0.4,
        max_tokens=1800,
        _debate_id=debate_id,
        _stage="presentation_coach",
    )
    coach = parse_llm_json(response["content"].strip(), stage="presentation_coach")
    return {**data, "coach": coach, "model_used": response.get("model", model_id)}
