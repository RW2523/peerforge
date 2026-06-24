"""
Materials upload and status endpoints
"""

import io
import uuid
from datetime import datetime
from typing import List, Optional
import psycopg2
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Header
from pydantic import BaseModel
from psycopg2.extras import Json

from src.config import settings
from src.schemas.materials import (
    MaterialUploadResponse,
    MaterialsStatusResponse,
    MaterialStatus,
    MaterialRetryRequest,
    MaterialRetryResponse
)
from src.utils.storage import get_storage_client
from src.utils.text_extraction import TextExtractor
from src.tasks.material_processing import process_material
from src.auth import require_auth
from src.tasks.material_processing import generate_debate_embeddings, chunk_inline_material
from src.database import get_db_connection, get_cursor

router = APIRouter()


def _delete_material_record(cur, debate_id: str, material_id: str) -> Optional[str]:
    """Delete one material row and its chunks. Returns file_key when present."""
    cur.execute(
        "SELECT file_key FROM meeting_materials WHERE material_id = %s AND debate_id = %s",
        (material_id, debate_id),
    )
    row = cur.fetchone()
    if not row:
        return None
    file_key = row["file_key"] if isinstance(row, dict) else row[0]

    cur.execute(
        """
        DELETE FROM memory_chunks
        WHERE source_debate_id = %s AND chunk_metadata->>'material_id' = %s
        """,
        (debate_id, material_id),
    )
    cur.execute(
        "DELETE FROM meeting_materials WHERE material_id = %s AND debate_id = %s",
        (material_id, debate_id),
    )
    return file_key


def _delete_existing_main_research_files(cur, debate_id: str) -> List[str]:
    """Remove all main research files for a debate. Returns storage keys to purge."""
    cur.execute(
        """
        SELECT material_id FROM meeting_materials
        WHERE debate_id = %s AND (is_primary = true OR material_category = 'main_research')
        """,
        (debate_id,),
    )
    rows = cur.fetchall()
    file_keys: List[str] = []
    for row in rows:
        material_id = row["material_id"] if isinstance(row, dict) else row[0]
        file_key = _delete_material_record(cur, debate_id, str(material_id))
        if file_key:
            file_keys.append(file_key)
    return file_keys


def _purge_storage_keys(file_keys: List[str]) -> None:
    if not file_keys:
        return
    storage_client = get_storage_client()
    for file_key in file_keys:
        try:
            storage_client.delete_file(file_key)
        except Exception as exc:
            print(f"Storage delete failed (non-fatal) for {file_key}: {exc}")


class InlineMaterial(BaseModel):
    kind: str  # 'text' | 'link'
    title: Optional[str] = None
    body_text: Optional[str] = None
    url: Optional[str] = None


class AddInlineMaterialsRequest(BaseModel):
    materials: List[InlineMaterial]


