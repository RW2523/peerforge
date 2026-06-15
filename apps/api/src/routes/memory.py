"""
Memory Import API endpoints
Allows users to import context from prior debates with granular scoping
"""

import psycopg2
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, Depends, Query
from psycopg2.extras import Json

from src.config import settings
from src.auth import require_auth
from src.schemas.memory import (
    ImportableSourcesResponse,
    ImportableDebate,
    MemoryPreviewResponse,
    MemoryPreviewChunk,
    MemoryImportRequest,
    MemoryImportResponse,
    MemoryGrantsResponse,
    MemoryGrant
)

router = APIRouter()


@router.get("/workspaces/{workspace_id}/memory/importable", response_model=ImportableSourcesResponse)
def list_importable_sources(
    workspace_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    workspace_id_auth: str = Depends(require_auth)
):
    """
    List recent debates in workspace that can be imported as memory sources
    
    Returns debates that:
    - Have ended (state='ended')
    - Have materials or generated artifacts
    - Are in the same workspace
    
    Auth: Requires workspace access
    """
    if workspace_id != workspace_id_auth:
        raise HTTPException(status_code=403, detail="Access denied to workspace")
    
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        # Get debates with chunk/material/artifact counts
        cursor.execute("""
            SELECT
                d.debate_id,
                d.title,
                d.state,
                d.created_at,
                d.ended_at,
                COUNT(DISTINCT mc.chunk_id) AS chunk_count,
                COUNT(DISTINCT mm.material_id) AS material_count,
                0 AS artifact_count,  -- TODO: join artifacts table when implemented
                COUNT(DISTINCT p.participant_id) AS participant_count
            FROM debates d
            LEFT JOIN memory_chunks mc ON d.debate_id = mc.source_debate_id
            LEFT JOIN meeting_materials mm ON d.debate_id = mm.debate_id
            LEFT JOIN participants p ON d.debate_id = p.debate_id
            WHERE d.workspace_id = %s
              AND d.state = 'ended'
            GROUP BY d.debate_id, d.title, d.state, d.created_at, d.ended_at
            ORDER BY d.ended_at DESC NULLS LAST, d.created_at DESC
            LIMIT %s
        """, (workspace_id, limit))
        
        rows = cursor.fetchall()
        
        debates = []
        for row in rows:
            debate_id, title, state, created_at, ended_at, chunk_count, material_count, artifact_count, participant_count = row
            
            debates.append(ImportableDebate(
                debate_id=debate_id,
                title=title,
                state=state,
                created_at=created_at,
                ended_at=ended_at,
                chunk_count=chunk_count,
                material_count=material_count,
                artifact_count=artifact_count,
                participant_count=participant_count
            ))
        
        return ImportableSourcesResponse(
            workspace_id=workspace_id,
            debates=debates,
            total_count=len(debates)
        )
    
    finally:
        cursor.close()
        conn.close()


