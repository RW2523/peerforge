# TICKET-13C.1: Remove Skip + BYOK-Safe Preflight Query Embeddings

**Date**: 2026-02-10  
**Scope**: Fix skipped test + implement BYOK-safe query embedding storage  
**Status**: PASS ✅  

---

## Summary

Fixed two critical issues from TICKET-13C:
1. **Removed skipped test**: Fixed `test_semantic_retrieval_respects_grants` - now PASS
2. **BYOK-safe embeddings**: Preflight no longer reads OpenRouter keys from DB

**Key Achievement**: Query embeddings are now generated at preflight START time (with BYOK header) and stored as vectors (not keys) in metadata, enabling semantic retrieval without violating BYOK promise.

---

## Problem 1: New Skipped Test (Policy Violation)

**Issue**: `test_semantic_retrieval_respects_grants` was marked `@pytest.mark.skip` due to DB constraint errors.

**Root Causes**:
1. Test used `debates.status` column (correct: `debates.state`)
2. Test omitted required `participants.participant_type` and `participants.role_name`
3. Test used `debate_memory_grants.created_by` (correct: `granted_by`)

**Fixes Applied**:
- Line 287: `INSERT INTO debates (... status ...)` → `state`
- Line 305: Same fix for target debate
- Line 314: Added `participant_type='agent', role_name='Test Strategic Analyst'`
- Line 324: `created_by='test'` → `granted_by='test-user'`

**Result**: Test now PASS (unskipped).

---

## Problem 2: BYOK Violation (Enterprise Blocker)

**Original Issue** (TICKET-13C):
```python
# preflight.py line 161 (old)
openrouter_key = policy_config.get('openrouter_key')  # ❌ Reads key from DB
```

**Why This Violates BYOK**:
- OpenRouter keys must never be stored in `policy_config` or any DB column
- This would require users to save keys server-side (security risk)
- Multi-device sync would spread keys across infra (compliance violation)

**Solution** (TICKET-13C.1):
Generate query embeddings at preflight START time, store only the embedding vector.

---

## Implementation: BYOK-Safe Query Embeddings

### Architecture:

```
User Clicks "Start Preflight" (Web UI)
  ↓
POST /debates/{debate_id}/preflight/start
Header: X-OpenRouter-Key: sk-or-v1-... (BYOK, not stored)
  ↓
For each participant:
  1. Build semantic query = problem_statement + role
  2. Call OpenRouter embeddings API (key in-memory only)
  3. Store embedding vector in preflight_participant_runs.metadata
  4. Drop key (Python GC)
  ↓
Preflight task runs (Celery)
  1. Read query_embedding from metadata (no key needed)
  2. Call retrieve_allowed_chunks(query_embedding=..., openrouter_key=None)
  3. Semantic retrieval works without key ✅
```

### 1. Preflight Start Endpoint (routes/preflight.py)

**Added**:
- Import: `from src.services.memory_retrieval import get_query_embedding`
- Import: `Header` from fastapi
- Parameter: `x_openrouter_key: Optional[str] = Header(None)`

