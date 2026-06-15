"""
Memory Retrieval Service
Implements enforcement hook for memory import with auditing
TICKET-13C: Semantic retrieval using embeddings + cosine similarity
"""

import psycopg2
import math
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from psycopg2.extras import Json

from src.config import settings
from src.database import get_cursor
from src.schemas.memory import MemoryChunkResult, MemoryRetrievalResponse


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Compute cosine similarity between two vectors
    
    Formula: cos(θ) = (A · B) / (||A|| × ||B||)
    
    Args:
        vec1: First vector (embedding)
        vec2: Second vector (embedding)
    
    Returns:
        Similarity score between -1 and 1 (higher is more similar)
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    
    # Dot product
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    
    # Magnitudes
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)


def get_query_embedding(
    query: str,
    openrouter_key: Optional[str],
    embeddings_model_id: str = 'openai/text-embedding-3-small'
) -> Optional[List[float]]:
    """
    Generate embedding for a query using OpenRouter
    
    Args:
        query: Query text
        openrouter_key: OpenRouter API key (BYOK)
        embeddings_model_id: Model ID for embeddings
    
    Returns:
        Embedding vector or None if failed
    """
    if not openrouter_key:
        return None
    
    try:
        import httpx
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {openrouter_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": embeddings_model_id,
                    "input": query
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data') and len(data['data']) > 0:
                    return data['data'][0]['embedding']
            
            return None
    except Exception as e:
        print(f"Failed to generate query embedding: {e}")
        return None


def retrieve_allowed_chunks(
    debate_id: str,
    participant_id: Optional[str],
    query: str,
    top_k: int = 10,
    openrouter_key: Optional[str] = None,
    use_semantic: bool = True,
    query_embedding: Optional[List[float]] = None
) -> MemoryRetrievalResponse:
    """
    Retrieve chunks that a participant is allowed to access
    
    Enforcement rules:
    1. Always include current debate's material chunks (source_debate_id = debate_id, agent_id IS NULL)
    2. Include imported sources ONLY if matching grant exists:
       - scope='all_agents' applies to any participant
       - scope='specific_agents' applies only to granted participant_ids
    3. Log retrieval to memory_access_log with chunk_ids and grant_ids
    
    Retrieval methods (TICKET-13C, TICKET-13C.1):
    - Semantic (preferred): Cosine similarity over embeddings
      - Requires: query_embedding (pre-computed) OR openrouter_key
      - Falls back to keyword if embeddings missing
    - Keyword (fallback): Simple word matching in chunk_text
    
    Performance constraints:
    - Hard cap: Only consider chunks from allowed_source_debate_ids (enforced by grants)
    - Embedding candidate selection: Filter by embedding_status='complete' before loading vectors
    - This avoids loading all chunks into memory (scales to thousands of chunks per debate)
    
    BYOK Safety (TICKET-13C.1):
    - Preflight can pre-compute query_embedding at request time (with BYOK key in header)
    - Store embedding vector (not key) in metadata
    - Retrieval uses stored embedding without needing key again
    
    Args:
        debate_id: Current debate ID
        participant_id: Participant requesting retrieval (None for all)
        query: Search query
        top_k: Maximum chunks to return
        openrouter_key: OpenRouter API key for embedding generation (BYOK)
        use_semantic: Whether to attempt semantic retrieval (default True)
        query_embedding: Pre-computed query embedding (BYOK-safe, preferred for preflight)
    
    Returns:
        MemoryRetrievalResponse with chunks, grant_ids used, and retrieval_method
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = get_cursor(conn)
    
    try:
        # 0. Resolve agent_id from participant_id for audit logging
        agent_id_for_logging = None
        if participant_id:
            cursor.execute("""
                SELECT agent_config->>'agent_id' AS agent_id
                FROM participants
                WHERE participant_id = %s
            """, (participant_id,))
            result = cursor.fetchone()
            if result and result.get('agent_id'):
                agent_id_for_logging = result['agent_id']
        
        # 1. Get allowed source debate IDs based on grants
        allowed_source_debate_ids = [debate_id]  # Always include current debate
        grant_ids_used = []
        # Sources imported as 'materials_only' must not expose agent-generated chunks
        materials_only_sources = []

        # Grants with scope='all_agents' apply even without a participant context
        # (e.g. research analysis for practice Q&A). 'specific_agents' grants need one.
        cursor.execute("""
            SELECT grant_id, source_debate_id, source_type
            FROM debate_memory_grants
            WHERE debate_id = %s
              AND (
                  scope = 'all_agents'
                  OR (scope = 'specific_agents' AND %s::text = ANY(allowed_participant_ids::text[]))
              )
              AND (expires_at IS NULL OR expires_at > NOW())
        """, (debate_id, participant_id or ''))

        grants = cursor.fetchall()
        for grant in grants:
            source_debate_id = str(grant['source_debate_id']) if grant['source_debate_id'] else None
            if source_debate_id and source_debate_id not in allowed_source_debate_ids:
                allowed_source_debate_ids.append(source_debate_id)
                grant_ids_used.append(str(grant['grant_id']))
                if grant.get('source_type') == 'materials_only':
                    materials_only_sources.append(source_debate_id)
        
        # 2. Attempt semantic retrieval if requested
        retrieval_method = 'keyword'  # Default
        actual_query_embedding = query_embedding  # Use pre-computed if provided
        
        if use_semantic and not actual_query_embedding and openrouter_key:
            # Generate query embedding on-the-fly (BYOK).
            # The query MUST be embedded with the same model as the stored chunks
            # (cosine similarity across different models is meaningless), so derive
            # the model from the chunks themselves; workspace settings are only a
            # fallback when no chunks are embedded yet.
            cursor.execute("""
                SELECT embedding_model_id AS model_id, COUNT(*) AS n
                FROM memory_chunks
                WHERE source_debate_id = ANY(%s::uuid[])
                  AND embedding_status = 'complete'
                  AND embedding_model_id IS NOT NULL
                GROUP BY embedding_model_id
                ORDER BY n DESC
                LIMIT 1
            """, (allowed_source_debate_ids,))
            chunk_model = cursor.fetchone()

            if chunk_model and chunk_model.get('model_id'):
                embeddings_model_id = chunk_model['model_id']
            else:
                cursor.execute("""
                    SELECT w.settings->>'embeddings_model_id' AS model_id
                    FROM debates d
                    JOIN workspaces w ON d.workspace_id = w.workspace_id
                    WHERE d.debate_id = %s
                """, (debate_id,))
                model_result = cursor.fetchone()
                embeddings_model_id = (
                    model_result['model_id']
                    if model_result and model_result.get('model_id')
                    else 'openai/text-embedding-3-small'
                )

            # Generate query embedding
            actual_query_embedding = get_query_embedding(query, openrouter_key, embeddings_model_id)
            if actual_query_embedding is None:
                print(f"memory_retrieval: query embedding failed (model={embeddings_model_id}) — falling back to keyword search")
        
        if actual_query_embedding:
            retrieval_method = 'semantic'
        
        # 3. Retrieve chunks based on method
        rows = []
        
        if retrieval_method == 'semantic' and actual_query_embedding:
            # Semantic retrieval: cosine similarity over embeddings
            # Constraint: Only load chunks with embedding_status='complete' to avoid memory issues
            cursor.execute("""
                SELECT
                    chunk_id,
                    chunk_text,
                    source_debate_id,
                    agent_id,
                    chunk_metadata,
                    embedding_vector,
                    embedding_model_id
                FROM memory_chunks
                WHERE source_debate_id = ANY(%s::uuid[])
                  AND embedding_status = 'complete'
                  AND embedding_vector IS NOT NULL
                  AND (
                      -- Current debate materials (agent_id IS NULL)
                      (source_debate_id = %s AND agent_id IS NULL)
                      -- Imported debate chunks (if grants exist)
                      OR (source_debate_id != %s)
                  )
                  -- 'materials_only' imports: exclude agent-generated chunks
                  AND NOT (source_debate_id = ANY(%s::uuid[]) AND agent_id IS NOT NULL)
            """, (allowed_source_debate_ids, debate_id, debate_id, materials_only_sources))
            
            candidate_chunks = cursor.fetchall()
            
            if not candidate_chunks:
                # No embeddings available, fall back to keyword
                retrieval_method = 'keyword_fallback'
            else:
                # Compute cosine similarity for each chunk in Python
                scored_chunks = []

                for row in candidate_chunks:
                    embedding_vector = row['embedding_vector']
                    # JSONB vector is stored as array
                    if isinstance(embedding_vector, list):
                        similarity = cosine_similarity(actual_query_embedding, embedding_vector)
                        scored_chunks.append({
                            'chunk_id': row['chunk_id'],
                            'chunk_text': row['chunk_text'],
                            'source_debate_id': row['source_debate_id'],
                            'agent_id': row['agent_id'],
                            'chunk_metadata': row['chunk_metadata'],
                            'score': similarity,
                        })
                    else:
                        print(f"memory_retrieval: chunk {row['chunk_id']} marked complete but has no usable vector — skipping")

                # Sort by similarity (descending) and take top_k
                scored_chunks.sort(key=lambda x: x['score'], reverse=True)
                rows = scored_chunks[:top_k]
        
        if not rows:
            # Keyword retrieval (fallback or primary)
            retrieval_method = retrieval_method if retrieval_method == 'keyword_fallback' else 'keyword'
            
            query_words = query.lower().split()
            
            cursor.execute("""
                WITH scored_chunks AS (
                    SELECT
                        chunk_id,
                        chunk_text,
                        source_debate_id,
                        agent_id,
                        chunk_metadata,
                        -- Simple keyword scoring: count matches of query words in chunk_text
                        (
                            SELECT COUNT(*)
                            FROM unnest(%s::text[]) AS word
                            WHERE LOWER(chunk_text) LIKE '%%' || word || '%%'
                        ) AS score
                    FROM memory_chunks
                    WHERE source_debate_id = ANY(%s::uuid[])
                      AND (
                          -- Current debate materials (agent_id IS NULL)
                          (source_debate_id = %s AND agent_id IS NULL)
                          -- Imported debate chunks (if grants exist)
                          OR (source_debate_id != %s)
                      )
                      -- 'materials_only' imports: exclude agent-generated chunks
                      AND NOT (source_debate_id = ANY(%s::uuid[]) AND agent_id IS NOT NULL)
                )
                SELECT
                    chunk_id,
                    chunk_text,
                    source_debate_id,
                    agent_id,
                    chunk_metadata,
                    score
                FROM scored_chunks
                WHERE score > 0
                ORDER BY score DESC, chunk_id
                LIMIT %s
            """, (query_words, allowed_source_debate_ids, debate_id, debate_id, materials_only_sources, top_k))
            
            rows = cursor.fetchall()
        
        # 4. Build response
        chunks = []
        chunk_ids = []
        
        for row in rows:
            chunk_metadata = row['chunk_metadata']
            chunks.append(MemoryChunkResult(
                chunk_id=str(row['chunk_id']),
                chunk_text=row['chunk_text'],
                source_debate_id=str(row['source_debate_id']),
                source_material_id=chunk_metadata.get('material_id') if chunk_metadata else None,
                agent_id=str(row['agent_id']) if row['agent_id'] else None,
                chunk_metadata=chunk_metadata or {},
                score=float(row['score'])
            ))
            chunk_ids.append(str(row['chunk_id']))
        
        # 5. Log retrieval to memory_access_log for audit (only if agent_id resolved)
        if agent_id_for_logging:
            cursor.execute("""
                INSERT INTO memory_access_log (
                    access_id,
                    agent_id,
                    debate_id,
                    access_type,
                    query_text,
                    results_count,
                    chunk_ids,
                    metadata,
                    created_at
                ) VALUES (
                    gen_random_uuid(),
                    %s,
                    %s,
                    'retrieval',
                    %s,
                    %s,
                    %s::uuid[],
                    %s,
                    NOW()
                )
            """, (
                agent_id_for_logging,
                debate_id,
                query,
                len(chunks),
                chunk_ids,
                Json({
                    'grant_ids': grant_ids_used,
                    'retrieval_method': retrieval_method,
                    'allowed_source_debate_ids': allowed_source_debate_ids,
                    'embeddings_available': retrieval_method == 'semantic',
                    'query_embedding_used': actual_query_embedding is not None
                })
            ))
        
        conn.commit()
        
        return MemoryRetrievalResponse(
            debate_id=debate_id,
            participant_id=participant_id,
            query=query,
            chunks=chunks,
            total_chunks=len(chunks),
            grant_ids_used=grant_ids_used,
            retrieval_method=retrieval_method
        )
    
    finally:
        cursor.close()
        conn.close()


def check_participant_has_access(
    debate_id: str,
    participant_id: str,
    source_debate_id: str
) -> bool:
    """
    Check if a participant has access to a source debate's memory
    
    Args:
        debate_id: Current debate ID
        participant_id: Participant ID to check
        source_debate_id: Source debate ID to check access for
    
    Returns:
        True if participant has access, False otherwise
    """
    if source_debate_id == debate_id:
        # Always have access to current debate's own materials
        return True
    
    conn = psycopg2.connect(settings.database_url)
    cursor = get_cursor(conn)
    
    try:
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM debate_memory_grants
                WHERE debate_id = %s
                  AND source_debate_id = %s
                  AND (
                      scope = 'all_agents'
                      OR (scope = 'specific_agents' AND %s::text = ANY(allowed_participant_ids::text[]))
                  )
                  AND (expires_at IS NULL OR expires_at > NOW())
            ) AS has_access
        """, (debate_id, source_debate_id, participant_id))

        result = cursor.fetchone()
        return bool(result['has_access']) if result else False
    
    finally:
        cursor.close()
        conn.close()
