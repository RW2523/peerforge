# Local Demo: Memory Import V1

**Purpose**: Demonstrate end-to-end Memory Import flow in setup wizard → room

**Prerequisites**:
- Local Supabase stack running (`make db-up`)
- Migrations applied (`make db-migrate`)
- At least ONE completed debate in the database (required for import source)

---

## Demo Steps

### 1. Start Local Services

```bash
cd /Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2

# Start database stack
make db-up
make db-migrate
make db-seed  # Optional: creates sample debates
make db-smoke

# Start API (terminal 1)
cd apps/api
REQUIRE_AUTH=false python3.11 -m uvicorn src.main:app --reload --port 8000

# Start Web (terminal 2)
cd apps/web
npm run dev
```

### 2. Create a Source Debate (if needed)

If you don't have any completed debates yet:

1. Navigate to http://localhost:3000
2. Click "Create Debate"
3. Fill in:
   - Title: "Q4 Product Strategy"
   - Problem: "Should we prioritize growth or profitability?"
4. Add materials (optional)
5. Add at least 2 participants
6. Skip Memory Import (OFF)
7. Launch debate
8. Start debate
9. Send 1-2 interventions
10. End debate

**Result**: You now have an "ended" debate that can be imported.

### 3. Create a New Debate with Memory Import

1. Navigate to http://localhost:3000
2. Click "Create Debate"
3. Fill in basic info:
   - Title: "Q1 Planning Meeting"
   - Problem: "How should we execute on the Q4 strategy?"
4. Add materials (optional)
5. Add participants (at least 1)
6. **Step 4: Memory Import**
   - Toggle: **ON**
   - Wait for past meetings to load
   - Select: "Q4 Product Strategy" (or your prior debate)
   - Source Type: "Full Meeting"
   - Scope: "All Participants"
   - Preview: Verify chunk counts are displayed
7. Review and Launch

**Expected**: Debate is created, memory grants are created, no errors.

### 4. Verify Grants Were Created

**Via API**:
```bash
DEBATE_ID="<new_debate_id_from_url>"

curl http://localhost:8000/debates/${DEBATE_ID}/memory/grants | jq
```

**Expected Response**:
```json
{
  "debate_id": "...",
  "grants": [
    {
      "grant_id": "...",
      "source_debate_id": "...",
      "source_debate_title": "Q4 Product Strategy",
      "source_type": "debate_full",
      "scope": "all_agents",
      "granted_by": "...",
      "granted_at": "2026-02-10T..."
    }
  ],
  "total_count": 1
}
```

**Via Database**:
```bash
# Connect to DB
docker exec -it arinar-db psql -U postgres -d postgres

# Query grants
SELECT 
  g.grant_id,
  g.debate_id,
  g.source_debate_id,
  d_src.title AS source_title,
  g.scope,
  g.granted_at
FROM debate_memory_grants g
LEFT JOIN debates d_src ON g.source_debate_id = d_src.debate_id
WHERE g.debate_id = '<new_debate_id>';
```

### 5. Verify Grant Immutability (Start Debate)

1. In the web UI, navigate to `/room?debate_id=<new_debate_id>`
2. Click "Start Debate"
3. Try to revoke the grant via API:

```bash
GRANT_ID="<grant_id_from_step_4>"

curl -X DELETE http://localhost:8000/debates/${DEBATE_ID}/memory/grants/${GRANT_ID}
```

**Expected**: `400 Bad Request` - "Cannot revoke grants after debate has started"

This proves audit integrity: grants are immutable once the debate is running.

### 6. Verify Retrieval Enforcement (Optional)

This requires agent preflight to be implemented. For now, you can test the enforcement hook directly:

```python
# In Python REPL
from src.services.memory_retrieval import retrieve_allowed_chunks

# Get participant_id from participants table
result = retrieve_allowed_chunks(
    debate_id="<new_debate_id>",
    participant_id="<participant_id>",
    query="strategy roadmap",
    top_k=5
)

print(f"Total chunks: {result.total_chunks}")
print(f"Grants used: {result.grant_ids_used}")
print(f"Chunks: {[c.chunk_text[:50] for c in result.chunks]}")
```

**Expected**: Chunks from both current debate materials AND imported source debate.

---

## Troubleshooting

**Problem**: "No past meetings available to import"
- **Fix**: Create and complete at least one debate first (see Step 2)

**Problem**: Memory import fails with "Failed to import memory"
- **Check**: API logs for detailed error
- **Common causes**:
  - Source debate not in "ended" state
  - Database connection issues
  - Invalid debate_id

**Problem**: Setup page doesn't show Memory Import step
- **Fix**: Clear browser cache, refresh page
- **Verify**: Step 4 labeled "Memory" should appear after "Participants"

**Problem**: Grants list is empty after creation
- **Check**: API response status (should be 200)
- **Verify**: Database has grants (see Step 4 DB query)
- **Possible**: Debate setup succeeded but import silently failed (check API logs)

---

## Success Criteria

✅ Can toggle Memory Import ON/OFF in setup  
✅ Can select past meetings from list  
✅ Can choose scope (all vs specific participants)  
✅ Can see preview of what will be imported  
✅ Debate creation succeeds with grants  
✅ Grants appear in database  
✅ Grants list API returns expected data  
✅ Cannot revoke grants after debate starts  
✅ No errors in API or web console  

---

## Next Steps (Out of Scope for V1)

- **Specific Participants Mapping**: Currently only "all_agents" scope is fully supported. Mapping selected participant indices to actual participant_ids requires backend enhancement to return participant_ids from setup.
- **Vector Search**: Upgrade keyword scoring to pgvector embeddings for semantic retrieval.
- **Artifact Grants**: Support importing from specific artifacts once artifact schema exists.
- **Grant Analytics**: Dashboard showing grant usage patterns and retrieval audit logs.

---

**Demo Complete!** Memory Import V1 is functional and audit-compliant.
