"""
Celery tasks for material processing
Handles file validation, text extraction, chunking, embedding generation, and storage
"""

import json
from datetime import datetime
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import Json

from src.celery_app import celery_app
from src.config import settings
from src.utils.storage import get_storage_client
from src.utils.text_extraction import TextExtractor
from src.utils.chunking import TextChunker
from src.database import get_db_connection
from src.services.memory_retrieval import get_query_embedding

# Embedding model used for document chunks
EMBEDDINGS_MODEL = "openai/text-embedding-3-small"
# Max chunks to embed in a single OpenRouter API call
EMBED_BATCH_SIZE = 20
# Multimodal model used to transcribe uploaded audio meeting recordings.
# Must accept `input_audio` content parts via OpenRouter chat-completions.
AUDIO_TRANSCRIBE_MODEL = "openai/gpt-4o-audio-preview"
# Map MIME type -> the `format` string OpenRouter expects for input_audio
_AUDIO_FORMAT_BY_MIME = {
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/webm": "webm",
}


def _transcribe_audio(file_data: bytes, mime_type: str, openrouter_key: str) -> str:
    """
    Transcribe an audio recording to text via an OpenRouter multimodal model.

    Sends the audio as a base64 `input_audio` content part to a chat model and
    asks for a verbatim transcript. Returns the transcript text (may be empty on
    failure — caller decides how to handle).
    """
    import base64
    import httpx

    audio_format = _AUDIO_FORMAT_BY_MIME.get(mime_type, "mp3")
    b64 = base64.b64encode(file_data).decode("utf-8")

    payload = {
        "model": AUDIO_TRANSCRIBE_MODEL,
        "modalities": ["text"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Transcribe this meeting recording verbatim. Return only the "
                            "transcript text with no commentary, headers, or timestamps."
                        ),
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {"data": b64, "format": audio_format},
                    },
                ],
            }
        ],
    }

    with httpx.Client(timeout=300.0) as client:
        response = client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code != 200:
        raise Exception(
            f"Audio transcription failed (status {response.status_code}): {response.text[:300]}"
        )

    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise Exception("Audio transcription returned no choices")
    return (choices[0].get("message", {}).get("content") or "").strip()


def _get_openrouter_key_for_debate(cursor, debate_id: str) -> Optional[str]:
    """
    Resolve the best available OpenRouter key for Celery background tasks.

    Priority order:
    1. Server-side key from settings (OPENROUTER_API_KEY env var)
    2. Temporarily stored key in debate's policy_config (set by preflight/upload)
    """
    if settings.openrouter_api_key:
        return settings.openrouter_api_key

    cursor.execute(
        "SELECT policy_config FROM debates WHERE debate_id = %s",
        (debate_id,),
    )
    row = cursor.fetchone()
    if row and row[0]:
        return row[0].get("openrouter_key")

    return None


def _embed_chunks_batch(
    texts: List[str],
    openrouter_key: str,
    model_id: str = EMBEDDINGS_MODEL,
) -> List[Optional[List[float]]]:
    """
    Generate embeddings for a batch of texts via OpenRouter.

    Returns a list of embedding vectors (or None for any that failed).
    """
    import httpx

    results: List[Optional[List[float]]] = [None] * len(texts)

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {openrouter_key}",
                    "Content-Type": "application/json",
                },
                json={"model": model_id, "input": texts},
            )

        if response.status_code == 200:
            data = response.json()
            for item in data.get("data", []):
                idx = item.get("index", 0)
                if idx < len(results):
                    results[idx] = item.get("embedding")
        else:
            print(f"Embedding API error {response.status_code}: {response.text[:200]}")
    except Exception as exc:
        print(f"Embedding batch failed: {exc}")

    return results


def _generate_and_store_embeddings(
    conn,
    chunk_ids: List[str],
    chunk_texts: List[str],
    openrouter_key: str,
) -> int:
    """
    Generate embeddings for a list of chunks and persist them to memory_chunks.

    Returns the count of successfully embedded chunks.
    """
    cursor = conn.cursor()
    total_embedded = 0

    for batch_start in range(0, len(chunk_ids), EMBED_BATCH_SIZE):
        batch_ids = chunk_ids[batch_start : batch_start + EMBED_BATCH_SIZE]
        batch_texts = chunk_texts[batch_start : batch_start + EMBED_BATCH_SIZE]

        vectors = _embed_chunks_batch(batch_texts, openrouter_key)

        for chunk_id, vector in zip(batch_ids, vectors):
            if vector:
                cursor.execute(
                    """
                    UPDATE memory_chunks
                    SET embedding_vector     = %s,
                        embedding_status     = 'complete',
                        embedding_model_id   = %s,
                        embedding_generated_at = NOW(),
                        embedding_error      = NULL
                    WHERE chunk_id = %s
                    """,
                    (Json(vector), EMBEDDINGS_MODEL, chunk_id),
                )
                total_embedded += 1
            else:
                cursor.execute(
                    """
                    UPDATE memory_chunks
                    SET embedding_status = 'failed',
                        embedding_error  = 'API returned no vector'
                    WHERE chunk_id = %s
                    """,
                    (chunk_id,),
                )

    conn.commit()
    return total_embedded


