"""Summary and outputs endpoints (M3)"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import Dict, Any
from ..auth import get_current_user, check_workspace_access
from ..debate_service import DebateService
from ..summary_service import SummaryService
from ..openrouter_client import OpenRouterAuthError, OpenRouterError
from ..schemas.summary import (
    SummarizeRequest,
    SummaryResponse,
)

router = APIRouter()


@router.post("/debates/{debate_id}/summarize", response_model=SummaryResponse, status_code=status.HTTP_200_OK)
async def generate_summary(
    debate_id: str,
    request: SummarizeRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Generate end-of-meeting summary, minutes, and action items (M3)
    
    Requires debate to be in 'ended' state.
    Uses OpenRouter BYOK - key is never stored.
    
    Protected: Requires valid JWT and workspace access
    
    Raises:
        400: Invalid state (debate not ended)
        401: Invalid OpenRouter key
        403: Forbidden (workspace access denied)
        404: Debate not found
        500: Internal server error
    """
    # Check debate exists and get workspace for auth check
    service = DebateService()
    debate = service.get_debate(debate_id)
    
    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debate {debate_id} not found"
        )
    
    # Check workspace access
    check_workspace_access(current_user, debate['workspace_id'])
    
    # Verify debate is in ended state
    if debate['state'] != 'ended':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Debate must be in 'ended' state to generate summary. Current state: {debate['state']}"
        )
    
    try:
        summary_service = SummaryService()
        outputs = summary_service.generate_summary(
            debate_id=debate_id,
            openrouter_api_key=request.openrouter_api_key,
            model_id=request.model_id if hasattr(request, 'model_id') else "openai/gpt-4o-mini"  # Cost-optimized
        )
        
        # The summary_service.generate_summary already saves to DB
        # Retrieve the saved record which includes output_id
        saved_summary = summary_service.get_summary(debate_id)
        
        if not saved_summary:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Summary was generated but failed to save to database"
            )
        
        return SummaryResponse(
            output_id=str(saved_summary['output_id']),
            debate_id=debate_id,
            summary=saved_summary['summary'],
            minutes=saved_summary['minutes'],
            action_items=saved_summary['action_items'],
            generated_at=saved_summary['generated_at'].isoformat() if hasattr(saved_summary['generated_at'], 'isoformat') else str(saved_summary['generated_at']),
            model_used=saved_summary.get('model_used')
        )
    
    except OpenRouterAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"OpenRouter authentication failed: {str(e)}"
        )
    except OpenRouterError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OpenRouter API error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {str(e)}"
        )


@router.get("/debates/{debate_id}/summary", response_model=SummaryResponse)
async def get_summary(
    debate_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get previously generated summary for a debate (M3)
    
    Protected: Requires valid JWT and workspace access
    
    Raises:
        401: Unauthorized
        403: Forbidden (workspace access denied)
        404: Debate or summary not found
        500: Internal server error
    """
    # Check debate exists and get workspace for auth check
    service = DebateService()
    debate = service.get_debate(debate_id)
    
    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debate {debate_id} not found"
        )
    
    # Check workspace access
    check_workspace_access(current_user, debate['workspace_id'])
    
    try:
        summary_service = SummaryService()
        outputs = summary_service.get_summary(debate_id)

        if not outputs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No summary found for debate {debate_id}. Generate one first using POST /debates/{debate_id}/summarize"
            )

        generated_at = outputs.get('generated_at')
        if hasattr(generated_at, 'isoformat'):
            generated_at = generated_at.isoformat()
        else:
            generated_at = str(generated_at) if generated_at else ''

        return SummaryResponse(
            output_id=str(outputs['output_id']),
            debate_id=str(outputs['debate_id']),
            summary=outputs.get('summary', ''),
            minutes=outputs.get('minutes', ''),
            action_items=outputs.get('action_items') or [],
            generated_at=generated_at,
            model_used=outputs.get('model_used')
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve summary: {str(e)}"
        )
