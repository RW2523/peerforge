"""Meeting setup endpoints (M4 primitives)"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import Dict, Any
from ..auth import get_current_user, check_workspace_access
from ..meeting_setup_service import MeetingSetupService, MeetingSetupError
from ..schemas.setup import (
    DebateSetupRequest,
    DebateSetupResponse,
)

router = APIRouter()


@router.post("/debates/setup", response_model=DebateSetupResponse, status_code=status.HTTP_201_CREATED)
async def setup_debate(
    request: DebateSetupRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create a debate with participants + materials in one call (M4 setup primitives).

    Protected: Requires valid JWT and workspace access.
    """
    check_workspace_access(current_user, request.workspace_id)

    svc = MeetingSetupService()
    try:
        debate_id, participant_ids, material_ids = svc.create_setup(
            workspace_id=request.workspace_id,
            title=request.title,
            problem_statement=request.problem_statement,
            agenda=request.agenda,
            desired_outcomes=request.desired_outcomes,
            max_rounds=request.max_rounds,
            timebox_minutes=request.timebox_minutes,
            enable_host=request.enable_host,
            host_model_id=request.host_model_id,
            reasoning_mode=request.reasoning_mode or "medium",
            participants=[
                p.model_dump(exclude_none=True, by_alias=True) for p in request.participants
            ],
            materials=[m.model_dump(exclude_none=True) for m in (request.materials or [])],
        )
    except MeetingSetupError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return DebateSetupResponse(
        debate_id=debate_id,
        participant_ids=participant_ids,
        material_ids=material_ids,
    )
