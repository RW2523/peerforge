"""
Presentation Coach routes (concept 7.6)
=======================================
GET  /debates/{id}/presentation/deck     → deterministic deck structure + flags (no LLM)
POST /debates/{id}/presentation/coach    → deck metrics + LLM coaching narrative
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from ..auth import get_current_user, check_workspace_access
from ..debate_service import DebateService
from ..services.presentation_coach import deck_data, coach_deck

logger = logging.getLogger(__name__)
router = APIRouter(tags=["presentation"])


def _get_debate_or_404(debate_id: str):
    debate = DebateService().get_debate(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail=f"Debate {debate_id} not found")
    return debate


class CoachRequest(BaseModel):
    model_id: str = Field(default="")
    mode: Literal["light", "medium", "heavy"] = Field(default="light")


@router.get("/debates/{debate_id}/presentation/deck")
async def get_presentation_deck(
    debate_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Slide-by-slide structure metrics with honest flags. Fast, no LLM."""
    debate = _get_debate_or_404(debate_id)
    check_workspace_access(current_user, debate["workspace_id"])
    try:
        return deck_data(debate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Deck analysis failed for %s", debate_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/debates/{debate_id}/presentation/coach")
async def run_presentation_coach(
    debate_id: str,
    body: CoachRequest = CoachRequest(),
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Deck metrics + LLM coaching narrative (structure, clarity, per-slide
    suggestions, likely audience questions)."""
    if not x_openrouter_key:
        raise HTTPException(status_code=400, detail="X-OpenRouter-Key header is required")
    debate = _get_debate_or_404(debate_id)
    check_workspace_access(current_user, debate["workspace_id"])
    try:
        return coach_deck(debate_id, x_openrouter_key, body.model_id, body.mode)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Presentation coach failed for %s", debate_id)
        raise HTTPException(status_code=500, detail=str(exc))
