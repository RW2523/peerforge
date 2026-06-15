# TICKET-15.1: Memory Import Hardening (Contracts + Real Audit Logging)

**Date**: 2026-02-10  
**Scope**: Memory Import V1 - Contract enforcement + Audit logging validation  
**Status**: PASS ✅  

---

## Summary

Hardened Memory Import V1 to be enterprise-ready by:
1. Adding all memory endpoints to OpenAPI contract with full schemas
2. Enforcing memory endpoints in contract validation gates
3. Fixing audit logging to properly resolve agent_id from participants.agent_config
4. Adding comprehensive test that proves audit logging works with real DB rows

This ticket makes Memory Import V1 audit-compliant and contract-enforced.

---

## What Changed

### Backend Changes
1. **apps/api/src/services/memory_retrieval.py**
   - Added agent_id resolution from participants.agent_config->>'agent_id'
   - Fixed audit logging to use resolved agent_id (not participant_id)
   - Ensured chunk_ids and grant_ids are properly logged in memory_access_log

### Contract Changes
2. **packages/contracts/openapi/arinar-v1.yaml**
   - Added 5 memory endpoints:
     - GET /workspaces/{workspace_id}/memory/importable
     - GET /debates/{debate_id}/memory/preview
     - POST /debates/{debate_id}/memory/import
     - GET /debates/{debate_id}/memory/grants
     - DELETE /debates/{debate_id}/memory/grants/{grant_id}
   - Added 8 new schemas:
     - ImportableDebate
     - ImportableSourcesResponse
     - MemoryPreviewChunk
     - MemoryPreviewResponse
     - MemoryImportRequest
     - MemoryImportResponse
     - MemoryGrant
     - MemoryGrantsResponse
   - Added 'memory' tag for documentation

3. **packages/contracts/scripts/validate-openapi.js**
   - Added 5 memory endpoints to requiredEndpoints enforcement list

4. **packages/contracts/tests/contracts.test.js**
   - Added 5 memory paths to requiredPaths test

### Test Changes
5. **apps/api/tests/test_memory_import.py**
   - Added `test_audit_logging_with_real_agent()` - comprehensive test proving:
     - agent_id is correctly resolved from participants.agent_config
     - chunk_ids are logged in memory_access_log
     - grant_ids are logged in metadata
     - All FK constraints are satisfied

---

## Commands Run

### Contract Validation
```bash
cd /Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/packages/contracts
npm run validate:openapi
# ✅ All 28 endpoints validated
# ✅ All 5 memory endpoints present

npm test
# ✅ 9 tests passed
# ✅ All required memory paths validated

npm run generate:types
# ✅ TypeScript types generated
```

### API Tests
```bash
cd /Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/api
.venv/bin/python3.11 -m pytest tests/test_memory_import.py -v
# ✅ 9 tests passed (including new audit logging test)
```

### Full Verification
```bash
cd /Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2
make verify
# ✅ All quality gates passed
# ⚠️ 1 warning (TODO comments in memory.py - acceptable, non-blocking)
```

---

## Gates Checklist

| Gate | Status | Evidence |
|------|--------|----------|
| OpenAPI includes memory endpoints | ✅ YES | 5 endpoints validated |
| Contract validation enforces endpoints | ✅ YES | validate-openapi.js + contracts.test.js |
| Agent_id resolution works | ✅ YES | test_audit_logging_with_real_agent passes |
| Audit log FK satisfied | ✅ YES | memory_access_log.agent_id -> agents.agent_id |
| Chunk_ids logged | ✅ YES | Test asserts chunk_ids in audit row |
| Grant_ids logged in metadata | ✅ YES | Test asserts metadata.grant_ids present |
| Types generated | ✅ YES | api-types.ts includes memory schemas |
| make verify passes | ✅ YES | All gates green |
| No new skipped tests | ✅ YES | All 9 memory tests execute |
| OpenRouter-only policy | ✅ YES | No provider SDK usage |

---

## Audit Logging Evidence

### Test: test_audit_logging_with_real_agent

**Setup**:
1. Created persistent agent in `agents` table
2. Created source debate with memory chunk containing "Contract terms and legal requirements"
3. Created target debate (pending)
4. Created participant linked to persistent agent via agent_config: `{"agent_id": "<uuid>", "model_id": "..."}`
5. Created memory grant allowing all_agents access

**Execution**:
```python
result = retrieve_allowed_chunks(
    debate_id=target_debate_id,
    participant_id=participant_id,
    query="contract legal",
    top_k=10
)
```

**Assertions Passed**:
- ✅ Chunks retrieved from source debate
- ✅ Grant ID present in result.grant_ids_used
- ✅ Audit log row created
- ✅ Audit log.agent_id == persistent agent_id (not participant_id)
- ✅ Audit log.chunk_ids contains returned chunk UUIDs
- ✅ Audit log.metadata.grant_ids contains grant UUID
- ✅ Audit log.metadata.retrieval_method == 'keyword'

**SQL Evidence Snippet**:
```sql
SELECT agent_id, debate_id, chunk_ids, metadata
FROM memory_access_log
WHERE debate_id = '<target_debate_id>' 
  AND agent_id = '<resolved_agent_id>'
ORDER BY created_at DESC
LIMIT 1;

-- Returns:
-- agent_id: <persistent agent UUID>
-- chunk_ids: [<source_chunk_id>]
-- metadata: {"grant_ids": ["<grant_id>"], "retrieval_method": "keyword", "allowed_source_debate_ids": [...]}
```

---

## Blockers

None. All gates passed.

---

## Next Steps (out of scope for this ticket)

1. **Web UI Component**: Add Memory Import step to setup wizard (TICKET-15.2)
2. **Vector Search Upgrade**: Replace keyword scoring with pgvector embeddings (future optimization)
3. **Artifact Grants**: Extend to support source_artifact_id once artifact schema exists
4. **Grant Analytics**: Add dashboard showing grant usage patterns

---

## Engineering Notes

### Agent ID Resolution Strategy
We chose to resolve agent_id from `participants.agent_config->>'agent_id'` because:
- Participants may be persistent agents (have agent_id) or inline agents (no agent_id)
- Audit logging requires FK to agents.agent_id for compliance
- If no agent_id exists (inline agent), audit logging is skipped for now
- This is acceptable for V1; inline agents are temporary and don't need long-term audit trails
- Enterprise customers use persistent agents, which will have full audit logging

### Why Contract Enforcement Matters
Without contract gates, endpoints can drift or be removed without detection. By adding memory endpoints to:
- `validate-openapi.js`: ensures CI fails if endpoints disappear
- `contracts.test.js`: ensures test suite validates required paths
- Generated types: ensures frontend has type-safe API access

This prevents regression and ensures memory import remains stable across releases.

### TODO Comments
Two TODO comments remain in `apps/api/src/routes/memory.py`:
- Line 61: `0 AS artifact_count, -- TODO: join artifacts table when implemented`
- Line 361: `NULL AS source_artifact_title, -- TODO: join artifacts when implemented`

These are acceptable because:
- Artifact schema doesn't exist yet (deferred to live artifacts ticket)
- Queries will work correctly when artifact joins are added
- No production code is blocked

---

**Report Status**: PASS ✅  
**All Gates**: GREEN ✅  
**Contract Enforcement**: LIVE ✅  
**Audit Logging**: PROVEN ✅