@router.get("/debates/{debate_id}/memory/preview", response_model=MemoryPreviewResponse)
def preview_memory_import(
    debate_id: str,
    source_debate_id: str = Query(..., description="Debate ID to preview"),
    workspace_id: str = Depends(require_auth)
):
    """
    Preview what would be imported from a source debate
    
    Shows:
    - Source debate title
    - Total chunks available
    - Breakdown by type (materials, agent knowledge, artifacts)
    - Date range
    
    Auth: Requires access to both debates' workspace
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        # Verify both debates exist and are in the same workspace
        cursor.execute("""
            SELECT d1.workspace_id, d2.workspace_id, d2.title, d2.created_at, d2.ended_at
            FROM debates d1, debates d2
            WHERE d1.debate_id = %s AND d2.debate_id = %s
        """, (debate_id, source_debate_id))
        
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Debate not found")
        
        ws1, ws2, source_title, created_at, ended_at = result
        
        if ws1 != workspace_id or ws2 != workspace_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get chunk breakdown by type
        cursor.execute("""
            SELECT
                CASE
                    WHEN mc.agent_id IS NULL AND mc.chunk_metadata->>'material_id' IS NOT NULL THEN 'material'
                    WHEN mc.agent_id IS NOT NULL THEN 'agent_knowledge'
                    ELSE 'other'
                END AS source_type,
                COUNT(*) AS chunk_count,
                MAX(mc.created_at) AS last_updated
            FROM memory_chunks mc
            WHERE mc.source_debate_id = %s
            GROUP BY source_type
        """, (source_debate_id,))
        
        breakdown_rows = cursor.fetchall()
        
        # Get material titles for better preview
        cursor.execute("""
            SELECT DISTINCT
                mm.title,
                COUNT(mc.chunk_id) AS chunk_count,
                MAX(mc.created_at) AS last_updated
            FROM meeting_materials mm
            JOIN memory_chunks mc ON mc.chunk_metadata->>'material_id' = mm.material_id::text
            WHERE mm.debate_id = %s AND mc.source_debate_id = %s
            GROUP BY mm.title
        """, (source_debate_id, source_debate_id))
        
        material_rows = cursor.fetchall()
        
        breakdown = []
        total_chunks = 0
        
        # Add material-specific entries
        for title, chunk_count, last_updated in material_rows:
            breakdown.append(MemoryPreviewChunk(
                source_type='material',
                title=title or 'Untitled Material',
                chunk_count=chunk_count,
                last_updated=last_updated
            ))
            total_chunks += chunk_count
        
        # Add aggregate entries for agent knowledge
        for source_type, chunk_count, last_updated in breakdown_rows:
            if source_type == 'agent_knowledge':
                breakdown.append(MemoryPreviewChunk(
                    source_type=source_type,
                    title='Agent Knowledge',
                    chunk_count=chunk_count,
                    last_updated=last_updated
                ))
                total_chunks += chunk_count
        
        return MemoryPreviewResponse(
            source_debate_id=source_debate_id,
            source_title=source_title,
            total_chunks=total_chunks,
            breakdown=breakdown,
            date_range={
                'start': created_at.isoformat() if created_at else None,
                'end': ended_at.isoformat() if ended_at else None
            }
        )
    
    finally:
        cursor.close()
        conn.close()


@router.post("/debates/{debate_id}/memory/import", response_model=MemoryImportResponse)
def import_memory(
    debate_id: str,
    request: MemoryImportRequest,
    workspace_id: str = Depends(require_auth)
):
    """
    Create memory grants to import context from prior debates
    
    Creates grants that allow participants to retrieve chunks from specified source debates.
    
    Rules:
    - Debate must be in pending state (cannot import after started)
    - scope='all_agents': any participant can access
    - scope='specific_agents': only specified participant_ids can access
    
    Auth: Requires workspace access
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        # Verify debate exists, is in workspace, and is pending
        cursor.execute("""
            SELECT workspace_id, state
            FROM debates
            WHERE debate_id = %s
        """, (debate_id,))
        
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Debate not found")
        
        db_workspace_id, state = result
        
        if db_workspace_id != workspace_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if state != 'pending':
            raise HTTPException(status_code=400, detail="Cannot import memory after debate has started")
        
        # Validate scope + participant_ids consistency
        if request.scope == 'specific_agents' and not request.participant_ids:
            raise HTTPException(status_code=400, detail="participant_ids required for specific_agents scope")
        
        if request.scope == 'all_agents' and request.participant_ids:
            raise HTTPException(status_code=400, detail="participant_ids must be null for all_agents scope")
        
        # Verify source debates exist and are in same workspace
        cursor.execute("""
            SELECT debate_id
            FROM debates
            WHERE debate_id = ANY(%s::uuid[]) AND workspace_id = %s
        """, (request.source_debate_ids, workspace_id))
        
        valid_sources = [row[0] for row in cursor.fetchall()]
        
        if len(valid_sources) != len(request.source_debate_ids):
            raise HTTPException(status_code=400, detail="One or more source debates not found or not in workspace")
        
        # Create grants (one per source debate)
        grant_ids = []
        
        for source_debate_id in request.source_debate_ids:
            cursor.execute("""
                INSERT INTO debate_memory_grants (
                    grant_id,
                    debate_id,
                    source_debate_id,
                    source_type,
                    scope,
                    allowed_participant_ids,
                    granted_by,
                    metadata
                ) VALUES (
                    gen_random_uuid(),
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                ON CONFLICT (debate_id, source_debate_id, source_artifact_id, scope)
                DO UPDATE SET
                    allowed_participant_ids = EXCLUDED.allowed_participant_ids,
                    metadata = EXCLUDED.metadata
                RETURNING grant_id
            """, (
                debate_id,
                source_debate_id,
                request.source_type,
                request.scope,
                request.participant_ids,
                workspace_id,  # Use workspace_id as granted_by for now
                Json(request.metadata or {})
            ))
            
            grant_id = cursor.fetchone()[0]
            grant_ids.append(grant_id)
        
        conn.commit()
        
        return MemoryImportResponse(
            debate_id=debate_id,
            grants_created=len(grant_ids),
            grant_ids=grant_ids
        )
    
    finally:
        cursor.close()
        conn.close()


