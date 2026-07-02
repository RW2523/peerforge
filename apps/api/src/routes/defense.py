"""
Academic Review & Feedback — API routes
========================================
All endpoints are scoped to an existing debate/session ID.

Flow:
  POST /debates/{id}/analyze-research            → trigger research analysis
  GET  /debates/{id}/research-profile            → get completed profile
  POST /debates/{id}/suggest-personas            → AI-suggested committee personas
  POST /debates/{id}/defense-questions/generate  → generate questions
  GET  /debates/{id}/defense-questions           → list questions
  POST /debates/{id}/answers                     → submit + evaluate answer
  GET  /debates/{id}/answers                     → list evaluated answers
  POST /debates/{id}/readiness-report            → generate report
  GET  /debates/{id}/readiness-report            → get report
  GET  /reasoning-modes                          → list available modes + model info
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException, Header, Depends, status
from pydantic import BaseModel, Field

from ..auth import get_current_user, check_workspace_access
from ..debate_service import DebateService
from ..services.research_analyzer import analyze_research, get_research_profile
from ..services.question_generator import generate_questions, get_questions
from ..services.answer_evaluator import evaluate_answer, get_answers
from ..services.readiness_reporter import generate_readiness_report, get_readiness_report
from ..services.persona_suggester import suggest_personas
from ..services.provenance import get_provenance
from ..services.reasoning_modes import MODES, mode_from_policy

logger = logging.getLogger(__name__)
router = APIRouter(tags=["defense"])

ReasoningModeType = Literal["light", "medium", "heavy"]


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_debate_or_404(debate_id: str):
    svc = DebateService()
    debate = svc.get_debate(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail=f"Debate {debate_id} not found")
    return debate


def _require_key(x_openrouter_key: Optional[str]) -> str:
    if not x_openrouter_key:
        raise HTTPException(
            status_code=400,
            detail="X-OpenRouter-Key header is required for this operation"
        )
    return x_openrouter_key


# ── Pydantic models ────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    model_id:   str              = Field(default="")
    max_chunks: int              = Field(default=20, ge=5, le=50)
    mode:       ReasoningModeType = Field(default="medium")


class SuggestPersonasRequest(BaseModel):
    mode: ReasoningModeType = Field(default="medium")


class GenerateQuestionsRequest(BaseModel):
    model_id:    str              = Field(default="")
    n_questions: int              = Field(default=15, ge=5, le=30)
    mode:        ReasoningModeType = Field(default="medium")


class SubmitAnswerRequest(BaseModel):
    question_id: str
    answer_text: str             = Field(..., min_length=10)
    model_id:    str             = Field(default="")
    mode:        ReasoningModeType = Field(default="medium")


class ReadinessReportRequest(BaseModel):
    model_id: str              = Field(default="")
    mode:     ReasoningModeType = Field(default="medium")


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/reasoning-modes")
async def list_reasoning_modes():
    """Return the three reasoning mode definitions and their model assignments."""
    return {"modes": MODES}


@router.post("/debates/{debate_id}/analyze-research")
async def trigger_research_analysis(
    debate_id: str,
    body: AnalyzeRequest = AnalyzeRequest(),
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Analyse uploaded research materials and build a structured profile."""
    key = _require_key(x_openrouter_key)
    debate = _get_debate_or_404(debate_id)
    check_workspace_access(current_user, debate["workspace_id"])

    # Resolve mode: body > policy_config fallback
    mode = body.mode or mode_from_policy(debate.get("policy_config") or {})

    try:
        profile = analyze_research(
            debate_id=debate_id,
            openrouter_key=key,
            model_id=body.model_id,
            max_chunks=body.max_chunks,
            mode=mode,
        )
        return {"status": "complete", "profile": _serialize(profile), "mode_used": mode}
    except Exception as exc:
        logger.exception("Research analysis failed for %s", debate_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/debates/{debate_id}/research-profile")
async def get_research_profile_route(
    debate_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Return the completed research profile for a session."""
    debate = _get_debate_or_404(debate_id)
    check_workspace_access(current_user, debate["workspace_id"])

    profile = get_research_profile(debate_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="No research profile found. Run POST /debates/{id}/analyze-research first."
        )
    return _serialize(profile)


@router.post("/debates/{debate_id}/suggest-personas")
async def suggest_committee_personas(
    debate_id: str,
    body: SuggestPersonasRequest = SuggestPersonasRequest(),
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Use the existing research profile to suggest 6 AI committee personas
    tailored to the research domain, methodology, and weak areas.

    Returns personas with names, roles, expertise, and model assignments
    based on the chosen reasoning mode.
    """
    key = _require_key(x_openrouter_key)
    debate = _get_debate_or_404(debate_id)
    check_workspace_access(current_user, debate["workspace_id"])

    profile = get_research_profile(debate_id)
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="Research profile not found. Run /analyze-research first."
        )

    mode = body.mode or mode_from_policy(debate.get("policy_config") or {})

    try:
        personas = suggest_personas(
            research_profile=dict(profile),
            openrouter_key=key,
            mode=mode,
        )
        return {
            "status":   "complete",
            "mode":     mode,
            "personas": personas,
            "mode_info": MODES.get(mode, {}),
        }
    except Exception as exc:
        logger.exception("Persona suggestion failed for %s", debate_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/debates/{debate_id}/defense-questions/generate")
async def trigger_question_generation(
    debate_id: str,
    body: GenerateQuestionsRequest = GenerateQuestionsRequest(),
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Generate panel-style review questions from the research profile."""
    key = _require_key(x_openrouter_key)
    debate = _get_debate_or_404(debate_id)
    check_workspace_access(current_user, debate["workspace_id"])

    mode = body.mode or mode_from_policy(debate.get("policy_config") or {})

    try:
        questions = generate_questions(
            debate_id=debate_id,
            openrouter_key=key,
            model_id=body.model_id,
            n_questions=body.n_questions,
            mode=mode,
        )
        return {
            "status":    "complete",
            "count":     len(questions),
            "questions": questions,
            "mode_used": mode,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Question generation failed for %s", debate_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/debates/{debate_id}/defense-questions")
async def list_defense_questions(
    debate_id: str,
    unanswered_only: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """List generated review questions (optionally filter to unanswered only)."""
    debate = _get_debate_or_404(debate_id)
    check_workspace_access(current_user, debate["workspace_id"])

    questions = get_questions(debate_id, unanswered_only=unanswered_only)
    return {"count": len(questions), "questions": questions}


@router.get("/debates/{debate_id}/provenance")
async def get_debate_provenance(
    debate_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Glass-Box lineage: every reviewer question with its hard-linked, sha256-
    verified source chunk — or flagged as an evidence gap when unsupported."""
    debate = _get_debate_or_404(debate_id)
    check_workspace_access(current_user, debate["workspace_id"])
    try:
        return get_provenance(debate_id)
    except Exception as exc:
        logger.exception("Provenance assembly failed for %s", debate_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/debates/{debate_id}/answers")
async def submit_answer(
    debate_id: str,
    body: SubmitAnswerRequest,
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Submit a student answer and receive a 6-axis AI evaluation."""
    key = _require_key(x_openrouter_key)
    debate = _get_debate_or_404(debate_id)
    check_workspace_access(current_user, debate["workspace_id"])

    mode = body.mode or mode_from_policy(debate.get("policy_config") or {})

    try:
        result = evaluate_answer(
            debate_id=debate_id,
            question_id=body.question_id,
            answer_text=body.answer_text,
            openrouter_key=key,
            model_id=body.model_id,
            mode=mode,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Answer evaluation failed for %s", debate_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/debates/{debate_id}/answers")
async def list_answers(
    debate_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Return all evaluated answers for a session."""
    debate = _get_debate_or_404(debate_id)
    check_workspace_access(current_user, debate["workspace_id"])

    answers = get_answers(debate_id)
    return {"count": len(answers), "answers": answers}


@router.post("/debates/{debate_id}/readiness-report")
async def trigger_readiness_report(
    debate_id: str,
    body: ReadinessReportRequest = ReadinessReportRequest(),
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Generate the readiness report from all evaluated answers."""
    key = _require_key(x_openrouter_key)
    debate = _get_debate_or_404(debate_id)
    check_workspace_access(current_user, debate["workspace_id"])

    mode = body.mode or mode_from_policy(debate.get("policy_config") or {})

    try:
        report = generate_readiness_report(
            debate_id=debate_id,
            openrouter_key=key,
            model_id=body.model_id,
            mode=mode,
        )
        return _serialize(report)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Readiness report failed for %s", debate_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/debates/{debate_id}/readiness-report")
async def get_readiness_report_route(
    debate_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Return the generated readiness report."""
    debate = _get_debate_or_404(debate_id)
    check_workspace_access(current_user, debate["workspace_id"])

    report = get_readiness_report(debate_id)
    if not report:
        raise HTTPException(
            status_code=404,
            detail="No readiness report found. Generate one via POST /debates/{id}/readiness-report"
        )
    return _serialize(report)


# ── Serialization helper ───────────────────────────────────────────────────

def _serialize(row: Dict) -> Dict:
    """Convert datetimes / UUIDs in a DB row to JSON-safe strings."""
    import uuid as _uuid
    from datetime import datetime
    result = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            result[k] = v.isoformat()
        elif isinstance(v, _uuid.UUID):
            result[k] = str(v)
        elif isinstance(v, list) and v and isinstance(v[0], _uuid.UUID):
            result[k] = [str(i) for i in v]
        else:
            result[k] = v
    return result
