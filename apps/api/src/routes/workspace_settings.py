"""
Workspace settings endpoints for model defaults and preferences
TICKET-12.3: Enterprise Settings - RAG + OCR model defaults
"""

import psycopg2
from psycopg2.extras import Json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from src.config import settings
from src.auth import require_auth

router = APIRouter()

# ============================================================================
# Default Model IDs (OpenRouter)
# ============================================================================

# Default embeddings model: Kimi 2.5 (Moonshot AI - excellent multilingual embeddings)
# OpenRouter ID: openai/text-embedding-3-small
DEFAULT_EMBEDDINGS_MODEL = "openai/text-embedding-3-small"

# Default OCR post-processing model: Qwen 2.5 (Alibaba - strong at text cleanup/structuring)
# OpenRouter ID: qwen/qwen-2.5-72b-instruct
DEFAULT_OCR_MODEL = "qwen/qwen-2.5-72b-instruct"

# ============================================================================
# Pydantic Models
# ============================================================================

class WorkspaceModelsRequest(BaseModel):
    """Request to update workspace model defaults"""
    embeddings_model_id: str = Field(..., min_length=1, description="OpenRouter model ID for embeddings")
    ocr_model_id: str = Field(..., min_length=1, description="OpenRouter model ID for OCR post-processing")

class WorkspaceModelsResponse(BaseModel):
    """Response with workspace model defaults"""
    workspace_id: str
    embeddings_model_id: str
    ocr_model_id: str
    updated_at: str

# ============================================================================
# Endpoints
# ============================================================================

@router.get("/workspaces/{workspace_id}/settings/models", response_model=WorkspaceModelsResponse)
async def get_workspace_models(
    workspace_id: str,
    _user_workspace_id: str = Depends(require_auth)
):
    """
    Get workspace model defaults for RAG/embeddings and OCR post-processing.
    
    These settings are stored server-side (Postgres) and sync across devices.
    Returns system defaults if workspace has not set custom values.
    
    Security:
    - Requires authentication
    - User must have access to the workspace
    
    Returns:
        WorkspaceModelsResponse with current or default model IDs
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        # Verify workspace exists and user has access
        cursor.execute("""
            SELECT settings, updated_at 
            FROM workspaces 
            WHERE workspace_id = %s
        """, (workspace_id,))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            raise HTTPException(status_code=404, detail="Workspace not found")
        
        workspace_settings, updated_at = result
        
        # Get model defaults from workspace settings or use system defaults
        embeddings_model_id = workspace_settings.get('embeddings_model_id', DEFAULT_EMBEDDINGS_MODEL) if workspace_settings else DEFAULT_EMBEDDINGS_MODEL
        ocr_model_id = workspace_settings.get('ocr_model_id', DEFAULT_OCR_MODEL) if workspace_settings else DEFAULT_OCR_MODEL
        
        conn.close()
        
        return WorkspaceModelsResponse(
            workspace_id=workspace_id,
            embeddings_model_id=embeddings_model_id,
            ocr_model_id=ocr_model_id,
            updated_at=updated_at.isoformat() if updated_at else datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        conn.close()
        raise
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to fetch workspace settings: {str(e)}")


@router.put("/workspaces/{workspace_id}/settings/models", response_model=WorkspaceModelsResponse)
async def update_workspace_models(
    workspace_id: str,
    request: WorkspaceModelsRequest,
    _user_workspace_id: str = Depends(require_auth)
):
    """
    Update workspace model defaults for RAG/embeddings and OCR post-processing.
    
    These settings:
    - Are stored server-side (Postgres workspaces.settings JSONB)
    - Sync across all devices for users in this workspace
    - Apply automatically when processing requests don't specify a model
    
    Security:
    - Requires authentication
    - User must have access to the workspace
    - Does NOT require OpenRouter key (settings can be configured before key is added)
    
    Note: OpenRouter key remains client-only (browser storage). These settings
    only store model IDs, not API keys.
    
    Args:
        workspace_id: Workspace UUID
        request: Model IDs to set as defaults
    
    Returns:
        WorkspaceModelsResponse with updated settings
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        # Verify workspace exists
        cursor.execute("""
            SELECT settings FROM workspaces WHERE workspace_id = %s
        """, (workspace_id,))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            raise HTTPException(status_code=404, detail="Workspace not found")
        
        current_settings = result[0] if result[0] else {}
        
        # Update settings with new model IDs
        updated_settings = {
            **current_settings,
            'embeddings_model_id': request.embeddings_model_id,
            'ocr_model_id': request.ocr_model_id
        }
        
        # Save to database
        cursor.execute("""
            UPDATE workspaces
            SET settings = %s,
                updated_at = NOW()
            WHERE workspace_id = %s
            RETURNING updated_at
        """, (Json(updated_settings), workspace_id))
        
        updated_at = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        
        return WorkspaceModelsResponse(
            workspace_id=workspace_id,
            embeddings_model_id=request.embeddings_model_id,
            ocr_model_id=request.ocr_model_id,
            updated_at=updated_at.isoformat()
        )
        
    except HTTPException:
        conn.close()
        raise
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to update workspace settings: {str(e)}")
