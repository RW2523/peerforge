"""
Preflight API Routes
Endpoints for agent preparation orchestration
"""

import psycopg2
from psycopg2.extras import Json
from fastapi import APIRouter, HTTPException, status, Depends, Header
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.config import settings
from src.auth import require_auth
from src.database import get_cursor
from src.tasks.preflight import orchestrate_preflight
from src.services.memory_retrieval import get_query_embedding

router = APIRouter()


# Request/Response Models

class PreflightStartResponse(BaseModel):
    run_id: str
    debate_id: str
    status: str
    participant_count: int
    participant_runs: List[Dict[str, Any]]


class ParticipantRunStatus(BaseModel):
    participant_run_id: str
    participant_id: str
    agent_id: Optional[str]
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error: Optional[str]
    skip_reason: Optional[str]
    prep_pack_knowledge_id: Optional[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PreflightStatusResponse(BaseModel):
    run_id: str
    debate_id: str
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error: Optional[str]
    participant_runs: List[ParticipantRunStatus]


class PreflightRetryRequest(BaseModel):
    participant_id: str


class PreflightSkipRequest(BaseModel):
    participant_id: str
    reason: str


class PreflightActionResponse(BaseModel):
    participant_run_id: str
    participant_id: str
    status: str
    message: str


# Helper functions

def check_workspace_access(workspace_id: str, auth_workspace_id: str):
    """Check if user has access to workspace"""
    if workspace_id != auth_workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to workspace"
        )


def get_debate_workspace(debate_id: str) -> str:
    """Get workspace_id for a debate"""
    conn = psycopg2.connect(settings.database_url)
    cursor = get_cursor(conn)
    try:
        cursor.execute("SELECT workspace_id FROM debates WHERE debate_id = %s", (debate_id,))
        result = cursor.fetchone()
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Debate {debate_id} not found"
            )
        return result['workspace_id']
    finally:
        cursor.close()
        conn.close()


# Endpoints

