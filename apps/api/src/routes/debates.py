"""Debate-related endpoints"""
from fastapi import APIRouter, HTTPException, status, Depends, Query, Header
from typing import Dict, Any, Optional, List
from ..auth import get_current_user, check_workspace_access
from ..config import settings
from ..debate_engine import DebateEngine
from ..debate_service import DebateService
from ..openrouter_client import OpenRouterAuthError, OpenRouterError
from ..state_machine import StateTransitionError
from ..schemas.debates import (
    DebateRunRequest,
    DebateRunResponse,
    CreateDebateRequest,
    DebateResponse,
    InterveneRequest,
    InterventionResponse,
    DebateListResponse,
    DebateListItem,
    ExtendDebateRequest,
)

router = APIRouter()


@router.get("/debates", response_model=DebateListResponse)
async def list_debates(
    workspace_id: str = Query(..., description="Workspace ID to filter debates"),
    limit: int = Query(20, ge=1, le=100, description="Max debates to return"),
    cursor: Optional[str] = Query(None, description="Cursor for pagination"),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """
    List debates in a workspace with cursor pagination.
    Protected by workspace access checks.
    """
    import traceback
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Check workspace access
        if current_user:
            check_workspace_access(current_user, workspace_id)
        
        service = DebateService()
        
        # Get debates from DB
        debates_data = service.list_debates(workspace_id, limit=limit, cursor=cursor)
        
        items = [
            DebateListItem(
                debate_id=d["debate_id"],
                workspace_id=d["workspace_id"],
                title=d["title"],
                state=d["state"],
                created_at=d["created_at"].isoformat() if d.get("created_at") else None,
                updated_at=d["updated_at"].isoformat() if d.get("updated_at") else None,
                started_at=d["started_at"].isoformat() if d.get("started_at") else None,
                ended_at=d["ended_at"].isoformat() if d.get("ended_at") else None,
            )
            for d in debates_data["items"]
        ]
        
        return DebateListResponse(
            items=items,
            next_cursor=debates_data.get("next_cursor")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing debates: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list debates: {str(e)}"
        )


@router.post("/debates/run", response_model=DebateRunResponse, status_code=status.HTTP_200_OK)
async def run_debate(request: DebateRunRequest):
    """
    Run a 5-turn debate with 3 agents
    
    M1 scope:
    - Accepts problem statement + 3 agent configs + OpenRouter key
    - Runs deterministic 5-turn round-robin
    - Persists debate + events to database
    - Returns summary + minutes + action items + event history
    
    Raises:
        400: Invalid request (wrong number of agents, missing fields)
        401: Invalid OpenRouter API key
        500: Internal server error
    """
    # Validate agent count
    if len(request.agents) != 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly 3 agents required for M1"
        )
    
    try:
        # Initialize engine with BYOK
        engine = DebateEngine(openrouter_api_key=request.openrouter_api_key)
        
        # Convert agents to dict format
        agents_list = [
            {
                'name': agent.name,
                'role': agent.role,
                'model_id': agent.model_id
            }
            for agent in request.agents
        ]
        
        # Run debate
        result = engine.run_debate(
            problem_statement=request.problem_statement,
            agents=agents_list,
            debate_title=request.debate_title
        )
        
        return result
    
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
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/debates/{debate_id}", response_model=DebateResponse)
async def get_debate(
    debate_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get debate by ID
    
    Protected: Requires valid JWT and workspace access
    
    Raises:
        401: Unauthorized
        403: Forbidden (workspace access denied)
        404: Debate not found
    """
    service = DebateService()
    debate = service.get_debate(debate_id)
    
    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debate {debate_id} not found"
        )
    
    # Check workspace access (raises HTTPException if denied)
    check_workspace_access(current_user, debate['workspace_id'])
    
    # Fetch participants
    participants = service.get_participants(debate_id)
    participant_list = [
        {
            "participant_id": p['participant_id'],
            "participant_type": p.get('participant_type', 'agent'),
            "role_name": p.get('role_name', 'Unknown'),
            "agent_config": p.get('agent_config'),
            "created_at": p['created_at'].isoformat() if p.get('created_at') else None
        }
        for p in participants
    ]
    
    return DebateResponse(
        debate_id=debate['debate_id'],
        workspace_id=debate['workspace_id'],
        title=debate['title'],
        state=debate['state'],
        policy_config=debate.get('policy_config'),
        created_at=debate['created_at'].isoformat(),
        participants=participant_list,
        autonomous_mode=debate.get('autonomous_mode', False),
        autonomous_status=debate.get('autonomous_status'),
        auto_turn_delay_seconds=debate.get('auto_turn_delay_seconds', 10)
    )


@router.post("/debates", response_model=DebateResponse, status_code=status.HTTP_201_CREATED)
async def create_debate(
    request: CreateDebateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create new debate in pending state (M2)
    
    Protected: Requires valid JWT
    
    Raises:
        401: Unauthorized (missing/invalid token)
        403: Forbidden (workspace access denied)
        400: Invalid request
        500: Internal server error
    """
    # Verify user has access to requested workspace
    check_workspace_access(current_user, request.workspace_id)

    # Paywall: block creating another review session past the plan's quota.
    from ..services.plans import require_session_quota
    require_session_quota(request.workspace_id)

    try:
        service = DebateService()
        debate = service.create_debate(
            workspace_id=request.workspace_id,
            title=request.title,
            policy_config=request.policy_config
        )
        
        return DebateResponse(
            debate_id=debate['debate_id'],
            workspace_id=debate['workspace_id'],
            title=debate['title'],
            state=debate['state'],
            created_at=debate['created_at'].isoformat()
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/debates/{debate_id}/start", response_model=DebateResponse)
async def start_debate(
    debate_id: str,
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Start debate (pending -> running)
    
    Protected: Requires valid JWT and workspace access
    
    Raises:
        401: Unauthorized
        403: Forbidden (workspace access denied)
        400: Invalid state transition
        404: Debate not found
        500: Internal server error
    """
    service = DebateService()
    debate = service.get_debate(debate_id)
    
    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debate {debate_id} not found"
        )
    
    # Check workspace access (raises HTTPException if denied)
    check_workspace_access(current_user, debate['workspace_id'])

    # A session cannot start without a panel (participants may be added after
    # creation — deferred staffing — but must exist before starting).
    participants = service.get_participants(debate_id)
    if not participants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add at least one panel member before starting the session.",
        )

    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Starting debate {debate_id} - current state: {debate.get('state')}")
        debate = service.start_debate(debate_id)
        logger.info(f"Debate {debate_id} started successfully - new state: {debate.get('state')}")

        # Queue embedding backfill so AI reviewers have full semantic RAG from the start
        resolved_key = x_openrouter_key or settings.openrouter_api_key
        if resolved_key:
            try:
                from src.tasks.material_processing import generate_debate_embeddings
                generate_debate_embeddings.delay(debate_id, resolved_key)
                logger.info(f"Embedding backfill queued for debate {debate_id}")
            except Exception as embed_err:
                logger.warning(f"Could not queue embedding backfill: {embed_err}")
        
        return DebateResponse(
            debate_id=debate['debate_id'],
            workspace_id=debate['workspace_id'],
            title=debate['title'],
            state=debate['state'],
            created_at=debate['created_at'].isoformat()
        )
    
    except ValueError as e:
        logger.error(f"ValueError starting debate {debate_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except StateTransitionError as e:
        logger.error(f"StateTransitionError starting debate {debate_id}: {str(e)} - current state: {debate.get('state')}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start debate: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error starting debate {debate_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/debates/{debate_id}/pause", response_model=DebateResponse)
async def pause_debate(
    debate_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Pause debate (running -> paused)
    
    Protected: Requires valid JWT and workspace access
    
    Raises:
        401: Unauthorized
        403: Forbidden
        400: Invalid state transition
        404: Debate not found
        500: Internal server error
    """
    service = DebateService()
    debate = service.get_debate(debate_id)
    
    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debate {debate_id} not found"
        )
    
    check_workspace_access(current_user, debate['workspace_id'])
    
    try:
        debate = service.pause_debate(debate_id)
        
        return DebateResponse(
            debate_id=debate['debate_id'],
            workspace_id=debate['workspace_id'],
            title=debate['title'],
            state=debate['state'],
            created_at=debate['created_at'].isoformat()
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except StateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/debates/{debate_id}/resume", response_model=DebateResponse)
async def resume_debate(
    debate_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Resume debate (paused -> running)
    
    Protected: Requires valid JWT and workspace access
    
    Raises:
        401: Unauthorized
        403: Forbidden
        400: Invalid state transition
        404: Debate not found
        500: Internal server error
    """
    service = DebateService()
    debate = service.get_debate(debate_id)
    
    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debate {debate_id} not found"
        )
    
    check_workspace_access(current_user, debate['workspace_id'])
    
    try:
        debate = service.resume_debate(debate_id)
        
        return DebateResponse(
            debate_id=debate['debate_id'],
            workspace_id=debate['workspace_id'],
            title=debate['title'],
            state=debate['state'],
            created_at=debate['created_at'].isoformat()
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except StateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/debates/{debate_id}/intervene", response_model=InterventionResponse)
async def intervene_debate(
    debate_id: str,
    request: InterveneRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Add intervention to debate
    
    Protected: Requires valid JWT and workspace access
    
    Raises:
        401: Unauthorized
        403: Forbidden
        400: Invalid state for intervention
        404: Debate not found
        500: Internal server error
    """
    service = DebateService()
    debate = service.get_debate(debate_id)
    
    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debate {debate_id} not found"
        )
    
    check_workspace_access(current_user, debate['workspace_id'])
    
    try:
        result = service.intervene(
            debate_id=debate_id,
            message=request.message,
            tagged_agents=request.tagged_agents
        )
        
        return InterventionResponse(**result)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except StateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/debates/{debate_id}/end", response_model=DebateResponse)
async def end_debate(
    debate_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    End debate (running/paused -> ended)
    
    Protected: Requires valid JWT and workspace access
    
    Raises:
        401: Unauthorized
        403: Forbidden
        400: Invalid state transition
        404: Debate not found
        500: Internal server error
    """
    service = DebateService()
    debate = service.get_debate(debate_id)
    
    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debate {debate_id} not found"
        )
    
    check_workspace_access(current_user, debate['workspace_id'])
    
    try:
        debate = service.end_debate(debate_id)
        
        return DebateResponse(
            debate_id=debate['debate_id'],
            workspace_id=debate['workspace_id'],
            title=debate['title'],
            state=debate['state'],
            created_at=debate['created_at'].isoformat()
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except StateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )



@router.patch("/debates/{debate_id}/extend")
async def extend_debate(
    debate_id: str,
    request: ExtendDebateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Extend debate rounds or time during an active debate
    
    This allows extending the discussion when more time is needed.
    Can extend rounds (for rounds-based meetings) or add time (for time-based meetings).
    
    Raises:
        401: Unauthorized
        403: Forbidden (workspace access denied)
        404: Debate not found
        400: Invalid request (can't extend both rounds and time, or neither)
    """
    if not request.extend_rounds and not request.extend_minutes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify either extend_rounds or extend_minutes"
        )
    
    if request.extend_rounds and request.extend_minutes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot extend both rounds and time in the same request"
        )
    
    service = DebateService()
    debate = service.get_debate(debate_id)
    
    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debate {debate_id} not found"
        )
    
    check_workspace_access(current_user, debate['workspace_id'])
    
    try:
        policy_config = debate.get('policy_config') or {}
        policy_updates = {}
        
        if request.extend_rounds:
            current_rounds = policy_config.get('max_rounds', 3)
            policy_updates['max_rounds'] = current_rounds + request.extend_rounds
        
        if request.extend_minutes:
            current_minutes = policy_config.get('timebox_minutes', 30)
            policy_updates['timebox_minutes'] = current_minutes + request.extend_minutes
        
        updated = service.update_policy_config(debate_id, policy_updates)
        
        return {
            "debate_id": debate_id,
            "policy_config": updated['policy_config'],
            "message": f"Extended by {request.extend_rounds or 0} rounds and {request.extend_minutes or 0} minutes"
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.delete("/debates/{debate_id}")
async def delete_debate(
    debate_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """
    Delete a debate and all associated data.
    Protected by workspace access checks.
    """
    service = DebateService()
    debate = service.get_debate(debate_id)
    
    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debate {debate_id} not found"
        )
    
    # Check workspace access
    if current_user:
        check_workspace_access(current_user, debate['workspace_id'])
    
    try:
        # Delete debate and associated data (events, participants, etc.)
        service.delete_debate(debate_id)
        
        return {
            "success": True,
            "message": f"Debate {debate_id} deleted successfully"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete debate: {str(e)}"
        )


# NOTE: Additional endpoints have been extracted for maintainability:
#  - Turn orchestration: see routes/turns.py
#  - Setup endpoint: see routes/setup.py
#  - Summary endpoints: see routes/summary.py
