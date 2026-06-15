"""
Backfill embeddings for all memory_chunks that are missing them.

Usage:
    cd apps/api
    source .venv/bin/activate
    python scripts/backfill_embeddings.py --key sk-or-v1-...

Or set OPENROUTER_API_KEY in .env and run without --key.
"""
import argparse
import sys
import os

# Allow imports from src/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import Json
from src.config import settings
from src.tasks.material_processing import (
    _embed_chunks_batch,
    EMBEDDINGS_MODEL,
    EMBED_BATCH_SIZE,
)


def backfill(openrouter_key: str, debate_id: str | None = None):
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()

    query = """
        SELECT chunk_id, chunk_text, source_debate_id
        FROM memory_chunks
        WHERE embedding_status IN ('not_started', 'failed')
          AND agent_id IS NULL
    """
    params = []
    if debate_id:
        query += " AND source_debate_id = %s"
        params.append(debate_id)

    query += " ORDER BY created_at"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    if not rows:
        print("No chunks to embed.")
        conn.close()
        return

    print(f"Found {len(rows)} chunk(s) to embed.")

    chunk_ids = [str(r[0]) for r in rows]
    chunk_texts = [r[1] for r in rows]

    total_ok = 0
    total_fail = 0

    for batch_start in range(0, len(chunk_ids), EMBED_BATCH_SIZE):
        batch_ids = chunk_ids[batch_start : batch_start + EMBED_BATCH_SIZE]
        batch_texts = chunk_texts[batch_start : batch_start + EMBED_BATCH_SIZE]
        end = batch_start + len(batch_ids)
        print(f"  Embedding chunks {batch_start+1}–{end} ...", end=" ", flush=True)

        vectors = _embed_chunks_batch(batch_texts, openrouter_key)

        for chunk_id, vector in zip(batch_ids, vectors):
            if vector:
                cursor.execute(
                    """
                    UPDATE memory_chunks
                    SET embedding_vector      = %s,
                        embedding_status      = 'complete',
                        embedding_model_id    = %s,
                        embedding_generated_at = NOW(),
                        embedding_error       = NULL
                    WHERE chunk_id = %s
                    """,
                    (Json(vector), EMBEDDINGS_MODEL, chunk_id),
                )
                total_ok += 1
            else:
                cursor.execute(
                    "UPDATE memory_chunks SET embedding_status='failed', embedding_error='no vector returned' WHERE chunk_id=%s",
                    (chunk_id,),
                )
                total_fail += 1

        conn.commit()
        print(f"done ({sum(1 for v in vectors if v)} ok)")

    print(f"\nBackfill complete: {total_ok} embedded, {total_fail} failed.")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill embeddings for memory_chunks")
    parser.add_argument("--key", help="OpenRouter API key (overrides OPENROUTER_API_KEY env)")
    parser.add_argument("--debate", help="Limit to a specific debate_id (optional)")
    args = parser.parse_args()

    key = args.key or settings.openrouter_api_key
    if not key:
        print("ERROR: No OpenRouter key. Pass --key sk-or-v1-... or set OPENROUTER_API_KEY in .env")
        sys.exit(1)

    backfill(key, debate_id=args.debate)