@router.post("/debates/{debate_id}/materials")
async def add_inline_materials(
    debate_id: str,
    request: AddInlineMaterialsRequest,
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
    _workspace_id: str = Depends(require_auth),
):
    """
    Add (replace) inline TEXT/LINK materials for an existing debate and chunk
    them so they are retrievable by prep + live turns.

    The setup wizard creates the debate early (before materials are entered),
    so inline text/link cards are persisted here. Idempotent: replaces all
    existing inline (kind in text/link) materials for the debate.
    """
    resolved_key = x_openrouter_key or settings.openrouter_api_key

    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("SELECT debate_id FROM debates WHERE debate_id = %s", (debate_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Debate not found")

        # Remove prior inline materials + their chunks (idempotent re-submit).
        cur.execute(
            "SELECT material_id FROM meeting_materials WHERE debate_id = %s AND kind IN ('text','link')",
            (debate_id,),
        )
        old_ids = [str(r["material_id"]) for r in cur.fetchall()]
        for old_id in old_ids:
            cur.execute(
                "DELETE FROM memory_chunks WHERE source_debate_id = %s AND chunk_metadata->>'material_id' = %s",
                (debate_id, old_id),
            )
        cur.execute(
            "DELETE FROM meeting_materials WHERE debate_id = %s AND kind IN ('text','link')",
            (debate_id,),
        )
        conn.commit()

        created = []
        for m in request.materials:
            kind = m.kind
            body = (m.body_text or "").strip()
            url = (m.url or "").strip()
            if kind == "text" and not body:
                continue
            if kind == "link" and not url:
                continue
            material_id = str(uuid.uuid4())
            now = datetime.utcnow()
            cur.execute(
                """
                INSERT INTO meeting_materials (material_id, debate_id, kind, title, body_text, url, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (material_id, debate_id, kind, m.title, m.body_text, m.url, now, now),
            )
            conn.commit()
            created.append((material_id, kind, body, url, m.title))

    total_chunks = 0
    for material_id, kind, body, url, title in created:
        try:
            if kind == "text":
                total_chunks += chunk_inline_material(debate_id, material_id, body, "supplementary", resolved_key)
            elif kind == "link":
                descriptor = f"Reference link: {title or ''}\n{url}".strip()
                total_chunks += chunk_inline_material(debate_id, material_id, descriptor, "supplementary", resolved_key)
        except Exception as exc:
            print(f"Inline material chunking failed (non-fatal) for {material_id}: {exc}")

    return {
        "debate_id": debate_id,
        "materials_added": len(created),
        "chunks_created": total_chunks,
    }

# Valid knowledge-base categories for uploaded materials
VALID_CATEGORIES = {'main_research', 'research', 'transcript', 'supplementary'}


@router.post("/debates/{debate_id}/materials/upload", response_model=MaterialUploadResponse)
async def upload_materials(
    debate_id: str,
    files: List[UploadFile] = File(...),
    category: str = Form('supplementary'),
    is_primary: bool = Form(False),
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
    _workspace_id: str = Depends(require_auth)
):
    """
    Upload multiple files for a debate

    Steps:
    1. Validate file types and sizes (audio allowed only for transcripts)
    2. Upload to MinIO
    3. Create meeting_materials rows (tagged with knowledge-base category)
    4. Queue Celery processing tasks

    Args:
        category: Knowledge-base role — main_research | research | transcript | supplementary
        is_primary: Pin this file as the single main research file (always in KB)

    Returns:
        MaterialUploadResponse with material IDs and job IDs
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 files per upload")

    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category '{category}'")

    # Primary always implies the main research role
    if is_primary:
        category = 'main_research'

    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()

    # Verify debate exists and user has access
    cursor.execute("""
        SELECT workspace_id FROM debates WHERE debate_id = %s
    """, (debate_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        raise HTTPException(status_code=404, detail="Debate not found")

    db_workspace_id = result[0]
    if str(db_workspace_id) != _workspace_id:
        conn.close()
        raise HTTPException(status_code=403, detail="Access denied to this debate")

    material_ids = []
    job_ids = []
    stale_storage_keys: List[str] = []

    try:
        # A new primary file fully replaces any existing main research file(s).
        if is_primary:
            stale_storage_keys = _delete_existing_main_research_files(cursor, debate_id)

        for upload_file in files:
            # Read file contents
            file_contents = await upload_file.read()
            file_size = len(file_contents)

            # Validate file — audio is permitted only for transcripts
            is_valid, mime_type, error_msg = TextExtractor.validate_file(
                file_contents, upload_file.filename, allow_audio=(category == 'transcript')
            )

            if not is_valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"File '{upload_file.filename}' validation failed: {error_msg}"
                )

            # Audio files become 'audio' materials (transcribed before chunking)
            is_audio = mime_type in TextExtractor.AUDIO_TYPES
            material_kind = 'audio' if is_audio else 'file'

            # Generate file key for MinIO
            material_id = str(uuid.uuid4())
            file_extension = upload_file.filename.split('.')[-1] if '.' in upload_file.filename else 'bin'
            file_key = f"debates/{debate_id}/materials/{material_id}.{file_extension}"

            # Upload to MinIO
            try:
                storage_client = get_storage_client()
                storage_client.upload_file(
                    file_key=file_key,
                    file_data=io.BytesIO(file_contents),
                    file_size=file_size,
                    content_type=mime_type
                )
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to upload file '{upload_file.filename}': {str(e)}"
                )

            # Create meeting_materials row
            cursor.execute("""
                INSERT INTO meeting_materials (
                    material_id, debate_id, kind, material_category, is_primary, title,
                    file_key, file_size_bytes, file_mime_type,
                    processed_status, processing_metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)
                RETURNING material_id
            """, (
                material_id,
                debate_id,
                material_kind,
                category,
                is_primary,
                upload_file.filename,
                file_key,
                file_size,
                mime_type,
                Json({'uploaded_at': datetime.utcnow().isoformat()})
            ))

            created_material_id = cursor.fetchone()[0]
            material_ids.append(str(created_material_id))

            # Queue Celery task — pass BYOK key so worker can generate embeddings.
            # category is stored on chunk_metadata for provenance/labelling.
            task = process_material.delay(
                str(created_material_id), debate_id, x_openrouter_key, category
            )
            job_ids.append(task.id)

        conn.commit()
        _purge_storage_keys(stale_storage_keys)
        
        return MaterialUploadResponse(
            material_ids=material_ids,
            job_ids=job_ids,
            total_files=len(files)
        )
    
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        conn.close()


@router.get("/debates/{debate_id}/materials/status", response_model=MaterialsStatusResponse)
async def get_materials_status(
    debate_id: str,
    _workspace_id: str = Depends(require_auth)
):
    """
    Get processing status of all materials in a debate
    
    Returns:
        MaterialsStatusResponse with status for each material
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    # Verify debate exists and user has access
    cursor.execute("""
        SELECT workspace_id FROM debates WHERE debate_id = %s
    """, (debate_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        raise HTTPException(status_code=404, detail="Debate not found")
    
    db_workspace_id = result[0]
    if str(db_workspace_id) != _workspace_id:
        conn.close()
        raise HTTPException(status_code=403, detail="Access denied to this debate")
    
    # Fetch all materials for this debate
    cursor.execute("""
        SELECT
            material_id, title, kind, file_size_bytes, file_mime_type,
            processed_status, processing_metadata, created_at,
            processing_started_at, processing_completed_at,
            material_category, is_primary
        FROM meeting_materials
        WHERE debate_id = %s
        ORDER BY created_at DESC
    """, (debate_id,))

    rows = cursor.fetchall()
    conn.close()

    materials = []
    status_summary = {}

    for row in rows:
        material = MaterialStatus(
            material_id=str(row[0]),
            title=row[1],
            kind=row[2],
            file_size_bytes=row[3],
            file_mime_type=row[4],
            processed_status=row[5],
            processing_metadata=row[6] or {},
            created_at=row[7],
            processing_started_at=row[8],
            processing_completed_at=row[9],
            material_category=row[10] or 'supplementary',
            is_primary=bool(row[11]),
        )
        materials.append(material)
        
        # Update summary
        status = material.processed_status
        status_summary[status] = status_summary.get(status, 0) + 1
    
    return MaterialsStatusResponse(
        debate_id=debate_id,
        total_materials=len(materials),
        status_summary=status_summary,
        materials=materials
    )


@router.delete("/debates/{debate_id}/materials/{material_id}")
async def delete_material(
    debate_id: str,
    material_id: str,
    _workspace_id: str = Depends(require_auth),
):
    """Remove a material from the debate session (DB row, chunks, and stored file)."""
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            """
            SELECT mm.material_id, d.workspace_id
            FROM meeting_materials mm
            JOIN debates d ON d.debate_id = mm.debate_id
            WHERE mm.material_id = %s AND mm.debate_id = %s
            """,
            (material_id, debate_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Material not found")
        if str(row["workspace_id"]) != _workspace_id:
            raise HTTPException(status_code=403, detail="Access denied to this debate")

        file_key = _delete_material_record(cur, debate_id, material_id)

    _purge_storage_keys([file_key] if file_key else [])

    return {"material_id": material_id, "deleted": True}


@router.post("/debates/{debate_id}/materials/retry", response_model=MaterialRetryResponse)
async def retry_material_processing(
    debate_id: str,
    request: MaterialRetryRequest,
    _workspace_id: str = Depends(require_auth)
):
    """
    Retry processing a failed material
    
    Args:
        debate_id: Debate UUID
        request: Material ID to retry
    
    Returns:
        MaterialRetryResponse with new job ID
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    # Verify material exists and belongs to debate
    cursor.execute("""
        SELECT processed_status, material_category FROM meeting_materials
        WHERE material_id = %s AND debate_id = %s
    """, (request.material_id, debate_id))

    result = cursor.fetchone()
    if not result:
        conn.close()
        raise HTTPException(status_code=404, detail="Material not found")

    current_status = result[0]
    material_category = result[1] or 'supplementary'
    if current_status not in ['failed', 'needs_ocr']:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry material with status '{current_status}'"
        )
    
    # Reset status to pending
    cursor.execute("""
        UPDATE meeting_materials
        SET processed_status = 'pending',
            processing_metadata = processing_metadata || %s::jsonb,
            updated_at = NOW()
        WHERE material_id = %s
    """, (
        Json({'retry_at': datetime.utcnow().isoformat()}),
        request.material_id
    ))
    conn.commit()
    conn.close()
    
    # Queue new Celery task (preserve original category)
    task = process_material.delay(request.material_id, debate_id, None, material_category)

    return MaterialRetryResponse(
        material_id=request.material_id,
        job_id=task.id,
        message="Processing retry queued"
    )


@router.post("/debates/{debate_id}/materials/embed")
async def trigger_embedding_generation(
    debate_id: str,
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
    _workspace_id: str = Depends(require_auth),
):
    """
    Trigger (or re-trigger) embedding generation for all unembedded chunks in a debate.

    Useful after:
    - Initial upload when no server-side OPENROUTER_API_KEY was configured
    - Any embedding failures that need to be retried

    Requires X-OpenRouter-Key header (BYOK).
    """
    resolved_key = x_openrouter_key or settings.openrouter_api_key
    if not resolved_key:
        raise HTTPException(
            status_code=400,
            detail="No OpenRouter API key available. Pass X-OpenRouter-Key header or set OPENROUTER_API_KEY in .env",
        )

    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT debate_id FROM debates WHERE debate_id = %s", (debate_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Debate not found")

        cursor.execute(
            "SELECT COUNT(*) FROM memory_chunks WHERE source_debate_id = %s AND agent_id IS NULL AND (embedding_status IN ('not_started','failed') OR embedding_status IS NULL)",
            (debate_id,),
        )
        pending_count = cursor.fetchone()[0]
    finally:
        conn.close()

    if pending_count == 0:
        return {"debate_id": debate_id, "job_id": None, "message": "All chunks already have embeddings"}

    task = generate_debate_embeddings.delay(debate_id, resolved_key)
    return {
        "debate_id": debate_id,
        "job_id": task.id,
        "message": f"Embedding generation queued for {pending_count} chunks",
    }