@router.post("/debates/{debate_id}/preflight/start", response_model=PreflightStartResponse)
def start_preflight(
    debate_id: str,
    workspace_id: str = Depends(require_auth),
    x_openrouter_key: Optional[str] = Header(None)
):
    """
    Start preflight preparation for all participants in a debate
    
    Creates a preflight run and enqueues tasks to generate prep packs for each participant.
    
    BYOK Enhancement (TICKET-13C.1):
    - Optional X-OpenRouter-Key header enables semantic retrieval
    - If provided, generates query embeddings for each participant at start time
    - Stores embeddings (not key) in participant_runs.metadata
    - This enables semantic retrieval without storing OpenRouter keys server-side
    
    Protected: Requires valid JWT and workspace access
    """
    # Check workspace access
    debate_workspace = get_debate_workspace(debate_id)
    check_workspace_access(debate_workspace, workspace_id)
    
    conn = psycopg2.connect(settings.database_url)
    cursor = get_cursor(conn)
    
    try:
        # Check if a preflight run already exists for this debate
        cursor.execute("""
            SELECT run_id, status FROM preflight_runs WHERE debate_id = %s
        """, (debate_id,))
        
        existing_run = cursor.fetchone()
        if existing_run:
            run_id = existing_run['run_id']
            existing_status = existing_run['status']
            if existing_status in ('queued', 'running'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Preflight already {existing_status} for this debate"
                )
            
            # Delete old run to start fresh
            cursor.execute("DELETE FROM preflight_runs WHERE run_id = %s", (run_id,))
            conn.commit()
        
        # Create new preflight run
        cursor.execute("""
            INSERT INTO preflight_runs (run_id, debate_id, status, created_at)
            VALUES (gen_random_uuid(), %s, 'queued', NOW())
            RETURNING run_id
        """, (debate_id,))
        
        run_id = cursor.fetchone()['run_id']
        
        # Get participants, policy config, and workspace settings for query embedding
        cursor.execute("""
            SELECT p.participant_id, p.agent_config, d.policy_config,
                   w.settings->>'embeddings_model_id' AS embeddings_model
            FROM participants p
            JOIN debates d ON p.debate_id = d.debate_id
            JOIN workspaces w ON d.workspace_id = w.workspace_id
            WHERE d.debate_id = %s
        """, (debate_id,))
        
        participants = cursor.fetchall()
        
        if not participants:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No participants found for this debate"
            )
        
        # Get common data for query embedding generation (TICKET-13C.1)
        policy_config = participants[0]['policy_config'] if participants else {}
        embeddings_model_id = participants[0]['embeddings_model'] if participants and participants[0]['embeddings_model'] else 'openai/text-embedding-3-small'
        problem_statement = policy_config.get('problem_statement', '') if policy_config else ''
        
        # Store OpenRouter key in policy_config for preflight task to use (temporary)
        if x_openrouter_key and policy_config is not None:
            policy_config['openrouter_key'] = x_openrouter_key
            cursor.execute("""
                UPDATE debates 
                SET policy_config = %s, updated_at = NOW()
                WHERE debate_id = %s
            """, (Json(policy_config), debate_id))
            conn.commit()
            print(f"✅ OpenRouter key stored in policy_config for preflight generation")
        
        # Create participant run entries with query embeddings (BYOK-safe)
        participant_runs = []
        for participant in participants:
            participant_id = participant['participant_id']
            agent_config = participant['agent_config']
            agent_id = agent_config.get('agent_id') if agent_config else None
            
            # Generate query embedding if OpenRouter key provided (BYOK: not stored)
            query_embedding = None
            if x_openrouter_key and problem_statement:
                system_prompt = agent_config.get('system_prompt', '') if agent_config else ''
                semantic_query = f"{problem_statement[:300]}\n\nRole: {system_prompt[:200]}"
                query_embedding = get_query_embedding(semantic_query, x_openrouter_key, embeddings_model_id)
            
            # Store embedding vector (not key) in metadata
            initial_metadata = {}
            if query_embedding:
                initial_metadata = {
                    'query_embedding': query_embedding,
                    'query_embedding_model_id': embeddings_model_id,
                    'semantic_query_generated_at': datetime.utcnow().isoformat()
                }
            
            cursor.execute("""
                INSERT INTO preflight_participant_runs (
                    participant_run_id, run_id, participant_id, agent_id, status, metadata
                ) VALUES (
                    gen_random_uuid(), %s, %s, %s, 'queued', %s
                )
                RETURNING participant_run_id, participant_id, agent_id, status
            """, (run_id, participant_id, agent_id, Json(initial_metadata)))
            
            participant_run = cursor.fetchone()
            participant_runs.append({
                'participant_run_id': participant_run['participant_run_id'],
                'participant_id': participant_run['participant_id'],
                'agent_id': participant_run['agent_id'],
                'status': participant_run['status'],
                'has_query_embedding': query_embedding is not None
            })
        
        conn.commit()

        # If we have a BYOK key, also queue embedding generation for any un-embedded chunks.
        # This covers the common case where files were uploaded before the key was available.
        if x_openrouter_key:
            try:
                from src.tasks.material_processing import generate_debate_embeddings
                generate_debate_embeddings.delay(debate_id, x_openrouter_key)
                print(f"✅ Embedding backfill queued for debate {debate_id}")
            except Exception as embed_err:
                print(f"⚠️  Could not queue embedding backfill: {embed_err}")

        # Import threading to run preflight in background
        import threading
        from src.tasks.preflight import orchestrate_preflight_impl
        
        # Start preflight in background thread (non-blocking)
        def run_preflight_background():
            try:
                print(f"🔄 Starting preflight in background: run_id={run_id}, debate_id={debate_id}")
                orchestrate_preflight_impl(run_id, debate_id)
                print(f"✅ Preflight completed: run_id={run_id}")
            except Exception as e:
                print(f"❌ Background preflight failed: {e}")
                import traceback
                traceback.print_exc()
        
        # Launch background thread
        thread = threading.Thread(target=run_preflight_background, daemon=True)
        thread.start()
        print(f"✅ Preflight started in background thread, returning immediately")
        
        # Return immediately with initial status (frontend will poll for updates)
        return PreflightStartResponse(
            run_id=run_id,
            debate_id=debate_id,
            status='running',  # Set to running since background thread started
            participant_count=len(participant_runs),
            participant_runs=participant_runs
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"❌ Preflight route error: {e}")
        print(f"❌ Error type: {type(e)}")
        traceback.print_exc()
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start preflight: {str(e)}"
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/debates/{debate_id}/preflight/status", response_model=PreflightStatusResponse)
def get_preflight_status(
    debate_id: str,
    workspace_id: str = Depends(require_auth)
):
    """
    Get preflight preparation status for a debate
    
    Returns overall run status and per-participant progress.
    
    Protected: Requires valid JWT and workspace access
    """
    # Check workspace access
    debate_workspace = get_debate_workspace(debate_id)
    check_workspace_access(debate_workspace, workspace_id)
    
    conn = psycopg2.connect(settings.database_url)
    cursor = get_cursor(conn)
    
    try:
        # Get preflight run
        cursor.execute("""
            SELECT run_id, debate_id, status, created_at, started_at, completed_at, error
            FROM preflight_runs
            WHERE debate_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (debate_id,))
        
        run = cursor.fetchone()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No preflight run found for this debate"
            )
        
        run_id = run['run_id']
        debate_id = run['debate_id']
        run_status = run['status']
        created_at = run['created_at']
        started_at = run['started_at']
        completed_at = run['completed_at']
        error = run['error']
        
        # Get participant runs
        cursor.execute("""
            SELECT 
                participant_run_id, participant_id, agent_id, status,
                started_at, completed_at, error, skip_reason,
                prep_pack_knowledge_id, metadata
            FROM preflight_participant_runs
            WHERE run_id = %s
            ORDER BY started_at ASC NULLS LAST
        """, (run_id,))
        
        participant_runs = []
        for row in cursor.fetchall():
            participant_runs.append(ParticipantRunStatus(
                participant_run_id=row['participant_run_id'],
                participant_id=row['participant_id'],
                agent_id=row['agent_id'],
                status=row['status'],
                started_at=row['started_at'],
                completed_at=row['completed_at'],
                error=row['error'],
                skip_reason=row['skip_reason'],
                prep_pack_knowledge_id=row['prep_pack_knowledge_id'],
                metadata=row['metadata'] or {}
            ))
        
        return PreflightStatusResponse(
            run_id=run_id,
            debate_id=debate_id,
            status=run_status,
            created_at=created_at,
            started_at=started_at,
            completed_at=completed_at,
            error=error,
            participant_runs=participant_runs
        )
    
    finally:
        cursor.close()
        conn.close()


@router.post("/debates/{debate_id}/preflight/retry", response_model=PreflightActionResponse)
def retry_participant_preflight(
    debate_id: str,
    request: PreflightRetryRequest,
    workspace_id: str = Depends(require_auth)
):
    """
    Retry preflight preparation for a specific participant
    
    Only allowed if participant status is 'failed'.
    
    Protected: Requires valid JWT and workspace access
    """
    # Check workspace access
    debate_workspace = get_debate_workspace(debate_id)
    check_workspace_access(debate_workspace, workspace_id)
    
    conn = psycopg2.connect(settings.database_url)
    cursor = get_cursor(conn)
    
    try:
        # Get current run and participant run
        cursor.execute("""
            SELECT pr.run_id, pr.participant_run_id, pr.status
            FROM preflight_runs r
            JOIN preflight_participant_runs pr ON r.run_id = pr.run_id
            WHERE r.debate_id = %s AND pr.participant_id = %s
            ORDER BY r.created_at DESC
            LIMIT 1
        """, (debate_id, request.participant_id))
        
        result = cursor.fetchone()
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Participant preflight run not found"
            )
        
        run_id = result['run_id']
        participant_run_id = result['participant_run_id']
        current_status = result['status']
        
        if current_status != 'failed':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Can only retry failed runs. Current status: {current_status}"
            )
        
        # Reset participant run to queued
        cursor.execute("""
            UPDATE preflight_participant_runs
            SET status = 'queued', error = NULL, started_at = NULL, completed_at = NULL
            WHERE participant_run_id = %s
        """, (participant_run_id,))
        conn.commit()
        
        # Re-enqueue the task
        from src.tasks.preflight import prepare_participant_preflight
        prepare_participant_preflight(participant_run_id, request.participant_id, debate_id)
        
        return PreflightActionResponse(
            participant_run_id=participant_run_id,
            participant_id=request.participant_id,
            status='queued',
            message='Retry queued successfully'
        )
    
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry: {str(e)}"
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/debates/{debate_id}/preflight/skip", response_model=PreflightActionResponse)
def skip_participant_preflight(
    debate_id: str,
    request: PreflightSkipRequest,
    workspace_id: str = Depends(require_auth)
):
    """
    Skip preflight preparation for a specific participant
    
    Allowed if participant status is queued, running, or failed.
    Records skip reason for audit trail.
    
    Protected: Requires valid JWT and workspace access
    """
    # Check workspace access
    debate_workspace = get_debate_workspace(debate_id)
    check_workspace_access(debate_workspace, workspace_id)
    
    conn = psycopg2.connect(settings.database_url)
    cursor = get_cursor(conn)
    
    try:
        # Get current run and participant run
        cursor.execute("""
            SELECT pr.run_id, pr.participant_run_id, pr.status
            FROM preflight_runs r
            JOIN preflight_participant_runs pr ON r.run_id = pr.run_id
            WHERE r.debate_id = %s AND pr.participant_id = %s
            ORDER BY r.created_at DESC
            LIMIT 1
        """, (debate_id, request.participant_id))
        
        result = cursor.fetchone()
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Participant preflight run not found"
            )
        
        run_id = result['run_id']
        participant_run_id = result['participant_run_id']
        current_status = result['status']
        
        if current_status in ('success', 'skipped'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot skip completed runs. Current status: {current_status}"
            )
        
        # Update to skipped
        cursor.execute("""
            UPDATE preflight_participant_runs
            SET status = 'skipped', skip_reason = %s, completed_at = NOW()
            WHERE participant_run_id = %s
        """, (request.reason, participant_run_id))
        conn.commit()
        
        return PreflightActionResponse(
            participant_run_id=participant_run_id,
            participant_id=request.participant_id,
            status='skipped',
            message=f'Skipped: {request.reason}'
        )
    
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to skip: {str(e)}"
        )
    finally:
        cursor.close()
        conn.close()
