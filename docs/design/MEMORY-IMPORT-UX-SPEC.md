# Memory Import UX - Technical Specification

**Date:** 2026-02-09  
**Status:** Draft (Ready for Engineering Review)  
**Authority:** `/docs/design/DECISIONS-SOURCE-OF-TRUTH-2026-02-09.md`  
**Related:** `/docs/product/MEETING-FLOW-MEMORY-ARTIFACTS.md`

---

## Executive Summary

Memory Import enables users to explicitly share context from prior meetings with agents in new debates. This is NOT global memory—it's user-controlled, scoped, and auditable. Users can choose which prior meetings/artifacts to import and which agents can access them.

**Core Principle**: No agent can access prior context unless explicitly granted by user.

---

## Table of Contents

1. [Product Vision](#product-vision)
2. [Data Model](#data-model)
3. [Setup UI Flow](#setup-ui-flow)
4. [Enforcement Rules](#enforcement-rules)
5. [Audit & Observability](#audit--observability)
6. [Edge Cases](#edge-cases)
7. [Non-Goals](#non-goals)

---

## Product Vision

### User Story

```
As an enterprise user running multiple related debates,
I want to import context from prior meetings
So that agents can build on previous discussions instead of starting from scratch.

Example:
- Week 1: "Q1 Strategy" debate produces artifact
- Week 2: "Q1 Budget" debate
  → User imports "Q1 Strategy" artifact
  → Agents can reference strategy decisions
  → Continuity across meetings
```

### Key Requirements

1. **Explicit Import** (Not Automatic)
   - User explicitly enables memory import
   - Default: Each debate is isolated

2. **Granular Scoping**
   - User chooses: All agents OR specific agents
   - Example: Import legal context for Legal Counsel only

3. **Transparent Preview**
   - User sees exactly what will be imported before enabling
   - Topics, chunk count, last updated date

4. **Auditable**
   - Every retrieval is logged
   - Compliance can trace "why did agent know X?"

---

## Data Model

### Join Table: `debate_memory_grants`

Per DECISIONS doc: Use relational join table (not policy_config JSONB).

```sql
CREATE TABLE debate_memory_grants (
    grant_id UUID PRIMARY KEY,
    debate_id UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    source_debate_id UUID REFERENCES debates(debate_id) ON DELETE CASCADE,
    source_artifact_id UUID,  -- If importing artifact specifically
    source_type VARCHAR(50) NOT NULL,  -- 'debate_full', 'artifact', 'materials_only'
    scope VARCHAR(50) NOT NULL,  -- 'all_agents', 'specific_agents'
    allowed_participant_ids UUID[],  -- If scope='specific_agents'
    granted_by VARCHAR(100) NOT NULL,  -- 'user_id' or 'operator'
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,  -- Optional: time-bound access
    metadata JSONB,  -- Import context (why, what topics)
    
    CONSTRAINT valid_scope CHECK (
        (scope = 'all_agents' AND allowed_participant_ids IS NULL) OR
        (scope = 'specific_agents' AND allowed_participant_ids IS NOT NULL)
    )
);

CREATE INDEX idx_memory_grants_debate ON debate_memory_grants(debate_id);
CREATE INDEX idx_memory_grants_source ON debate_memory_grants(source_debate_id);
CREATE INDEX idx_memory_grants_artifact ON debate_memory_grants(source_artifact_id);
```

---

### Query Patterns

#### **Check if Agent Has Access to Memory**
```sql
-- Does participant_123 in debate_456 have access to source_debate_789?
SELECT EXISTS (
    SELECT 1 FROM debate_memory_grants
    WHERE debate_id = 'debate_456'
      AND source_debate_id = 'source_debate_789'
      AND (
          scope = 'all_agents' 
          OR 'participant_123' = ANY(allowed_participant_ids)
      )
);
```

#### **List All Memory Grants for Debate**
```sql
SELECT 
    g.grant_id,
    g.source_type,
    g.scope,
    d.title AS source_debate_title,
    a.title AS source_artifact_title,
    g.granted_at
FROM debate_memory_grants g
LEFT JOIN debates d ON g.source_debate_id = d.debate_id
LEFT JOIN artifacts a ON g.source_artifact_id = a.artifact_id
WHERE g.debate_id = 'current_debate_id';
```

#### **Audit Trail: Who Accessed What**
```sql
-- NOTE: The current repo's memory_access_log is minimal (query_text/results_count only).
-- For Memory Import auditing we extend it (no new table) to record which chunks were returned.
--
-- Required migration (V1):
--   ALTER TABLE memory_access_log ADD COLUMN IF NOT EXISTS chunk_ids UUID[];
--   ALTER TABLE memory_access_log ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';
--
-- Then we can produce a compliance-grade audit view:
SELECT
    mal.agent_id,
    mal.debate_id,
    mal.access_type,
    mal.query_text,
    mal.results_count,
    mal.created_at AS accessed_at,
    cid AS chunk_id,
    mc.source_debate_id,
    mc.chunk_metadata->>'material_id' AS material_id,
    g.grant_id,
    g.source_type
FROM memory_access_log mal
LEFT JOIN LATERAL unnest(mal.chunk_ids) AS cid ON true
LEFT JOIN memory_chunks mc ON mc.chunk_id = cid
LEFT JOIN debate_memory_grants g ON g.source_debate_id = mc.source_debate_id
WHERE mal.debate_id = 'current_debate_id'
ORDER BY mal.created_at DESC;
```

---

## Setup UI Flow

### Step 4.5: Memory Import (Optional Step in Setup Wizard)

**Placement**: After participants selected, before launch.

**UI Wireframe**:

```
┌──────────────────────────────────────────────────────────────┐
│  Step 4: Memory Import (Optional)                            │
│                                                               │
│  Enable agents to reference prior meeting context            │
│                                                               │
│  [Toggle: OFF] Import Context from Prior Meetings            │
│                                                               │
│  (If toggle ON, show below)                                  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Select Sources                                        │ │
│  │                                                        │ │
│  │  Recent Debates in Workspace:                          │ │
│  │                                                        │ │
│  │  ☑ Q1 Strategy Discussion                             │ │
│  │    • 5 agents, 3 artifacts                            │ │
│  │    • 12 materials (Legal, Product, Financial)         │ │
│  │    • Last updated: 2026-02-01                         │ │
│  │    Import: [Artifacts Only ▼] [All Agents ▼]         │ │
│  │                                                        │ │
│  │  ☐ Q4 Retrospective                                   │ │
│  │    • 3 agents, 1 artifact                             │ │
│  │    • 5 materials (Product)                            │ │
│  │    • Last updated: 2025-12-20                         │ │
│  │                                                        │ │
│  │  [Search Older Debates...]                            │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Preview: What Will Be Imported                        │ │
│  │                                                        │ │
│  │  From: Q1 Strategy Discussion                          │ │
│  │  • 3 finalized artifacts (Brief, PRD, Risk Memo)      │ │
│  │  • 47 knowledge chunks                                │ │
│  │  • Topics: Market positioning, Revenue model, Legal   │ │
│  │                                                        │ │
│  │  Shared With:                                          │ │
│  │  ✅ All 5 agents in this panel                        │ │
│  │                                                        │ │
│  │  [Change Scope] → Select specific agents              │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│  ⚠ Agents will see this context during preparation and     │
│    debate. This cannot be revoked after the debate starts.  │
│                                                               │
│  [< Previous]                              [Next: Review >]  │
└──────────────────────────────────────────────────────────────┘
```

---

### Scope Selection UI

**When User Clicks "Change Scope"**:

```
┌──────────────────────────────────────────────────────────────┐
│  Scope Memory Import: Q1 Strategy Discussion                 │
│                                                               │
│  Who can access this context?                                │
│                                                               │
│  ○ All agents in this panel (default)                        │
│  ● Selected agents only                                      │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Select Agents:                                        │ │
│  │                                                        │ │
│  │  ☑ Senior PM (Visionary)                              │ │
│  │  ☑ Legal Counsel                                      │ │
│  │  ☐ CFO (Analytical)                                   │ │
│  │  ☐ Senior Engineer                                    │ │
│  │  ☐ Designer                                           │ │
│  │                                                        │ │
│  │  2 of 5 selected                                      │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│  Rationale (optional):                                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Only PM and Legal need Q1 strategy context            │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│  [Cancel]                                    [Apply Scope]   │
└──────────────────────────────────────────────────────────────┘
```

---

## API Contracts

### **GET /debates/importable**
List debates that can be imported as memory sources.

**Query Params**:
- `workspace_id`: Current workspace
- `exclude_debate_id`: Don't show current debate
- `limit`: Max results (default 20)

**Response** (200):
```json
{
  "debates": [
    {
      "debate_id": "uuid",
      "title": "Q1 Strategy Discussion",
      "ended_at": "2026-02-01T18:00:00Z",
      "artifact_count": 3,
      "material_count": 12,
      "participant_count": 5,
      "topics": ["Market positioning", "Revenue model", "Legal risks"],
      "total_chunks": 47
    },
    {
      "debate_id": "uuid",
      "title": "Q4 Retrospective",
      "ended_at": "2025-12-20T16:30:00Z",
      "artifact_count": 1,
      "material_count": 5,
      "participant_count": 3,
      "topics": ["Performance", "Team health"],
      "total_chunks": 23
    }
  ],
  "total": 15
}
```

---

### **POST /debates/{debate_id}/memory/import**
Create memory grants for current debate.

**Request**:
```json
{
  "grants": [
    {
      "source_debate_id": "uuid",
      "source_type": "artifact",  // 'debate_full', 'artifact', 'materials_only'
      "source_artifact_id": "uuid",  // Required if source_type='artifact'
      "scope": "specific_agents",  // 'all_agents' or 'specific_agents'
      "allowed_participant_ids": ["uuid1", "uuid2"]
    },
    {
      "source_debate_id": "uuid2",
      "source_type": "debate_full",
      "scope": "all_agents"
    }
  ]
}
```

**Response** (201):
```json
{
  "grant_ids": ["uuid1", "uuid2"],
  "total_chunks_imported": 70,
  "affected_agents": ["uuid1", "uuid2", "uuid3", "uuid4", "uuid5"]
}
```

---

### **GET /debates/{debate_id}/memory/grants**
List active memory grants for current debate.

**Response** (200):
```json
{
  "grants": [
    {
      "grant_id": "uuid",
      "source_debate_title": "Q1 Strategy Discussion",
      "source_type": "artifact",
      "source_artifact_title": "Executive Brief",
      "scope": "specific_agents",
      "allowed_agents": [
        {"participant_id": "uuid", "name": "Senior PM"},
        {"participant_id": "uuid", "name": "Legal Counsel"}
      ],
      "granted_at": "2026-02-09T19:00:00Z",
      "chunk_count": 15
    }
  ],
  "total_grants": 1,
  "total_chunks_accessible": 15
}
```

---

### **DELETE /debates/{debate_id}/memory/grants/{grant_id}**
Revoke memory grant (before debate starts only).

**Response** (200):
```json
{
  "grant_id": "uuid",
  "revoked_at": "2026-02-09T19:30:00Z"
}
```

**Constraint**: Can only revoke grants if debate state = 'pending' or 'materials_processing'.

---

## Enforcement Rules

### Retrieval Allowlist

When agent requests context during preparation or debate:

```python
# apps/api/src/services/memory_service.py

class MemoryService:
    async def retrieve_for_agent(
        self,
        debate_id: str,
        participant_id: str,
        query: str,
        top_k: int = 10
    ) -> List[Chunk]:
        """Retrieve chunks respecting memory grants"""
        
        # 1. Get allowed source debates for this participant
        allowed_sources = await self._get_allowed_sources(debate_id, participant_id)
        
        # 2. Generate query embedding
        query_embedding = await generate_embedding(query)
        
        # 3. Vector search with source filter
        chunks = await vector_search(
            embedding=query_embedding,
            filters={
                "source_debate_id": allowed_sources,  # Only search allowed sources
                "debate_id": debate_id  # Include current debate materials
            },
            top_k=top_k
        )
        
        # 4. Log access for audit
        for chunk in chunks:
            await log_access(
                debate_id=debate_id,
                agent_id=participant_id,
                chunk_id=chunk.chunk_id,
                query=query
            )
        
        return chunks
    
    async def _get_allowed_sources(
        self,
        debate_id: str,
        participant_id: str
    ) -> List[str]:
        """Get list of debate IDs this participant can access"""
        
        # Query debate_memory_grants
        grants = db.execute("""
            SELECT DISTINCT source_debate_id
            FROM debate_memory_grants
            WHERE debate_id = %s
              AND (
                  scope = 'all_agents'
                  OR %s = ANY(allowed_participant_ids)
              )
        """, [debate_id, participant_id])
        
        source_ids = [g['source_debate_id'] for g in grants]
        
        # Always include current debate (agent can access current materials)
        source_ids.append(debate_id)
        
        return source_ids
```

---

### Chunk Source Filtering

Memory chunks must indicate their source:

```sql
-- Filter during vector search
SELECT 
    chunk_id,
    content,
    embedding,
    chunk_metadata
FROM memory_chunks
WHERE 
    -- Source filtering
    source_debate_id = ANY(%s)  -- Allowed debate IDs
    
    -- Vector similarity
    AND embedding <-> %s < 0.3  -- Cosine distance threshold
    
ORDER BY embedding <-> %s
LIMIT %s;
```

---

## Setup UI Flow

### Integration in Setup Wizard

**Current Flow**:
1. Basic info (title, problem, agenda)
2. Materials
3. Participants
4. **[NEW] Memory Import** ← Insert here
5. Review & Launch

### Step 4: Memory Import Screen

**Default State**: Toggle OFF

```
┌──────────────────────────────────────────────────────────────┐
│  Memory Import                                                │
│                                                               │
│  [Toggle: OFF] Enable Context from Prior Meetings            │
│                                                               │
│  By default, each debate starts fresh. Enable this to allow  │
│  agents to reference prior discussions.                       │
│                                                               │
│  [< Previous: Participants]           [Next: Review >]        │
└──────────────────────────────────────────────────────────────┘
```

**When Toggle ON**:

```
┌──────────────────────────────────────────────────────────────┐
│  Memory Import                                                │
│                                                               │
│  [Toggle: ON] Enable Context from Prior Meetings             │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Select Sources to Import                              │ │
│  │                                                        │ │
│  │  Search: [________________] [🔍]                       │ │
│  │                                                        │ │
│  │  Recent Debates (Last 30 Days):                        │ │
│  │                                                        │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │ ☑ Q1 Strategy Discussion              2026-02-01 │ │ │
│  │  │   Ended · 5 agents · 3 artifacts                 │ │ │
│  │  │                                                  │ │ │
│  │  │   Import Type: [Artifacts Only ▼]               │ │ │
│  │  │   Share With: [All Agents ▼]                    │ │ │
│  │  │                                                  │ │ │
│  │  │   📊 Preview: 47 chunks, 3 topics                │ │ │
│  │  │   Topics: Market positioning, Revenue, Legal     │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │                                                        │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │ ☐ Feature X Design Review              2026-01-15│ │ │
│  │  │   Ended · 3 agents · 1 artifact                  │ │ │
│  │  │                                                  │ │ │
│  │  │   [Select to Import]                             │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │                                                        │ │
│  │  ☐ Show Archived Debates (>90 days)                   │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Import Summary                                        │ │
│  │                                                        │ │
│  │  • 1 debate selected                                   │ │
│  │  • 47 knowledge chunks                                 │ │
│  │  • Accessible to: All 5 agents                        │ │
│  │                                                        │ │
│  │  ⚠ This context cannot be revoked after debate starts │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│  [< Previous]                              [Next: Review >]  │
└──────────────────────────────────────────────────────────────┘
```

---

### Import Type Dropdown

**Options**:
1. **Artifacts Only** (Recommended)
   - Import finalized artifacts (PRDs, briefs, memos)
   - Does NOT import raw materials or interim events
   - Cleanest signal (expert-reviewed output)

2. **Full Context**
   - Artifacts + materials + significant events
   - Higher volume, more noise
   - Use case: Deep continuity needed

3. **Materials Only**
   - Import original materials (PDFs, links, text)
   - Does NOT import debate outputs
   - Use case: Same documents, different discussion

---

### Share With Dropdown

**Options**:
1. **All Agents** (Default)
   - Every agent in current panel can access
   - Simplest, most common case

2. **Selected Agents**
   - Opens agent picker
   - User checks which agents get access
   - Example: Import legal context for Legal Counsel only

---

## Enforcement Rules

### Rule 1: Grant Validation

Before allowing retrieval:
```python
def can_access_chunk(
    debate_id: str,
    participant_id: str,
    chunk: Chunk
) -> bool:
    """Check if participant has access to this chunk"""
    
    # Always allow current debate's own content
    if chunk.source_debate_id == debate_id:
        return True
    
    # Check memory grants
    grant = db.query("""
        SELECT 1 FROM debate_memory_grants
        WHERE debate_id = %s
          AND source_debate_id = %s
          AND (
              scope = 'all_agents'
              OR %s = ANY(allowed_participant_ids)
          )
        LIMIT 1
    """, [debate_id, chunk.source_debate_id, participant_id])
    
    return grant is not None
```

---

### Rule 2: Immutable After Start

Once debate state transitions to 'running':
- Memory grants CANNOT be added or revoked
- DELETE /memory/grants returns 400 "Cannot revoke after debate started"

**Rationale**: Agents make decisions based on available context. Revoking mid-debate would be confusing.

---

### Rule 3: Audit Every Retrieval

```python
async def log_memory_access(
    debate_id: str,
    agent_id: str,
    chunk_ids: list[str],
    query: str,
    source_type: str
):
    """Log to memory_access_log (existing table)"""
    db.insert("memory_access_log", {
        "debate_id": debate_id,
        "agent_id": agent_id,
        "chunk_ids": chunk_ids,
        "query_text": query,
        "results_count": len(chunk_ids),
        "metadata": {
            "query": query,
            "source_type": source_type,
            "grant_id": "uuid"  # Links to debate_memory_grants
        }
    })
```

---

## Preview Generation

### GET /debates/{debate_id}/memory/preview

Generate "what will be imported" preview.

**Request Query Params**:
- `source_debate_id`: UUID
- `source_type`: artifact | debate_full | materials_only

**Response**:
```json
{
  "source_debate_id": "uuid",
  "source_debate_title": "Q1 Strategy Discussion",
  "source_type": "artifact",
  "preview": {
    "chunk_count": 47,
    "artifact_titles": ["Executive Brief", "Product Roadmap", "Risk Assessment"],
    "material_titles": [],  // Empty for artifact-only import
    "topics": [
      {"topic": "Market positioning", "chunk_count": 12},
      {"topic": "Revenue model", "chunk_count": 18},
      {"topic": "Legal compliance", "chunk_count": 17}
    ],
    "date_range": {
      "oldest": "2026-01-15T10:00:00Z",
      "newest": "2026-02-01T18:00:00Z"
    }
  }
}
```

**Implementation**:
```python
async def generate_import_preview(
    source_debate_id: str,
    source_type: str
) -> Dict:
    """Generate preview by analyzing chunks"""
    
    # Get chunks based on source_type
    if source_type == "artifact":
        chunks = get_chunks_from_artifacts(source_debate_id)
    elif source_type == "materials_only":
        chunks = get_chunks_from_materials(source_debate_id)
    else:  # debate_full
        chunks = get_all_chunks(source_debate_id)
    
    # Extract topics (use LLM or keyword extraction)
    topics = await extract_topics(chunks)
    
    return {
        "chunk_count": len(chunks),
        "topics": topics,
        "date_range": {
            "oldest": min(c.created_at for c in chunks),
            "newest": max(c.updated_at for c in chunks)
        }
    }
```

---

## Audit & Observability

### Audit UI (In Room or Settings)

**View Memory Access Log**:

```
┌──────────────────────────────────────────────────────────────┐
│  Memory Access Audit                                          │
│                                                               │
│  Debate: Q1 Budget Planning                                  │
│  Memory Grants: 1 active                                     │
│                                                               │
│  Access Log (Last 50):                                       │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 20:15:30 · CFO (Analytical)                            │ │
│  │ Retrieved: "Revenue projections Q4"                    │ │
│  │ Source: Q1 Strategy Discussion > Financial Model       │ │
│  │ Chunk ID: abc123                                       │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 20:14:15 · Senior PM                                   │ │
│  │ Retrieved: "Market positioning strategy"               │ │
│  │ Source: Q1 Strategy Discussion > Executive Brief       │ │
│  │ Chunk ID: def456                                       │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│  [Export Audit Log]                         [Filter by Agent]│
└──────────────────────────────────────────────────────────────┘
```

---

### Compliance Report Export

**GET /debates/{debate_id}/memory/audit/export**

**Response**: CSV file with columns:
- timestamp
- agent_name
- chunk_id
- source_debate_title
- source_material_title
- query_used
- grant_id

---

## Edge Cases

### Edge Case 1: Source Debate Deleted
**Scenario**: User imports context from debate A, then debate A is deleted.

**Handling**:
- **Soft delete debates** (mark as deleted, don't remove rows)
- Memory grants remain valid (chunks still accessible)
- UI shows: "Source: Q1 Strategy (Archived)"

**Alternative**: Hard delete breaks grant
- Grant query returns NULL for source_debate_id
- Retrieval skips that source
- UI shows warning: "Imported context no longer available"

**Decision**: Implement soft delete for debates with memory grants.

---

### Edge Case 2: User Revokes Permissions Mid-Debate
**Scenario**: User tries to DELETE memory grant after debate started.

**Handling**:
- Return 400 Bad Request: "Cannot revoke memory grants after debate starts"
- Enforce at API level (check debate state before allowing DELETE)

---

### Edge Case 3: Circular Memory References
**Scenario**: Debate A imports from Debate B, Debate B imports from Debate A.

**Handling**:
- Allow it (not technically a problem)
- Retrieval doesn't traverse grants (no recursive imports)
- Each grant is direct: "This debate can see that debate's chunks"

---

### Edge Case 4: Importing from Failed/Incomplete Debates
**Scenario**: Source debate ended without generating artifacts.

**Handling**:
- Allow import (raw materials and events still valuable)
- Preview shows: "0 artifacts, 12 materials"
- User decides if useful

---

### Edge Case 5: Agent Not Present in Source Debate
**Scenario**: Import "Q1 Strategy" for Legal Counsel, but Legal Counsel wasn't in Q1 Strategy.

**Handling**:
- Allow it (context is still useful)
- Legal Counsel can access any granted chunks from Q1 Strategy
- No restriction based on "who participated in source"

---

### Edge Case 6: Source Debate in Different Workspace
**Scenario**: User tries to import from debate in Workspace A while current debate is in Workspace B.

**Handling**:
- **Block at API level**: Return 403 Forbidden
- Reason: Cross-workspace context sharing is a security concern
- UI: Only show debates from current workspace in import picker

---

## Failure Modes

### Failure 1: Source Not Found
**Cause**: source_debate_id doesn't exist or user lacks access.

**Response** (404):
```json
{
  "error": "source_not_found",
  "detail": "Debate uuid not found or access denied"
}
```

---

### Failure 2: Participant Not in Current Debate
**Cause**: User tries to scope grant to participant_id that doesn't belong to current debate.

**Response** (400):
```json
{
  "error": "invalid_participant",
  "detail": "Participant uuid is not in this debate"
}
```

---

### Failure 3: Grant Already Exists
**Cause**: User tries to import same source twice.

**Response** (409):
```json
{
  "error": "grant_exists",
  "detail": "Memory grant for this source already exists",
  "existing_grant_id": "uuid"
}
```

**Alternative**: Allow duplicates, deduplicate at retrieval time.

---

## Non-Goals (V1)

### Explicitly Not Included

1. **Cross-Workspace Memory Import**
   - V1: Only import from same workspace
   - V2: Admin can enable cross-workspace with explicit approval

2. **Automatic Memory Suggestions**
   - V1: User manually selects sources
   - V2: AI suggests "You might want to import Q1 Strategy"

3. **Memory Compression/Summarization**
   - V1: Import raw chunks as-is
   - V2: AI summarizes imported context to reduce token usage

4. **Time-Based Memory Decay**
   - V1: Imported context never expires during debate
   - V2: Older context can be weighted lower in retrieval

5. **Memory Conflicts/Contradictions**
   - V1: Agent must handle if current materials contradict imported memory
   - V2: System detects and flags conflicts

6. **Granular Source Selection**
   - V1: Import entire debate/artifact (all chunks)
   - V2: User can select specific sections/topics to import

---

## Backend Service Structure

```python
# apps/api/src/services/memory_import_service.py

class MemoryImportService:
    async def create_grants(
        self,
        debate_id: str,
        grants: List[GrantRequest],
        granted_by: str
    ) -> List[str]:
        """Create memory grants for debate"""
        
        # Validate debate state
        debate = get_debate(debate_id)
        if debate.state not in ['pending', 'materials_processing']:
            raise ValueError("Cannot add grants after debate starts")
        
        # Validate sources exist and user has access
        for grant in grants:
            self._validate_source(grant.source_debate_id)
            if grant.source_artifact_id:
                self._validate_artifact(grant.source_artifact_id)
        
        # Create grants
        grant_ids = []
        for grant in grants:
            grant_id = db.insert("debate_memory_grants", {
                "grant_id": uuid4(),
                "debate_id": debate_id,
                "source_debate_id": grant.source_debate_id,
                "source_artifact_id": grant.source_artifact_id,
                "source_type": grant.source_type,
                "scope": grant.scope,
                "allowed_participant_ids": grant.allowed_participant_ids,
                "granted_by": granted_by,
                "granted_at": datetime.utcnow()
            })
            grant_ids.append(grant_id)
        
        return grant_ids
    
    async def list_importable_debates(
        self,
        workspace_id: str,
        exclude_debate_id: str
    ) -> List[Dict]:
        """List debates that can be imported"""
        
        debates = db.query("""
            SELECT 
                d.debate_id,
                d.title,
                d.ended_at,
                COUNT(DISTINCT a.artifact_id) AS artifact_count,
                COUNT(DISTINCT m.material_id) AS material_count,
                COUNT(DISTINCT p.participant_id) AS participant_count
            FROM debates d
            LEFT JOIN artifacts a ON d.debate_id = a.debate_id
            LEFT JOIN meeting_materials m ON d.debate_id = m.debate_id
            LEFT JOIN participants p ON d.debate_id = p.debate_id
            WHERE d.workspace_id = %s
              AND d.debate_id != %s
              AND d.state = 'ended'
              AND d.ended_at > NOW() - INTERVAL '90 days'
            GROUP BY d.debate_id
            ORDER BY d.ended_at DESC
            LIMIT 20
        """, [workspace_id, exclude_debate_id])
        
        # Enrich with topics preview
        for debate in debates:
            debate['topics'] = await self._extract_topics(debate['debate_id'])
        
        return debates
    
    async def generate_preview(
        self,
        source_debate_id: str,
        source_type: str
    ) -> Dict:
        """Generate import preview"""
        
        # Get relevant chunks
        if source_type == "artifact":
            chunks = self._get_artifact_chunks(source_debate_id)
        elif source_type == "materials_only":
            chunks = self._get_material_chunks(source_debate_id)
        else:
            chunks = self._get_all_chunks(source_debate_id)
        
        # Extract topics (simple keyword extraction or LLM)
        topics = await self._extract_topics_from_chunks(chunks)
        
        return {
            "chunk_count": len(chunks),
            "topics": topics,
            "date_range": {
                "oldest": min(c.created_at for c in chunks),
                "newest": max(c.updated_at for c in chunks)
            }
        }
```

---

## Acceptance Criteria

### User Can:
- ✅ Enable/disable memory import in setup wizard
- ✅ Search and select prior debates to import
- ✅ Preview what will be imported (chunks, topics, dates)
- ✅ Choose import type (artifacts, full context, materials only)
- ✅ Scope to all agents or specific agents
- ✅ See import summary before launching debate
- ✅ View memory grants in room (which sources are active)
- ✅ Export audit log showing which agents accessed what

### System Ensures:
- ✅ Agents can only retrieve chunks from granted sources
- ✅ Every retrieval is logged with timestamp, agent, query, source
- ✅ Grants cannot be revoked after debate starts
- ✅ Cross-workspace imports are blocked
- ✅ Deleted source debates are handled gracefully (soft delete)
- ✅ Preview is accurate (matches actual imported chunks)

### Technical Bars:
- ✅ Join table queries <50ms for typical grants (3-5 sources)
- ✅ Retrieval respects grants without performance penalty
- ✅ Audit log can be exported for compliance
- ✅ UI shows clear "why agent knows X" provenance

---

## Success Metrics

| Metric | Target | Why |
|--------|--------|-----|
| % debates using memory import | >30% | Feature adoption |
| Avg sources imported | 1-2 | Not overwhelming |
| Memory retrieval accuracy | >85% | Agents find relevant context |
| Audit log completeness | 100% | Compliance requirement |
| User understanding (survey) | >4/5 | "I understand what was imported" |

---

**Document Status**: Complete, ready for implementation  
**Next Step**: Engineering review and DB migration planning