@celery_app.task(name="src.tasks.material_processing.process_material", bind=True)
def process_material(
    self,
    material_id: str,
    debate_id: str,
    openrouter_key: Optional[str] = None,
    category: str = "supplementary",
):
    """
    Main task: Process uploaded material

    Steps:
    1. Fetch material metadata from DB
    2. Download file from MinIO
    3. Validate file
    4. (audio) transcribe to text, else extract text
    5. Chunk text
    6. Store chunks in memory_chunks (tagged with category)
    7. Generate embeddings (if OpenRouter key available)
    8. Update material status

    Args:
        material_id: UUID of material to process
        debate_id: UUID of debate
        openrouter_key: Optional BYOK key forwarded from the upload request
        category: Knowledge-base category, stored on each chunk's metadata
    """
    task_id = self.request.id
    conn = None

    try:
        conn = psycopg2.connect(settings.database_url)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT file_key, file_mime_type, title, kind FROM meeting_materials WHERE material_id = %s AND debate_id = %s",
            (material_id, debate_id),
        )

        result = cursor.fetchone()
        if not result:
            raise Exception(f"Material {material_id} not found")

        file_key, mime_type, title, kind = result

        _update_material_status(
            conn, material_id,
            status="processing",
            processing_metadata={"started_at": datetime.utcnow().isoformat()},
        )
        conn.commit()

        # Download from MinIO
        storage_client = get_storage_client()
        file_data = storage_client.download_file(file_key)

        # Audio recordings: transcribe to text first, then treat like a text material.
        if kind == "audio":
            resolved_key = openrouter_key or _get_openrouter_key_for_debate(cursor, debate_id)
            if not resolved_key:
                raise Exception("Audio transcription requires an OpenRouter API key")
            print(f"Transcribing audio material {material_id} ({mime_type})")
            transcript = _transcribe_audio(file_data, mime_type, resolved_key)
            if not transcript.strip():
                raise Exception("Transcription produced no text")
            # Persist transcript so it is viewable/editable and reusable for action items
            cursor.execute(
                "UPDATE meeting_materials SET body_text = %s WHERE material_id = %s",
                (transcript, material_id),
            )
            conn.commit()
            extraction_result = {
                "text": transcript,
                "extraction_method": "audio_transcription",
                "word_count": len(transcript.split()),
                "sha256": None,
            }
        else:
            # Validate
            is_valid, detected_mime, error_msg = TextExtractor.validate_file(file_data, title)
            if not is_valid:
                raise Exception(f"File validation failed: {error_msg}")

            # Extract text
            extraction_result = TextExtractor.extract(file_data, mime_type)

        if extraction_result.get("is_scanned"):
            _update_material_status(
                conn, material_id,
                status="needs_ocr",
                processing_metadata={
                    "message": "Scanned PDF detected. OCR required.",
                    "page_count": extraction_result.get("page_count", 0),
                },
            )
            conn.commit()
            return {"material_id": material_id, "status": "needs_ocr", "message": "Scanned PDF detected"}

        text = extraction_result.get("text", "")
        if not text or not text.strip():
            raise Exception("No text extracted from file")

        # Chunk text
        chunks = TextChunker.chunk_text(
            text=text,
            material_id=material_id,
            extraction_metadata=extraction_result,
        )

        if not chunks:
            raise Exception("No chunks generated from text")

        # Store chunks — idempotent: serialize concurrent runs of this material
        # with a row lock, then clear chunks from any previous run (retries /
        # concurrent processing must not duplicate them).
        cursor.execute(
            "SELECT material_id FROM meeting_materials WHERE material_id = %s FOR UPDATE",
            (material_id,),
        )
        cursor.execute(
            "DELETE FROM memory_chunks WHERE source_debate_id = %s AND chunk_metadata->>'material_id' = %s",
            (debate_id, str(material_id)),
        )
        chunk_ids: List[str] = []
        chunk_texts: List[str] = []
        for chunk in chunks:
            chunk_meta = {**chunk["chunk_metadata"], "category": category}
            cursor.execute(
                """
                INSERT INTO memory_chunks (
                    chunk_id, agent_id, source_debate_id, chunk_text, chunk_metadata, embedding_status
                )
                VALUES (gen_random_uuid(), NULL, %s, %s, %s, 'not_started')
                RETURNING chunk_id
                """,
                (debate_id, chunk["chunk_text"], Json(chunk_meta)),
            )
            cid = str(cursor.fetchone()[0])
            chunk_ids.append(cid)
            chunk_texts.append(chunk["chunk_text"])

        conn.commit()

        # Generate embeddings
        resolved_key = openrouter_key or _get_openrouter_key_for_debate(cursor, debate_id)
        embeddings_generated = 0

        if resolved_key:
            print(f"Generating embeddings for {len(chunk_ids)} chunks (material {material_id})")
            embeddings_generated = _generate_and_store_embeddings(conn, chunk_ids, chunk_texts, resolved_key)
            print(f"Embedded {embeddings_generated}/{len(chunk_ids)} chunks")
        else:
            print(
                f"No OpenRouter key available — skipping embeddings for material {material_id}. "
                "Set OPENROUTER_API_KEY in .env or run /debates/{id}/materials/embed with BYOK key."
            )

        # Update material status to complete
        processing_metadata = {
            "completed_at": datetime.utcnow().isoformat(),
            "extraction_method": extraction_result.get("extraction_method"),
            "word_count": extraction_result.get("word_count", 0),
            "chunk_count": len(chunks),
            "embeddings_generated": embeddings_generated,
            "sha256": extraction_result.get("sha256"),
        }

        if extraction_result.get("page_count"):
            processing_metadata["page_count"] = extraction_result["page_count"]
        if extraction_result.get("paragraph_count"):
            processing_metadata["paragraph_count"] = extraction_result["paragraph_count"]
        if extraction_result.get("line_count"):
            processing_metadata["line_count"] = extraction_result["line_count"]

        _update_material_status(
            conn, material_id,
            status="complete",
            processing_metadata=processing_metadata,
            processing_completed_at=datetime.utcnow(),
        )
        conn.commit()

        return {
            "material_id": material_id,
            "status": "complete",
            "chunk_count": len(chunks),
            "word_count": extraction_result.get("word_count", 0),
            "embeddings_generated": embeddings_generated,
            "chunk_ids": chunk_ids[:10],
        }

    except Exception as e:
        error_msg = str(e)
        print(f"Error processing material {material_id}: {error_msg}")

        if conn:
            try:
                _update_material_status(
                    conn, material_id,
                    status="failed",
                    processing_metadata={
                        "error": error_msg,
                        "failed_at": datetime.utcnow().isoformat(),
                    },
                )
                conn.commit()
            except Exception as update_error:
                print(f"Failed to update error status: {update_error}")

        raise

    finally:
        if conn:
            conn.close()


