"""
Academic Assessment Matrix — API routes
=======================================
POST /debates/{id}/assessment/generate  → build a fresh ten-dimension assessment
GET  /debates/{id}/assessment           → latest assessment
GET  /debates/{id}/assessment/history   → prior overall scores (progress over time)
"""
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from typing import Literal

from ..auth import require_auth
from ..services.academic_assessment import (
    generate_assessment,
    get_latest_assessment,
    get_assessment_history,
)
from ..services.certificate import build_certificate

router = APIRouter(tags=["assessment"])


class GenerateAssessmentRequest(BaseModel):
    mode: Literal["light", "medium", "heavy"] = "light"
    trigger_source: str = "manual"
    model_id: str = ""


@router.post("/debates/{debate_id}/assessment/generate")
async def create_assessment(
    debate_id: str,
    request: GenerateAssessmentRequest,
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
    _workspace_id: str = Depends(require_auth),
):
    """Generate the ten-dimension academic assessment from all session evidence."""
    if not x_openrouter_key:
        raise HTTPException(
            status_code=400,
            detail="X-OpenRouter-Key header is required for this operation",
        )
    try:
        return generate_assessment(
            debate_id=debate_id,
            openrouter_key=x_openrouter_key,
            mode=request.mode,
            trigger_source=request.trigger_source,
            model_id=request.model_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/debates/{debate_id}/assessment")
async def latest_assessment(
    debate_id: str,
    _workspace_id: str = Depends(require_auth),
):
    """Return the most recent assessment for this session."""
    result = get_latest_assessment(debate_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No assessment yet. Generate one via POST /debates/{id}/assessment/generate",
        )
    return result


@router.get("/debates/{debate_id}/assessment/history")
async def assessment_history(
    debate_id: str,
    _workspace_id: str = Depends(require_auth),
):
    """Return prior assessments (newest first) for progress tracking."""
    return {"debate_id": debate_id, "assessments": get_assessment_history(debate_id)}


@router.get("/debates/{debate_id}/certificate")
async def readiness_certificate(
    debate_id: str,
    _workspace_id: str = Depends(require_auth),
):
    """Assemble the tamper-evident Review-Readiness Certificate: per-dimension
    trajectory, the evidence ledger it rests on, and a sha256 ledger anchor."""
    try:
        return build_certificate(debate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
