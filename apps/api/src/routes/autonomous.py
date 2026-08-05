"""
Autonomous Debate API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from ..auth import authorize_debate, get_current_user
from ..config import resolve_openrouter_key
from ..autonomous_debate_service import autonomous_service

router = APIRouter(prefix="/api/debates", tags=["autonomous"])


class StartAutonomousRequest(BaseModel):
    # A zero delay turns the autonomous loop into a tight paid-API spin.
    auto_turn_delay_seconds: int = Field(default=10, ge=1, le=3600)


@router.post("/{debate_id}/start-autonomous")
async def start_autonomous(
    debate_id: str,
    request: StartAutonomousRequest,
    x_openrouter_key: Optional[str] = Header(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Start autonomous YOLO debate"""
    authorize_debate(debate_id, current_user)
    x_openrouter_key = resolve_openrouter_key(x_openrouter_key)
    
    # Get API key from header (BYOK model)
    api_key = x_openrouter_key
    
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="OpenRouter API key required. Please add your API key in Settings."
        )
    
    try:
        result = await autonomous_service.start_autonomous_debate(
            debate_id=debate_id,
            openrouter_api_key=api_key,
            auto_turn_delay=request.auto_turn_delay_seconds
        )
    except ValueError as exc:
        # "not started yet" and "no such session" are the caller's situation.
        raise HTTPException(status_code=400, detail=str(exc))

    return result


@router.post("/{debate_id}/pause-autonomous")
async def pause_autonomous(
    debate_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Pause autonomous debate"""
    authorize_debate(debate_id, current_user)
    await autonomous_service.pause_autonomous_debate(debate_id)
    return {"status": "paused"}


@router.post("/{debate_id}/resume-autonomous")
async def resume_autonomous(
    debate_id: str,
    x_openrouter_key: Optional[str] = Header(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Resume autonomous debate"""
    authorize_debate(debate_id, current_user)
    x_openrouter_key = resolve_openrouter_key(x_openrouter_key)
    # Get API key from header (needed to restart background task)
    api_key = x_openrouter_key
    
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="OpenRouter API key required to resume autonomous debate."
        )
    
    await autonomous_service.resume_autonomous_debate(debate_id, api_key)
    return {"status": "resumed"}


@router.get("/{debate_id}/autonomous-status")
async def get_autonomous_status(
    debate_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get autonomous debate status"""
    authorize_debate(debate_id, current_user)
    status = autonomous_service._get_debate_status(debate_id)
    is_running = debate_id in autonomous_service.running_debates
    
    return {
        "status": status,
        "is_running": is_running,
        "has_background_task": is_running
    }