@router.get("/debates/{debate_id}/memory/grants", response_model=MemoryGrantsResponse)
def list_memory_grants(
    debate_id: str,
    workspace_id: str = Depends(require_auth)
):
    """
    List all memory grants for a debate
    
    Shows which source debates/artifacts participants can access
    
    Auth: Requires workspace access
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        # Verify debate access
        cursor.execute("""
            SELECT workspace_id FROM debates WHERE debate_id = %s
        """, (debate_id,))
        
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Debate not found")
        
        if result[0] != workspace_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get grants with source debate titles
        cursor.execute("""
            SELECT
                g.grant_id,
                g.source_debate_id,
                d.title AS source_debate_title,
                g.source_artifact_id,
                NULL AS source_artifact_title,  -- TODO: join artifacts when implemented
                g.source_type,
                g.scope,
                g.allowed_participant_ids,
                g.granted_by,
                g.granted_at,
                g.expires_at,
                g.metadata
            FROM debate_memory_grants g
            LEFT JOIN debates d ON g.source_debate_id = d.debate_id
            WHERE g.debate_id = %s
            ORDER BY g.granted_at DESC
        """, (debate_id,))
        
        rows = cursor.fetchall()
        
        grants = []
        for row in rows:
            grant_id, source_debate_id, source_debate_title, source_artifact_id, source_artifact_title, \
            source_type, scope, allowed_participant_ids, granted_by, granted_at, expires_at, metadata = row
            
            grants.append(MemoryGrant(
                grant_id=grant_id,
                source_debate_id=source_debate_id,
                source_debate_title=source_debate_title,
                source_artifact_id=source_artifact_id,
                source_artifact_title=source_artifact_title,
                source_type=source_type,
                scope=scope,
                allowed_participant_ids=allowed_participant_ids,
                granted_by=granted_by,
                granted_at=granted_at,
                expires_at=expires_at,
                metadata=metadata or {}
            ))
        
        return MemoryGrantsResponse(
            debate_id=debate_id,
            grants=grants,
            total_count=len(grants)
        )
    
    finally:
        cursor.close()
        conn.close()


@router.delete("/debates/{debate_id}/memory/grants/{grant_id}")
def revoke_memory_grant(
    debate_id: str,
    grant_id: str,
    workspace_id: str = Depends(require_auth)
):
    """
    Revoke a memory grant
    
    Rules:
    - Can only revoke if debate is in pending state
    - Grants are immutable once debate starts (for audit integrity)
    
    Auth: Requires workspace access
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        # Verify debate state
        cursor.execute("""
            SELECT workspace_id, state FROM debates WHERE debate_id = %s
        """, (debate_id,))
        
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Debate not found")
        
        db_workspace_id, state = result
        
        if db_workspace_id != workspace_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if state != 'pending':
            raise HTTPException(
                status_code=400,
                detail="Cannot revoke grants after debate has started (immutable for audit integrity)"
            )
        
        # Delete grant
        cursor.execute("""
            DELETE FROM debate_memory_grants
            WHERE grant_id = %s AND debate_id = %s
            RETURNING grant_id
        """, (grant_id, debate_id))
        
        deleted = cursor.fetchone()
        if not deleted:
            raise HTTPException(status_code=404, detail="Grant not found")
        
        conn.commit()
        
        return {"status": "revoked", "grant_id": grant_id}
    
    finally:
        cursor.close()
        conn.close()