**Logic** (lines 148-200):
```python
# Get participants + policy_config + workspace embeddings model
cursor.execute("""
    SELECT p.participant_id, p.agent_config, d.policy_config,
           w.settings->>'embeddings_model_id' AS embeddings_model
    FROM participants p
    JOIN debates d ON p.debate_id = d.debate_id
    JOIN workspaces w ON d.workspace_id = w.workspace_id
    WHERE d.debate_id = %s
""", (debate_id,))

participants = cursor.fetchall()
policy_config = participants[0][2]
embeddings_model_id = participants[0][3] or 'moonshot/kimi-embeddings-v1'
problem_statement = policy_config.get('problem_statement', '')

# For each participant: generate query embedding
for participant in participants:
    participant_id, agent_config = participant[0], participant[1]
    
    query_embedding = None
    if x_openrouter_key and problem_statement:
        system_prompt = agent_config.get('system_prompt', '')
        semantic_query = f"{problem_statement[:300]}\n\nRole: {system_prompt[:200]}"
        
        # BYOK: key used once, not stored
        query_embedding = get_query_embedding(semantic_query, x_openrouter_key, embeddings_model_id)
    
    # Store embedding vector (not key) in metadata
    initial_metadata = {}
    if query_embedding:
        initial_metadata = {
            'query_embedding': query_embedding,           # ✅ Vector only
            'query_embedding_model_id': embeddings_model_id,
            'semantic_query_generated_at': datetime.utcnow().isoformat()
        }
    
    cursor.execute("""
        INSERT INTO preflight_participant_runs (
            participant_run_id, run_id, participant_id, agent_id, status, metadata
        ) VALUES (gen_random_uuid(), %s, %s, %s, 'queued', %s)
    """, (run_id, participant_id, agent_id, Json(initial_metadata)))
```

**Result**: Query embeddings generated once at start, stored as vectors, key dropped.

### 2. Retrieval Function (services/memory_retrieval.py)

**Added Parameter**:
```python
def retrieve_allowed_chunks(
    ...
    query_embedding: Optional[List[float]] = None  # NEW
) -> MemoryRetrievalResponse:
```

**Logic** (lines 157-179):
```python
# Attempt semantic retrieval
actual_query_embedding = query_embedding  # Use pre-computed if provided

if use_semantic and not actual_query_embedding and openrouter_key:
    # Fallback: generate on-the-fly (for non-preflight endpoints)
    actual_query_embedding = get_query_embedding(query, openrouter_key, ...)

if actual_query_embedding:
    retrieval_method = 'semantic'
    # ... cosine similarity scoring ...
```

**Result**: Accepts pre-computed embeddings (BYOK-safe) OR generates on-the-fly (other endpoints).

### 3. Preflight Task (tasks/preflight.py)

**Before**:
```python
openrouter_key = policy_config.get('openrouter_key')  # ❌ Reads from DB
```

**After**:
```python
# Get pre-computed query embedding from participant_run metadata (BYOK-safe)
cursor.execute("""
    SELECT metadata FROM preflight_participant_runs WHERE participant_run_id = %s
""", (participant_run_id,))

run_metadata = cursor.fetchone()
stored_query_embedding = None
if run_metadata and run_metadata[0]:
    stored_query_embedding = run_metadata[0].get('query_embedding')

# Use stored embedding (no key needed)
memory_retrieval_result = retrieve_allowed_chunks(
    debate_id=debate_id,
    participant_id=participant_id,
    query=semantic_query,
    top_k=15,
    openrouter_key=None,       # ✅ No key needed
    use_semantic=True,
    query_embedding=stored_query_embedding  # ✅ Pre-computed vector
)
```

**Result**: Preflight never reads OpenRouter keys from DB. BYOK promise preserved.

---

## Tests Fixed

### 1. `test_semantic_retrieval_respects_grants()` - NOW PASS ✅

**Fixed Issues**:
- Schema: `status` → `state` (debates table)
- Schema: Added required `participant_type`, `role_name` (participants table)
- Schema: `created_by` → `granted_by`, `created_at` → `granted_at` (debate_memory_grants)

**Test Flow**:
1. Create agent in agents table (FK requirement)
2. Create source debate with embedded chunk (vector [1.0, 0.0, 0.0])
3. Create target debate with participant
4. NO grant - assert retrieval returns 0 chunks ✅
5. CREATE grant (all_agents) - assert retrieval returns 1 chunk ✅
6. Assert grant_id is in result.grant_ids_used ✅

**Result**: Proves semantic retrieval respects grants (no bypass).

---

## Commands Run

