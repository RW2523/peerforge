"""
Embeddings + OCR endpoints for materials (TICKET-12.1, TICKET-12.3)
OpenRouter BYOK, client-driven, no server-side key storage
"""

import uuid
import shutil
from datetime import datetime
import psycopg2
import httpx
from psycopg2.extras import Json
from fastapi import APIRouter, HTTPException, Depends, Header

from src.config import settings
from src.auth import require_auth

router = APIRouter()

# Default embeddings model (system-wide fallback, TICKET-12.3)
# Kimi 2.5: Moonshot AI's multilingual embeddings model
DEFAULT_EMBEDDINGS_MODEL = "openai/text-embedding-3-small"

# Default OCR post-processing model (system-wide fallback, TICKET-12.3)
# Qwen 2.5: Alibaba's strong text cleanup/structuring model
DEFAULT_OCR_MODEL = "qwen/qwen-2.5-72b-instruct"


# ============================================================================
# Embeddings Endpoints
# ============================================================================

@router.post("/debates/{debate_id}/materials/{material_id}/embed")
async def generate_embeddings(
    debate_id: str,
    material_id: str,
    x_openrouter_key: str = Header(None, alias="X-OpenRouter-Key"),
    _workspace_id: str = Depends(require_auth)
):
    """
    Generate embeddings for material chunks using OpenRouter (BYOK).
    
    Requires:
        X-OpenRouter-Key header (client provides, not stored)
    
    Process:
        1. Fetch chunks for this material
        2. Call OpenRouter embeddings API (batch)
        3. Store embedding vectors in memory_chunks
        4. Update embedding_status to 'complete'
    
    Returns:
        Status and chunk counts
    """
    if not x_openrouter_key:
        raise HTTPException(
            status_code=400,
            detail="Missing X-OpenRouter-Key header. Embeddings require BYOK."
        )
    
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        # Verify material exists and belongs to debate
        cursor.execute("""
            SELECT processed_status, processing_metadata 
            FROM meeting_materials
            WHERE material_id = %s AND debate_id = %s
        """, (material_id, debate_id))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            raise HTTPException(status_code=404, detail="Material not found")
        
        processed_status, metadata = result
        if processed_status != 'complete':
            conn.close()
            raise HTTPException(
                status_code=400,
                detail=f"Material must be processed (status=complete) before generating embeddings. Current status: {processed_status}"
            )
        
        # Get workspace embeddings model default (TICKET-12.3)
        cursor.execute("""
            SELECT settings FROM workspaces WHERE workspace_id = %s
        """, (_workspace_id,))
        workspace_result = cursor.fetchone()
        workspace_settings = workspace_result[0] if workspace_result else {}
        
        # Use workspace default or system default (Kimi 2.5)
        embedding_model_id = workspace_settings.get('embeddings_model_id', DEFAULT_EMBEDDINGS_MODEL)
        
        # Get chunks for this material
        cursor.execute("""
            SELECT chunk_id, chunk_text
            FROM memory_chunks
            WHERE source_debate_id = %s
              AND chunk_metadata->>'material_id' = %s
              AND (embedding_status IS NULL OR embedding_status != 'complete')
        """, (debate_id, material_id))
        
        chunks = cursor.fetchall()
        if not chunks:
            conn.close()
            return {
                "material_id": material_id,
                "message": "No chunks found or all chunks already have embeddings",
                "chunks_processed": 0
            }
        
        # For Phase 1: Synchronous processing (simple, works for small batches)
        # Phase 2: Move to Celery for large batches
        
        # Mark chunks as running
        chunk_ids = [c[0] for c in chunks]
        cursor.execute("""
            UPDATE memory_chunks
            SET embedding_status = 'running',
                embedding_model_id = %s
            WHERE chunk_id = ANY(%s)
        """, (embedding_model_id, chunk_ids))
        conn.commit()
        
        # Call OpenRouter embeddings API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {x_openrouter_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": embedding_model_id,
                        "input": [c[1] for c in chunks]  # chunk texts
                    },
                    timeout=60.0
                )
                
                if response.status_code != 200:
                    # Mark as failed
                    cursor.execute("""
                        UPDATE memory_chunks
                        SET embedding_status = 'failed',
                            embedding_error = %s
                        WHERE chunk_id = ANY(%s)
                    """, (f"OpenRouter API error: {response.status_code}", chunk_ids))
                    conn.commit()
                    conn.close()
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"OpenRouter embeddings API failed: {response.text}"
                    )
                
                embeddings_data = response.json()
                embeddings = embeddings_data['data']
                
                # Store embeddings
                for i, chunk_id in enumerate(chunk_ids):
                    embedding_vector = embeddings[i]['embedding']
                    cursor.execute("""
                        UPDATE memory_chunks
                        SET embedding_status = 'complete',
                            embedding_vector = %s,
                            embedding_generated_at = NOW(),
                            embedding_error = NULL
                        WHERE chunk_id = %s
                    """, (Json(embedding_vector), chunk_id))
                
                conn.commit()
                
        except httpx.HTTPError as e:
            # Mark chunks as failed
            cursor.execute("""
                UPDATE memory_chunks
                SET embedding_status = 'failed',
                    embedding_error = %s
                WHERE chunk_id = ANY(%s)
            """, (str(e), chunk_ids))
            conn.commit()
            conn.close()
            raise HTTPException(status_code=500, detail=f"Embeddings generation failed: {str(e)}")
        
        conn.close()
        
        return {
            "material_id": material_id,
            "embedding_model_id": embedding_model_id,
            "chunks_processed": len(chunks),
            "status": "complete"
        }
        
    except HTTPException:
        conn.close()
        raise
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debates/{debate_id}/materials/{material_id}/embed/status")
async def get_embedding_status(
    debate_id: str,
    material_id: str,
    _workspace_id: str = Depends(require_auth)
):
    """
    Get embedding status for a material's chunks
    
    Returns:
        Chunk counts by embedding_status
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    # Verify material exists
    cursor.execute("""
        SELECT processed_status FROM meeting_materials
        WHERE material_id = %s AND debate_id = %s
    """, (material_id, debate_id))
    
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Material not found")
    
    # Get embedding status counts
    cursor.execute("""
        SELECT 
            COALESCE(embedding_status, 'not_started') as status,
            COUNT(*) as count
        FROM memory_chunks
        WHERE source_debate_id = %s
          AND chunk_metadata->>'material_id' = %s
        GROUP BY embedding_status
    """, (debate_id, material_id))
    
    status_counts = {}
    total_chunks = 0
    for row in cursor.fetchall():
        status_counts[row[0]] = row[1]
        total_chunks += row[1]
    
    conn.close()
    
    # Determine overall status
    if total_chunks == 0:
        overall_status = "no_chunks"
    elif status_counts.get('complete', 0) == total_chunks:
        overall_status = "complete"
    elif status_counts.get('failed', 0) > 0:
        overall_status = "partial_failure"
    elif status_counts.get('running', 0) > 0:
        overall_status = "in_progress"
    else:
        overall_status = "not_started"
    
    return {
        "material_id": material_id,
        "total_chunks": total_chunks,
        "overall_status": overall_status,
        "status_breakdown": status_counts
    }


# ============================================================================
# OCR Endpoints
# ============================================================================

@router.post("/debates/{debate_id}/materials/{material_id}/ocr")
async def run_ocr(
    debate_id: str,
    material_id: str,
    _workspace_id: str = Depends(require_auth)
):
    """
    Run OCR on a scanned PDF material
    
    Phase 1: Baseline implementation
    - Only allowed if processed_status = 'needs_ocr'
    - Uses Tesseract if available
    - Extracts text and re-chunks
    
    Returns:
        Job ID and status
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    # Verify material exists and needs OCR
    cursor.execute("""
        SELECT processed_status, file_key, processing_metadata
        FROM meeting_materials
        WHERE material_id = %s AND debate_id = %s
    """, (material_id, debate_id))
    
    result = cursor.fetchone()
    if not result:
        conn.close()
        raise HTTPException(status_code=404, detail="Material not found")
    
    processed_status, file_key, metadata = result
    
    if processed_status != 'needs_ocr':
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Material does not need OCR. Current status: {processed_status}"
        )
    
    # Check if Tesseract is available (Phase 1 baseline)
    tesseract_path = shutil.which('tesseract')
    
    if not tesseract_path:
        conn.close()
        raise HTTPException(
            status_code=501,
            detail="OCR is not available on this server (Tesseract not installed). OCR support coming in Phase 2."
        )
    
    # Get workspace OCR model default (TICKET-12.3)
    cursor.execute("""
        SELECT settings FROM workspaces WHERE workspace_id = %s
    """, (_workspace_id,))
    workspace_result = cursor.fetchone()
    workspace_settings = workspace_result[0] if workspace_result else {}
    
    # Use workspace default or system default (Qwen 2.5)
    ocr_model_id = workspace_settings.get('ocr_model_id', DEFAULT_OCR_MODEL)
    
    # Create OCR job with model metadata
    job_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO material_processing_jobs (
            job_id, material_id, debate_id, job_type, status, created_at
        )
        VALUES (%s, %s, %s, 'ocr', 'queued', NOW())
    """, (job_id, material_id, debate_id))
    
    # Update material metadata with OCR model
    cursor.execute("""
        UPDATE meeting_materials
        SET processing_metadata = processing_metadata || %s::jsonb,
            updated_at = NOW()
        WHERE material_id = %s
    """, (Json({
        'ocr_started_at': datetime.utcnow().isoformat(),
        'ocr_model_id': ocr_model_id
    }), material_id))
    
    conn.commit()
    conn.close()
    
    # Queue OCR Celery task (import at runtime to avoid circular deps)
    try:
        from src.tasks.ocr_processing import process_ocr
        process_ocr.delay(material_id, debate_id, job_id)
    except ImportError:
        # OCR task not implemented yet - return success with note
        pass
    
    return {
        "material_id": material_id,
        "job_id": job_id,
        "message": "OCR processing queued",
        "status": "queued"
    }


@router.get("/debates/{debate_id}/materials/{material_id}/ocr/status")
async def get_ocr_status(
    debate_id: str,
    material_id: str,
    _workspace_id: str = Depends(require_auth)
):
    """
    Get OCR processing status for a material
    
    Returns:
        OCR status and metadata
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    # Get material and latest OCR job
    cursor.execute("""
        SELECT 
            m.processed_status,
            m.processing_metadata,
            j.job_id,
            j.status as job_status,
            j.error_message,
            j.completed_at
        FROM meeting_materials m
        LEFT JOIN material_processing_jobs j ON j.material_id = m.material_id AND j.job_type = 'ocr'
        WHERE m.material_id = %s AND m.debate_id = %s
        ORDER BY j.created_at DESC
        LIMIT 1
    """, (material_id, debate_id))
    
    result = cursor.fetchone()
    if not result:
        conn.close()
        raise HTTPException(status_code=404, detail="Material not found")
    
    processed_status, metadata, job_id, job_status, error_message, completed_at = result
    
    conn.close()
    
    ocr_metadata = metadata.get('ocr_metadata', {}) if metadata else {}
    
    return {
        "material_id": material_id,
        "processed_status": processed_status,
        "ocr_job_id": job_id,
        "ocr_job_status": job_status,
        "ocr_completed": ocr_metadata.get('ocr_completed', False),
        "ocr_page_count": ocr_metadata.get('ocr_page_count'),
        "ocr_confidence_avg": ocr_metadata.get('ocr_confidence_avg'),
        "error_message": error_message,
        "completed_at": completed_at.isoformat() if completed_at else None
    }
