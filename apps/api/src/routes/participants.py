"""Participants management endpoints"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Dict, Any, List
from ..auth import get_current_user, check_workspace_access
from ..debate_service import DebateService
from ..meeting_setup_service import MeetingSetupService

router = APIRouter()


class AddParticipantsRequest(BaseModel):
    participants: List[Dict[str, Any]]


class AddParticipantsResponse(BaseModel):
    participant_ids: List[str]


@router.post("/debates/{debate_id}/participants", response_model=AddParticipantsResponse)
async def add_participants_to_debate(
    debate_id: str,
    request: AddParticipantsRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Add participants to an existing debate.
    Useful for adding participants after debate creation (e.g., after file uploads).
    """
    # Get debate and verify access
    debate_service = DebateService()
    debate = debate_service.get_debate(debate_id)
    
    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debate {debate_id} not found"
        )
    
    check_workspace_access(current_user, debate['workspace_id'])
    
    # Add participants
    setup_service = MeetingSetupService()
    try:
        participant_ids = setup_service._insert_participants(
            workspace_id=debate['workspace_id'],
            debate_id=debate_id,
            participants=request.participants
        )
        
        return AddParticipantsResponse(participant_ids=participant_ids)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to add participants: {str(e)}"
        )