@celery_app.task(name="src.tasks.material_processing.generate_debate_embeddings", bind=True)
def generate_debate_embeddings(self, debate_id: str, openrouter_key: str):
    """
    Backfill / on-demand embedding generation for all unembedded chunks in a debate.

    Triggered by:
    - POST /debates/{id}/materials/embed  (BYOK key in header)
    - preflight start (key stored in policy_config)
    """
    conn = None
    try:
        conn = psycopg2.connect(settings.database_url)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT chunk_id, chunk_text
            FROM memory_chunks
            WHERE source_debate_id = %s
              AND agent_id IS NULL
              AND (embedding_status IN ('not_started', 'failed') OR embedding_status IS NULL)
            ORDER BY created_at
            """,
            (debate_id,),
        )
        rows = cursor.fetchall()

        if not rows:
            print(f"No unembedded chunks for debate {debate_id}")
            return {"debate_id": debate_id, "embedded": 0, "skipped": 0}

        chunk_ids = [str(r[0]) for r in rows]
        chunk_texts = [r[1] for r in rows]

        print(f"Backfill: embedding {len(chunk_ids)} chunks for debate {debate_id}")
        embedded = _generate_and_store_embeddings(conn, chunk_ids, chunk_texts, openrouter_key)
        failed = len(chunk_ids) - embedded

        print(f"Backfill complete: {embedded} embedded, {failed} failed")
        return {"debate_id": debate_id, "embedded": embedded, "failed": failed}

    except Exception as exc:
        print(f"generate_debate_embeddings failed for {debate_id}: {exc}")
        raise

    finally:
        if conn:
            conn.close()


def _update_material_status(
    conn,
    material_id: str,
    status: str,
    processing_metadata: Dict = None,
    processing_started_at: datetime = None,
    processing_completed_at: datetime = None,
):
    """Helper to update material processing status"""
    cursor = conn.cursor()

    updates = ["processed_status = %s", "updated_at = NOW()"]
    params = [status]

    if processing_metadata:
        cursor.execute(
            "SELECT processing_metadata FROM meeting_materials WHERE material_id = %s",
            (material_id,),
        )
        existing_meta = cursor.fetchone()
        existing_meta = existing_meta[0] if existing_meta else {}
        merged_meta = {**existing_meta, **processing_metadata}
        updates.append("processing_metadata = %s")
        params.append(Json(merged_meta))

    if processing_started_at:
        updates.append("processing_started_at = %s")
        params.append(processing_started_at)

    if processing_completed_at:
        updates.append("processing_completed_at = %s")
        params.append(processing_completed_at)

    params.append(material_id)

    cursor.execute(
        f"UPDATE meeting_materials SET {', '.join(updates)} WHERE material_id = %s",
        params,
    )