### API Tests
```bash
make api-test

# Output (concise):
==================== 83 passed, 1 skipped, 2 warnings in 4.66s ====================
✅ API tests passed

# Breakdown:
- test_semantic_retrieval_respects_grants: PASS (was SKIP)
- All other semantic tests: PASS
- Total semantic tests: 8 (7 PASS, 1 SKIP - different test)
```

### Full Verification
```bash
make verify

# Output (concise):
✅ All quality gates passed!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Files Changed (3 total)

1. **`apps/api/src/routes/preflight.py`** (+48 lines, now 489 lines)
   - Added `x_openrouter_key: Optional[str] = Header(None)` to start_preflight
   - Generate query embeddings for each participant at start time
   - Store embedding vectors (not keys) in `preflight_participant_runs.metadata`

2. **`apps/api/src/tasks/preflight.py`** (+10 lines, now 333 lines)
   - Read `query_embedding` from participant_run.metadata
   - Pass to `retrieve_allowed_chunks()` as parameter
   - Removed `policy_config.get('openrouter_key')` (BYOK violation)

3. **`apps/api/src/services/memory_retrieval.py`** (+5 lines, now 445 lines)
   - Added `query_embedding: Optional[List[float]]` parameter
   - Use pre-computed embedding if provided (preflight path)
   - Fall back to on-the-fly generation if key provided (other endpoints)

4. **`apps/api/tests/test_semantic_retrieval.py`** (fixed 8 lines)
   - Removed `@pytest.mark.skip` decorator
   - Fixed debates.state column usage
   - Fixed participants.participant_type and role_name
   - Fixed debate_memory_grants.granted_by and granted_at

---

## BYOK Compliance Audit

### ✅ Keys Never Stored
**Database**:
```sql
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'preflight_participant_runs';

-- Results:
participant_run_id | uuid
run_id             | uuid
participant_id     | uuid
agent_id           | uuid
status             | varchar
started_at         | timestamptz
completed_at       | timestamptz
error              | text
skip_reason        | text
prep_pack_knowledge_id | uuid
metadata           | jsonb

-- ✅ No 'api_key', 'openrouter_key', 'credentials' column
```

**Metadata Content** (example):
```json
{
  "query_embedding": [0.023, 0.891, -0.134, ...],
  "query_embedding_model_id": "moonshot/kimi-embeddings-v1",
  "semantic_query_generated_at": "2026-02-10T23:05:30Z"
}
```
✅ Only vector stored, not key.

### ✅ Keys Used In-Memory Only
**Code Audit** (preflight.py lines 172-175):
```python
if x_openrouter_key and problem_statement:
    ...
    query_embedding = get_query_embedding(semantic_query, x_openrouter_key, embeddings_model_id)
    # Key dropped after function returns (Python GC)
```

**Network Call** (memory_retrieval.py lines 60-73):
```python
with httpx.Client(timeout=30.0) as client:
    response = client.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={"Authorization": f"Bearer {openrouter_key}"},  # ✅ Used here only
        ...
    )
# Key dropped when context exits
```

---

## Gates Checklist

| Gate | Status |
|------|--------|
| Skipped test removed | YES |
| `test_semantic_retrieval_respects_grants` PASS | YES |
| Preflight reads query embedding from metadata | YES |
| Preflight does NOT read key from policy_config | YES |
| Query embeddings generated at START time | YES |
| Embedding vectors stored (not keys) | YES |
| retrieve_allowed_chunks accepts pre-computed embedding | YES |
| No new skipped tests | YES |
| make verify | YES |
| 83 API tests PASS | YES |
| File sizes < limits | YES |
| BYOK promise kept | YES |

---

## Next Steps

### TICKET-14: pgvector Migration
- Replace Python cosine similarity with SQL `<=>` operator
- Add index for 10x faster retrieval at scale
- Maintain BYOK-safe query embedding storage (same pattern)

---

**Report Status**: PASS ✅  
**make verify**: PASS ✅  
**Skipped tests**: 1 (unchanged, unrelated to this ticket)  
**BYOK compliance**: VERIFIED ✅
