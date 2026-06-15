# Agent Preparation Architecture - Design Document

**Date:** 2026-02-09  
**Status:** Design Proposal  
**Author:** Strategic Planning Session  
**Context:** Post-TICKET-09B UI Simplification

**Update (2026-02-10):** Materials ingestion + memory import + preflight core are now implemented (see ticket reports). This doc remains the guiding design, but some “current state gaps” are partially closed.

---

## Executive Summary

This document defines the architecture for **Agent Preparation** - a critical feature that ensures AI agents enter debates fully informed with document context and optional internet research. This transforms debates from "cold start guessing" to "informed expert discussion."

**Core Principle**: Agents must have a complete picture of the problem before debating.

---

## Table of Contents

1. [Product Vision & Flow](#product-vision--flow)
2. [Current State Assessment](#current-state-assessment)
3. [Proposed Architecture](#proposed-architecture)
4. [Implementation Phases](#implementation-phases)
5. [Cost Analysis](#cost-analysis)
6. [Risk Mitigation](#risk-mitigation)
7. [Open Questions](#open-questions)

---

## Product Vision & Flow

### The Ideal User Experience

```
User Journey:

1. SETUP (2-5 min user time)
   ├─ Enter title, problem statement
   ├─ Define agenda and desired outcome
   ├─ Select 2-8 AI agents (mix roles/seniority/characters)
   ├─ Configure each agent (optional)
   └─ Click "Upload Materials & Prepare Panel"

2. MATERIALS INGESTION (30 sec - 3 min automated)
   ├─ User uploads documents (PDF, DOCX, TXT, URLs)
   ├─ AI processes, categorizes, chunks documents
   ├─ Embeds and indexes in vector database
   ├─ Progress bar: "Processing 3/5 documents..."
   └─ Status: "Materials ready" ✅

3. AGENT PREFLIGHT (1-4 min parallel)
   ├─ Each agent reviews relevant materials (by category/role)
   ├─ Optional: Internet research per agent
   ├─ Generate agent-specific "briefing memo"
   ├─ Inject context into agent system prompt
   ├─ Progress bars per agent with retry/skip controls
   └─ Status: "4/5 agents ready" ✅

4. ROOM (Debate runs live)
   ├─ Agents debate with full context
   ├─ Dynamic retrieval during turns
   ├─ Citations back to source materials
   └─ Generate summary with evidence map
```

### Key Product Principles

1. **Complete Picture Over Speed**
   - Agents MUST see uploaded documents before debating
   - Optional research for current information
   - Quality over instant gratification

2. **Transparent Progress**
   - User sees what's happening at each stage
   - Per-agent preparation status
   - Clear time estimates

3. **Graceful Failure Handling**
   - If 1 agent prep fails, others continue
   - User controls: Retry, Skip, or Abort
   - Unprepared agents get fallback context (docs + problem statement)

4. **Enterprise-Grade Reliability**
   - Audit trail of all preparation steps
   - Cost tracking per debate
   - Configurable timeouts and budgets

## RLM-Style Preparation (Long-Context Quality)

Agent preparation must remain high-quality even when meetings include large numbers of documents and imported memory.
We will use an **RLM-style multi-pass approach** (plan -> retrieve slices -> draft notes -> synthesize -> verify), rather than passing all materials into a single prompt.

This approach is:
- compatible with OpenRouter BYOK (works with any model selection)
- enterprise-auditable (every retrieval is explicit and can be logged)
- naturally timeboxable (budgets per pass and per agent)

Reference: `arinar-v2/docs/design/RLM-APPLICATION-TO-ARINAR.md`.

---

## Current State Assessment

### What We Have Today (M1-M2 Complete)

| Component | Status | Notes |
|-----------|--------|-------|
| **Debate Engine** | ✅ Complete | Round-robin, state machine, event ledger |
| **Agent Templates** | ✅ Complete | 10 curated templates with role + character combos |
| **Persistent Agents** | ⚠️ Backend Only | POST/GET /agents exists, NO UI for creation |
| **Materials Table** | ✅ Schema Exists | `meeting_materials` table for metadata |
| **File Upload** | ❌ Not Built | No upload handler, no storage integration |
| **Document Processing** | ❌ Not Built | No parsing, chunking, categorization |
| **Vector Search** | ❌ Not Built | pgvector extension ready but unused |
| **Internet Research** | ❌ Not Built | No API integration |
| **Preparation Phase** | ❌ Not Built | Debate goes directly from setup → running |

### Critical Gaps

**Gap 1: Material Upload & Processing Pipeline** 🔴
- No file upload handler
- No document parsing (PDF/DOCX)
- No AI categorization
- No chunking or embedding generation
- No vector storage or retrieval

**Gap 2: Agent Preparation Orchestration** 🔴
- No preparation phase in state machine
- No material review logic per agent
- No research integration
- No briefing memo generation
- No progress tracking

**Gap 3: Custom Agent Creation UI** 🟡
- Backend exists (POST /agents, GET /agents)
- No UI in Settings page
- Users stuck with 10 preset templates

**Gap 4: Context Injection During Debate** 🟡
- Current: Static system prompt at start
- Needed: Dynamic context retrieval per turn

---

## Proposed Architecture

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    STAGE 1: SETUP                                │
│  User Input: Title, Problem, Agents, Agenda                     │
│  Output: debate_id (state: 'pending')                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              STAGE 2: MATERIALS INGESTION                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Upload Service (FastAPI)                               │   │
│  │  ├─ POST /debates/{id}/materials/upload                 │   │
│  │  ├─ Validate file (size, type, virus scan)              │   │
│  │  └─ Store in MinIO/S3                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Processing Worker (Python/Celery)                      │   │
│  │  ├─ Text extraction (PyPDF2, python-docx, Jina Reader)  │   │
│  │  ├─ AI categorization (GPT-4 via OpenRouter)            │   │
│  │  ├─ Semantic chunking (LangChain or custom)             │   │
│  │  ├─ Embedding generation (text-embedding-3 via OR)      │   │
│  │  └─ Store chunks in pgvector                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  Database Updates:                                              │
│  ├─ meeting_materials: Add processed_status, category          │
│  ├─ memory_chunks: Store chunked text + embeddings (provenance)│
│  └─ debate.state: 'pending' → 'materials_processing'           │
│                                                                  │
│  Progress: WebSocket updates to UI                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              STAGE 3: AGENT PREFLIGHT                            │
│  State: 'materials_ready' → 'preparing_agents'                  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Preparation Orchestrator (Python)                      │   │
│  │  Coordinates parallel agent preparation                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│           ↓          ↓          ↓          ↓          ↓          │
│     Agent 1      Agent 2    Agent 3    Agent 4    Agent 5       │
│  ┌─────────┐  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│  │Review   │  │Review   │ │Review   │ │Review   │ │Review   │ │
│  │Docs     │  │Docs     │ │Docs     │ │Docs     │ │Docs     │ │
│  │(vector) │  │(vector) │ │(vector) │ │(vector) │ │(vector) │ │
│  ├─────────┤  ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤ │
│  │Research │  │Research │ │Research │ │Research │ │Research │ │
│  │Web      │  │Web      │ │Web      │ │Web      │ │Web      │ │
│  │(Perplex)│  │(Perplex)│ │(Perplex)│ │(Perplex)│ │(Perplex)│ │
│  ├─────────┤  ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤ │
│  │Generate │  │Generate │ │Generate │ │Generate │ │Generate │ │
│  │Briefing │  │Briefing │ │Briefing │ │Briefing │ │Briefing │ │
│  └─────────┘  └─────────┘ └─────────┘ └─────────┘ └─────────┘ │
│       ✅           ✅          ❌           ✅          ✅         │
│                                ↓ (retry/skip)                    │
│  All agents ready OR user approves partial readiness            │
│  → debate.state: 'preparing_agents' → 'ready'                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                 STAGE 4: ROOM (Debate Runs)                      │
│  State: 'ready' → 'running'                                     │
│  Agents debate with:                                            │
│  ├─ Prepared context from Stage 3                               │
│  ├─ Dynamic retrieval per turn (vector search)                  │
│  └─ Citation links back to source chunks                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Proposed Architecture

### Database Schema (No Duplicates)

This repo already has a memory fabric and meeting materials metadata. The implementation **must reuse existing tables** and only extend them where necessary.

Existing tables we should build on:
- `meeting_materials` (already exists): meeting-scoped material metadata + inline text/URLs placeholders
- `memory_chunks` (already exists): searchable chunks (currently agent-scoped, but we can extend to support meeting materials)
- `agent_knowledge_units` (already exists): durable "what an agent learned" units (ideal for preflight memos)
- `memory_access_log` (already exists): audit trail for retrieval
- `events` (already exists): immutable ledger for debate timeline and citations

#### **1. Extend `debates` table** (prep progress only)
```sql
ALTER TABLE debates ADD COLUMN preparation_status JSONB;

-- Example value:
{
  "materials_processing": {
    "status": "complete",
    "processed": 5,
    "failed": 0,
    "duration_seconds": 45
  },
  "agent_preparation": {
    "status": "partial_ready",
    "agents": [
      {"agent_id": "...", "status": "ready", "briefing_id": "..."},
      {"agent_id": "...", "status": "failed", "error": "Research timeout"},
      {"agent_id": "...", "status": "ready", "briefing_id": "..."}
    ],
    "duration_seconds": 120
  }
}
```

#### **2. Reuse `memory_chunks` for ingested material chunks** (extend, don’t duplicate)
Instead of creating a new `document_chunks` table, store material chunks in `memory_chunks` with clear provenance.

Recommended minimal extension:
```sql
-- Allow material chunks to exist without being "owned" by a specific agent.
ALTER TABLE memory_chunks ALTER COLUMN agent_id DROP NOT NULL;

-- Add embeddings for vector retrieval (pgvector).
-- Dimension depends on the embedding model chosen.
ALTER TABLE memory_chunks ADD COLUMN IF NOT EXISTS embedding VECTOR(1536);

-- Optional: add a fast filter column (or keep in chunk_metadata).
ALTER TABLE memory_chunks ADD COLUMN IF NOT EXISTS source_type VARCHAR(50);
-- Example values: 'material', 'preflight', 'artifact', 'meeting_event'
```

Provenance lives in `chunk_metadata`, for example:
```json
{
  "source_type": "material",
  "material_id": "…",
  "chunk_index": 12,
  "page_num": 4,
  "section": "Pricing",
  "category": "Legal",
  "sha256": "…"
}
```

Indexes:
```sql
CREATE INDEX IF NOT EXISTS idx_memory_chunks_debate_id ON memory_chunks(source_debate_id);
CREATE INDEX IF NOT EXISTS idx_memory_chunks_source_type ON memory_chunks(source_type);
-- Vector index depends on pgvector strategy (ivfflat/hnsw) and dimension.
```

#### **3. Reuse `agent_knowledge_units` for preflight briefings** (no `agent_briefings` table)
Store each agent’s preflight output as a knowledge unit:
- `content`: the briefing memo text
- `metadata`: citations + chunk IDs + research URLs + budgets used
- `source_debate_id`: the current debate_id (the meeting where briefing was generated)

Example metadata:
```json
{
  "type": "preflight_briefing",
  "participant_id": "…",
  "material_chunk_ids": ["…", "…"],
  "web_citations": [{"url": "…", "retrieved_at": "…"}],
  "policy": {"internet_mode": "limited", "citation_mode": "strict"}
}
```

#### **4. Update `meeting_materials` table**
```sql
ALTER TABLE meeting_materials ADD COLUMN processed_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE meeting_materials ADD COLUMN category VARCHAR(100);  -- 'Legal', 'Product', 'Technical', etc.
ALTER TABLE meeting_materials ADD COLUMN file_key VARCHAR(500);  -- S3/MinIO key
ALTER TABLE meeting_materials ADD COLUMN file_size_bytes INTEGER;
ALTER TABLE meeting_materials ADD COLUMN processing_metadata JSONB;

-- Example processing_metadata:
{
  "page_count": 12,
  "word_count": 3400,
  "chunk_count": 8,
  "extraction_method": "pypdf2",
  "ai_category_confidence": 0.95,
  "processing_duration_seconds": 12
}
```

### Memory Import + Scoping (User-Enabled)
Your product requirement: user can enable prior-meeting context and choose whether to expose it to all agents or only specific agents.

Do not build “global memory”.
Implement an explicit allowlist of knowledge sources per debate, scoped per participant.

V1 (lowest complexity): store allowlists in `debates.policy_config`:
```json
{
  "memory_imports": [
    {
      "source_debate_id": "…",
      "source_type": "artifact",
      "artifact_id": "…",
      "shared_with": "all"  // or list of participant_ids
    }
  ]
}
```

V2 (more queryable): a join table `debate_memory_grants` (not required for initial shipping).

### Live Artifact Drafting (Figma-Like) (Missing In Current Plan)
Your premium requirement: at the end of a debate, agents produce a collaborative artifact where each agent owns sections and users can watch them “type”.

This requires:
- Artifact template (sections)
- Section assignment (owner agent/participant)
- Streaming section deltas (WebSocket events) so the UI can show live drafting
- A “coherence pass” step by a host/moderator agent to unify tone and remove contradictions

Data storage should reuse:
- `events` for streaming deltas (append-only audit)
- `agent_knowledge_units` for finalized section commits (durable, searchable)
- `memory_chunks` for section chunking + retrieval later

Avoid introducing a second document store.

---

## New API Endpoints

### **Materials Endpoints**

```yaml
POST /debates/{debate_id}/materials/upload
  Input: multipart/form-data (files)
  Output: { material_ids: [...], job_id: "..." }
  
GET /debates/{debate_id}/materials/status
  Output: {
    total: 5,
    processed: 3,
    failed: 1,
    processing: 1,
    materials: [
      { material_id, filename, status, category, progress }
    ]
  }

POST /debates/{debate_id}/materials/retry/{material_id}
  Retry failed material processing
```

### **Preparation Endpoints**

```yaml
POST /debates/{debate_id}/prepare
  Triggers agent preparation phase
  Input: { enable_research: true/false }
  Output: { job_id: "...", estimated_duration_seconds: 120 }

GET /debates/{debate_id}/preparation/status
  Output: {
    overall_status: "processing" | "partial_ready" | "ready" | "failed",
    agents: [
      {
        participant_id,
        agent_name,
        status: "ready" | "processing" | "failed",
        progress_percent: 75,
        briefing_preview: "Reviewed 12 chunks, researched 3 topics...",
        error: null | "Research timeout after 60s"
      }
    ],
    actions_available: ["retry_failed", "skip_failed", "abort"]
  }

POST /debates/{debate_id}/preparation/retry
  Input: { participant_ids: [...] }  # Which agents to retry
  
POST /debates/{debate_id}/preparation/skip
  Input: { participant_ids: [...] }  # Start debate without these agents' prep
```

---

## Technical Architecture

### Component Breakdown

#### **1. Document Processing Pipeline** (NEW)

**Tech Stack**:
- **Upload Handler**: FastAPI multipart handler
- **Storage**: MinIO (already in docker-compose) or S3
- **Text Extraction**:
  - PDF: `PyPDF2` or `pdfplumber` (handles tables better)
  - DOCX: `python-docx`
  - TXT: Direct read
  - URL: `Jina AI Reader API` or `requests` + `BeautifulSoup`
- **Job Queue**: Redis + Celery or simple async tasks
- **Chunking**: LangChain `RecursiveCharacterTextSplitter` or custom
- **Embeddings**: OpenRouter `openai/text-embedding-3-small`
- **Vector DB**: pgvector (already available in Supabase)

**Service Structure**:
```python
# apps/api/src/services/document_processor.py

class DocumentProcessor:
    async def process_material(self, material_id: str):
        """Main processing pipeline"""
        # 1. Download from storage
        # 2. Extract text
        # 3. AI categorization
        # 4. Chunk text
        # 5. Generate embeddings
        # 6. Store in pgvector
        # 7. Update material status
        
    async def categorize_document(self, text: str) -> str:
        """Use OpenRouter to categorize: Legal/Product/Technical/Financial"""
        prompt = f"""Categorize this document into ONE category:
        - Legal (contracts, compliance, policies)
        - Product (roadmaps, specs, user research)
        - Technical (architecture, code, systems)
        - Financial (budgets, forecasts, ROI)
        - Strategic (vision, goals, planning)
        - General (other)
        
        Document excerpt:
        {text[:2000]}
        
        Return only the category name."""
        
        # Cost: ~$0.01-0.02 per doc
        
    async def chunk_document(self, text: str) -> List[Dict]:
        """Semantic chunking with overlap"""
        # Use LangChain or custom logic
        # Chunk size: 1000 tokens with 200 token overlap
        # Preserve paragraph boundaries
        
    async def generate_embeddings(self, chunks: List[str]) -> List[List[float]]:
        """Batch embedding generation"""
        # Use OpenRouter: openai/text-embedding-3-small
        # Cost: ~$0.0001 per 1k tokens
```

---

#### **2. Research Service** (NEW)

**Recommended API**: **Perplexity AI**
- Best for: Fact-based research with citations
- Cost: $0.05-0.20 per query
- Returns: Answer + source URLs

**Alternative**: Tavily API, Exa, or custom Google Search

**Service Structure**:
```python
# apps/api/src/services/research_service.py

class ResearchService:
    def __init__(self, perplexity_api_key: str):
        self.client = PerplexityClient(perplexity_api_key)
        
    async def research_for_agent(
        self,
        agent_role: str,
        problem_statement: str,
        focus_areas: List[str]
    ) -> Dict:
        """
        Generate research query tailored to agent role,
        execute search, return structured results with citations.
        """
        query = self._build_query(agent_role, problem_statement, focus_areas)
        
        # Cost: ~$0.05-0.20
        result = await self.client.search(query, model="pplx-70b-online")
        
        return {
            "summary": result["answer"],
            "citations": result["citations"],
            "sources": result["sources"],
            "query_used": query
        }
        
    def _build_query(self, role: str, problem: str, focus: List[str]) -> str:
        """Generate role-specific research query"""
        return f"""
        As a {role}, research the following problem:
        {problem}
        
        Focus on: {', '.join(focus)}
        
        Provide current data, trends, and risks from {role} perspective.
        """
```

**Budget Controls**:
```python
# Per debate limits
MAX_RESEARCH_COST_PER_DEBATE = 1.00  # $1.00
MAX_RESEARCH_QUERIES_PER_AGENT = 2
RESEARCH_TIMEOUT_SECONDS = 60
```

---

#### **3. Preparation Orchestrator** (NEW)

**Service Structure**:
```python
# apps/api/src/services/preparation_orchestrator.py

class PreparationOrchestrator:
    """Coordinates parallel agent preparation"""
    
    async def prepare_all_agents(
        self,
        debate_id: str,
        enable_research: bool = False
    ) -> Dict:
        """
        Prepare all agents in parallel.
        Returns status dict with per-agent results.
        """
        debate = get_debate(debate_id)
        participants = get_participants(debate_id)
        materials = get_materials(debate_id)
        
        # Update state
        update_debate_state(debate_id, 'preparing_agents')
        
        # Prepare all agents in parallel
        tasks = [
            self._prepare_single_agent(
                debate_id, 
                participant, 
                materials, 
                enable_research
            )
            for participant in participants
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate results
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        
        if success_count >= len(participants) * 0.5:  # At least 50% ready
            update_debate_state(debate_id, 'ready')
        else:
            update_debate_state(debate_id, 'preparation_failed')
            
        return {
            "overall_status": "ready" if success_count == len(participants) else "partial_ready",
            "agent_results": results
        }
        
    async def _prepare_single_agent(
        self,
        debate_id: str,
        participant: Dict,
        materials: List[Dict],
        enable_research: bool
    ) -> Dict:
        """Prepare one agent"""
        try:
            # Step 1: Retrieve relevant materials (vector search)
            relevant_chunks = await self._retrieve_materials(
                debate_id,
                participant["role_description"],
                participant.get("agent_config", {}).get("category")
            )
            
            # Step 2: Internet research (optional)
            research_results = None
            if enable_research:
                research_results = await self._research_for_agent(
                    participant,
                    debate_id
                )
            
            # Step 3: Generate briefing memo
            briefing = await self._generate_briefing(
                participant,
                relevant_chunks,
                research_results
            )
            
            # Step 4: Store briefing
            briefing_id = save_briefing(
                debate_id,
                participant["participant_id"],
                briefing,
                relevant_chunks,
                research_results
            )
            
            # Step 5: Update participant with enriched context
            update_participant_context(
                participant["participant_id"],
                briefing
            )
            
            return {
                "participant_id": participant["participant_id"],
                "status": "ready",
                "briefing_id": briefing_id,
                "chunks_reviewed": len(relevant_chunks),
                "research_executed": enable_research
            }
            
        except Exception as e:
            return {
                "participant_id": participant["participant_id"],
                "status": "failed",
                "error": str(e)
            }
    
    async def _retrieve_materials(
        self,
        debate_id: str,
        agent_role: str,
        category_filter: Optional[str] = None
    ) -> List[Dict]:
        """Vector search for relevant chunks"""
        # Generate query embedding
        query = f"Documents relevant to {agent_role} for this discussion"
        query_embedding = await generate_embedding(query)
        
        # Vector similarity search
        chunks = vector_search(
            debate_id=debate_id,
            embedding=query_embedding,
            category=category_filter,
            top_k=15
        )
        
        return chunks
        
    async def _research_for_agent(
        self,
        participant: Dict,
        debate_id: str
    ) -> Dict:
        """Execute internet research"""
        debate = get_debate(debate_id)
        problem = debate["policy_config"]["problem_statement"]
        
        research_service = ResearchService(os.getenv("PERPLEXITY_API_KEY"))
        
        results = await research_service.research_for_agent(
            agent_role=participant["role_description"],
            problem_statement=problem,
            focus_areas=[]  # Could be derived from materials
        )
        
        return results
        
    async def _generate_briefing(
        self,
        participant: Dict,
        chunks: List[Dict],
        research: Optional[Dict]
    ) -> str:
        """Generate agent briefing memo"""
        materials_summary = "\n\n".join([
            f"[Document {i+1}]: {chunk['text'][:500]}..."
            for i, chunk in enumerate(chunks[:10])
        ])
        
        research_summary = ""
        if research:
            research_summary = f"\n\nInternet Research:\n{research['summary']}"
        
        prompt = f"""Generate a concise briefing memo for this agent:

Role: {participant['role_description']}

Materials Reviewed:
{materials_summary}
{research_summary}

Create a 200-300 word memo summarizing key points this agent should know.
"""
        
        # Call OpenRouter for memo generation
        # Cost: ~$0.02-0.05
        response = await openrouter_client.complete(prompt)
        
        return response
```

---

### **Progress Tracking System**

**Real-time Updates via WebSocket**:
```python
# apps/api/src/services/progress_tracker.py

class ProgressTracker:
    """Broadcast preparation progress to UI"""
    
    async def update_material_progress(self, debate_id: str, material_id: str, status: str):
        """Update material processing status"""
        await broadcast_to_room(debate_id, {
            "type": "material_progress",
            "material_id": material_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    async def update_agent_progress(
        self,
        debate_id: str,
        participant_id: str,
        step: str,  # 'reviewing_docs', 'researching', 'generating_briefing', 'ready'
        progress_percent: int
    ):
        """Update agent preparation progress"""
        await broadcast_to_room(debate_id, {
            "type": "agent_progress",
            "participant_id": participant_id,
            "step": step,
            "progress": progress_percent,
            "timestamp": datetime.utcnow().isoformat()
        })
```

---

### **New UI Components**

#### **Component 1: Material Processing Progress**
```tsx
// apps/web/src/components/setup/MaterialProcessing.tsx

<div className={styles.processingPanel}>
  <h2>Processing Materials</h2>
  <div className={styles.overallProgress}>
    <ProgressBar value={60} max={100} />
    <span>3 of 5 complete</span>
  </div>
  
  <div className={styles.materialsList}>
    <MaterialItem
      filename="Contract.pdf"
      status="complete"
      category="Legal"
      icon="✅"
    />
    <MaterialItem
      filename="Roadmap.docx"
      status="complete"
      category="Product"
      icon="✅"
    />
    <MaterialItem
      filename="Research.pdf"
      status="processing"
      category="?"
      progress={45}
      icon="⏳"
    />
    <MaterialItem
      filename="Budget.xlsx"
      status="failed"
      error="Unsupported format"
      icon="❌"
      actions={<button>Retry</button>}
    />
    <MaterialItem
      filename="Proposal.pdf"
      status="queued"
      icon="⏸️"
    />
  </div>
</div>
```

#### **Component 2: Agent Preflight Dashboard**
```tsx
// apps/web/src/components/setup/AgentPreflight.tsx

<div className={styles.preflightPanel}>
  <h2>Preparing Your Panel</h2>
  <p className={styles.estimate}>Estimated time: 2-3 minutes</p>
  
  <div className={styles.agentsList}>
    <AgentPreflightCard
      agentName="CFO (Analytical)"
      status="ready"
      steps={[
        { label: "Reviewed documents", status: "complete", detail: "12 chunks from Financial category" },
        { label: "Internet research", status: "complete", detail: "Current market data" },
        { label: "Generated briefing", status: "complete", detail: "240 words" }
      ]}
      briefingPreview="Reviewed budget docs, researched Q1 2026 market trends..."
      icon="✅"
    />
    
    <AgentPreflightCard
      agentName="Senior PM (Visionary)"
      status="ready"
      steps={[
        { label: "Reviewed documents", status: "complete", detail: "8 chunks from Product category" },
        { label: "Internet research", status: "complete", detail: "Competitor analysis" },
        { label: "Generated briefing", status: "complete", detail: "285 words" }
      ]}
      icon="✅"
    />
    
    <AgentPreflightCard
      agentName="Legal Counsel"
      status="processing"
      steps={[
        { label: "Reviewed documents", status: "complete", detail: "5 legal docs" },
        { label: "Internet research", status: "processing", detail: "45% complete..." },
        { label: "Generated briefing", status: "pending" }
      ]}
      progress={65}
      icon="⏳"
    />
    
    <AgentPreflightCard
      agentName="Engineer (Pragmatic)"
      status="failed"
      steps={[
        { label: "Reviewed documents", status: "complete" },
        { label: "Internet research", status: "failed", detail: "Timeout after 60s" }
      ]}
      error="Research API timeout"
      actions={
        <>
          <button onClick={() => retry(agentId)}>Retry</button>
          <button onClick={() => skip(agentId)}>Skip & Use Docs Only</button>
        </>
      }
      icon="❌"
    />
    
    <AgentPreflightCard
      agentName="First Principles Thinker"
      status="queued"
      icon="⏸️"
    />
  </div>
  
  <div className={styles.actions}>
    <button onClick={handleAbort} className={styles.btnSecondary}>
      Cancel Preparation
    </button>
    <button 
      onClick={handleStartAnyway} 
      disabled={readyCount === 0}
      className={styles.btnPrimary}
    >
      Start with {readyCount}/5 Agents Ready
    </button>
  </div>
</div>
```

---

## State Machine Extension

### Current States
```
pending → running → paused → ended
```

### New States (With Preparation)
```
pending
  ↓
materials_processing
  ↓
materials_ready
  ↓
preparing_agents
  ↓
ready  (NEW: agents prepared, waiting for user to start)
  ↓
running
  ↓
paused
  ↓
ended
```

### State Transitions

| From State | To State | Trigger | Conditions |
|------------|----------|---------|------------|
| `pending` | `materials_processing` | POST /materials/upload | User uploads files |
| `materials_processing` | `materials_ready` | Auto | All materials processed or failed |
| `materials_ready` | `preparing_agents` | POST /prepare | User clicks "Prepare Panel" |
| `preparing_agents` | `ready` | Auto | ≥50% agents ready OR user skips |
| `preparing_agents` | `preparation_failed` | Auto | All agents failed |
| `ready` | `running` | POST /start | User clicks "Start Debate" |
| `ready` | `pending` | POST /reset | User restarts setup |

---

## Implementation Phases

### **Phase 1: Materials Pipeline Only** (2 weeks)
**Goal**: Users can upload docs, agents see them in debate

**Deliverables**:
- ✅ File upload endpoint + MinIO storage
- ✅ Text extraction (PDF, DOCX, TXT, URLs)
- ✅ Simple chunking (fixed 2000 char, no AI)
- ✅ Store chunks in `memory_chunks` (no embeddings yet)
- ✅ At debate start: Concatenate all chunks into system prompt
- ✅ Progress UI for material processing
- ❌ Skip: AI categorization, embeddings, vector search, research

**Cost**: ~$0 per debate (no AI processing)  
**User Wait Time**: 30 seconds - 2 minutes

**Outcome**: Agents can reference uploaded materials (basic but functional)

---

### **Phase 2: Smart Retrieval** (2 weeks)
**Goal**: Scale to large documents with relevant context per turn

**Deliverables**:
- ✅ AI categorization (OpenRouter GPT-4)
- ✅ Semantic chunking (LangChain)
- ✅ Embedding generation (OpenRouter)
- ✅ pgvector storage + indexing
- ✅ Dynamic context retrieval per turn
- ✅ Citation tracking back to source chunks
- ❌ Skip: Internet research, agent preflight

**Cost**: ~$0.10-0.30 per debate  
**User Wait Time**: 1-3 minutes (categorization + embeddings)

**Outcome**: Agents get relevant context per turn, scales to 100+ page docs

---

### **Phase 3: Agent Preflight + Research** (3 weeks)
**Goal**: Agents come prepared with research and briefings

**Deliverables**:
- ✅ Perplexity API integration
- ✅ Agent preparation orchestrator (parallel)
- ✅ Per-agent material retrieval (vector search)
- ✅ Per-agent research queries
- ✅ Briefing memo generation
- ✅ Context injection into system prompts
- ✅ Progress UI with per-agent cards
- ✅ Retry/skip controls
- ✅ Fallback for unprepared agents

**Cost**: ~$0.50-1.50 per debate (with research)  
**User Wait Time**: 2-4 minutes (parallel agent prep)

**Outcome**: Full vision - prepared agents with docs + research

---

### **Phase 4: Custom Agents UI** (1 week, can be parallel to Phase 1)
**Goal**: Users can create custom agents in Settings

**Deliverables**:
- ✅ Settings page: Custom Agent Builder
- ✅ Form: name, role, character, system prompt
- ✅ Prompt preview
- ✅ Save to workspace (POST /agents)
- ✅ Edit/delete existing agents
- ✅ Import/export agent configs

**Cost**: $0  
**User Value**: HIGH (most requested feature)

**Outcome**: Users not limited to 10 presets

---

## Cost Analysis

### Per-Debate Cost Breakdown (5 agents, 5 docs)

| Stage | Operation | Unit Cost | Quantity | Total |
|-------|-----------|-----------|----------|-------|
| **Stage 2: Materials** | | | | |
| | File storage | $0.001/GB/month | 50MB | ~$0.001 |
| | Text extraction | $0 | 5 docs | $0 |
| | AI categorization | $0.01-0.02/doc | 5 docs | $0.05-0.10 |
| | Chunking | $0 | - | $0 |
| | Embeddings | $0.002/doc | 5 docs | $0.01 |
| | **Subtotal Stage 2** | | | **$0.06-0.11** |
| **Stage 3: Preflight** | | | | |
| | Vector search | $0 | 5 agents | $0 |
| | Internet research | $0.05-0.20/query | 5 agents | $0.25-1.00 |
| | Briefing memos | $0.02-0.05/agent | 5 agents | $0.10-0.25 |
| | **Subtotal Stage 3** | | | **$0.35-1.25** |
| **Stage 4: Debate** | | | | |
| | Debate turns | $0.05-0.20/turn | 10 turns | $0.50-2.00 |
| | Summary generation | $0.05-0.10 | 1 | $0.05-0.10 |
| | **Subtotal Stage 4** | | | **$0.55-2.10** |
| | | | | |
| **TOTAL PER DEBATE** | | | | **$0.96-3.46** |

### Cost Scaling Analysis

| Scenario | Setup | Est. Cost | Acceptable? |
|----------|-------|-----------|-------------|
| Quick debate (2 agents, 1 doc, no research) | Small | $0.20 | ✅ Yes |
| Standard debate (5 agents, 5 docs, research) | Medium | $1.50 | ✅ Yes (enterprise) |
| Large debate (8 agents, 20 docs, research) | Large | $4.00 | ⚠️ Maybe (premium tier) |
| Massive debate (8 agents, 100 docs, research) | Very Large | $12.00+ | ❌ Need optimization |

**Recommendation**: 
- Tier 1 (Free): Max 2 agents, 3 docs, no research
- Tier 2 (Pro): Max 5 agents, 10 docs, research enabled
- Tier 3 (Enterprise): Max 8 agents, unlimited docs, research + custom models

---

## Risk Mitigation Strategies

### **Risk 1: Long Wait Times** ⏰

**Problem**: User waits 3-5 minutes before debate starts

**Mitigations**:
1. ✅ **Show detailed progress** (not just spinner)
   - "Processing Contract.pdf... 2 of 12 pages"
   - "Agent 3 researching financial trends... 45%"
2. ✅ **Accurate time estimates** 
   - "Estimated time: 2-3 minutes"
   - Update in real-time as tasks complete
3. ✅ **Parallel execution**
   - All agents prepare simultaneously (not serial)
   - Materials process while user picks agents
4. ✅ **Skip option**
   - "Start debate now without preparation" button
   - Trade-off clearly explained

---

### **Risk 2: Partial Failures** ⚠️

**Problem**: 1-2 agents fail to prepare, what happens?

**Solution** (Your suggestion - EXCELLENT):
```
┌────────────────────────────────────────────┐
│  Agent Preparation Complete                │
│  ✅ 4 of 5 agents ready                    │
│                                            │
│  ❌ Agent 3 (Legal) - Research failed      │
│     Error: Perplexity API timeout         │
│                                            │
│  Options:                                  │
│  [Retry Legal Agent]                       │
│  [Start with 4 Agents]                     │
│  [Cancel & Fix Setup]                      │
└────────────────────────────────────────────┘
```

**Fallback for Failed Agent**:
- Still participates in debate
- Gets: problem statement + raw document text
- No research insights
- System prompt includes: "Note: Your preparation step failed. Base input on provided materials only."

**Audit Trail**:
- Log which agents were fully prepared vs fallback
- Include in final report: "Legal agent participated without research due to API timeout"

---

### **Risk 3: API Rate Limits / Costs** 💰

**Problem**: OpenRouter/Perplexity rate limits or budget overruns

**Mitigations**:
1. ✅ **Budget Controls**
   ```python
   MAX_PREPARATION_COST_PER_DEBATE = 2.00  # $2.00
   MAX_RESEARCH_QUERIES_PER_AGENT = 2
   MAX_RESEARCH_COST_PER_AGENT = 0.40
   ```
2. ✅ **Rate Limiting**
   - Max 5 concurrent API calls
   - Exponential backoff on 429 errors
3. ✅ **Caching**
   - Cache research results for 24 hours
   - If same problem + same role: reuse results
4. ✅ **Graceful Degradation**
   - If research fails: continue without it
   - If categorization fails: use "General" category

---

### **Risk 4: Bad Document Quality** 📄

**Problem**: Scanned PDFs, encrypted PDFs, malformed files

**Mitigations**:
1. ✅ **File Validation**
   - Max size: 50MB per file
   - Allowed types: PDF, DOCX, TXT
   - Virus scan (ClamAV or cloud service)
2. ✅ **OCR Fallback** (Phase 2)
   - If PDF has no text: use OCR (Tesseract or AWS Textract)
   - Warn user: "Scanned document detected, OCR in progress..."
3. ✅ **Quality Checks**
   - If extracted text < 100 chars: warn user
   - If AI categorization confidence < 50%: flag for manual review

---

## Open Questions

### **Q1: Research API Choice**

**Options**:
1. **Perplexity AI** (Recommended)
   - ✅ Best for: Factual research + citations
   - ✅ Cost: $0.05-0.20 per query
   - ✅ Quality: Excellent
   - ❌ Con: External dependency

2. **Tavily API**
   - ✅ Good for: News + recent events
   - ⚠️ Cost: Similar to Perplexity
   - ⚠️ Quality: Good but not as strong

3. **Custom (Google Custom Search)**
   - ✅ Cost: Cheaper ($0.005 per query)
   - ❌ Quality: Lower, needs post-processing
   - ❌ Complexity: More code to maintain

4. **OpenRouter + Web Browsing Model**
   - ⚠️ Experimental: Some models claim web access
   - ⚠️ Unclear pricing and reliability

**Recommendation**: Start with **Perplexity** for quality, can add alternatives later.

---

### **Q2: Should Research Be Enabled By Default?**

**Option A**: Research OFF by default (cost control)
- User explicitly enables: "Enable internet research (+$0.50, +2 min)"

**Option B**: Research ON by default (better quality)
- User explicitly disables: "Skip research (faster but less informed)"

**Recommendation**: 
- **Free tier**: Research OFF by default
- **Paid tier**: Research ON by default with budget controls

---

### **Q3: How to Handle Very Large Documents?**

**Scenario**: User uploads 200-page legal document

**Challenges**:
- Extraction: 2-3 minutes
- Categorization: $0.05
- Embedding: $0.10
- Storage: 150+ chunks

**Options**:
1. **Hard limit**: Max 50 pages per document
2. **Sampling**: AI categorizes first 10 pages only
3. **Progressive processing**: Process in batches, start debate with partial context
4. **Tiered limits**: Free tier 20 pages, Pro tier 100 pages, Enterprise unlimited

**Recommendation**: Start with **Option 1** (hard limit), add progressive processing in Phase 2

---

### **Q4: What If User Uploads 50 Documents?**

**Problem**: Processing time + cost becomes prohibitive

**Solution**: Tiered Limits
- **Free**: Max 3 documents
- **Pro**: Max 10 documents
- **Enterprise**: Max 50 documents (with batching)

Plus:
- Show cumulative cost estimate BEFORE processing
- "This will cost ~$2.50 and take ~5 minutes. Continue?"

---

## Success Criteria

### **Stage 2: Materials Ingestion**

| Metric | Target | Why |
|--------|--------|-----|
| Upload success rate | >95% | Reliability |
| Processing time (avg) | <60 seconds for 5 docs | User patience |
| Categorization accuracy | >80% | Agents get right context |
| Extraction quality | >90% text captured | No data loss |
| Cost per debate | <$0.30 | Scalability |

### **Stage 3: Agent Preflight**

| Metric | Target | Why |
|--------|--------|-----|
| Preparation success rate | >90% | Reliability |
| Parallel prep time | <3 minutes for 5 agents | User patience |
| Research quality | >80% relevant results | Agent usefulness |
| Briefing clarity | User-testable | Trust |
| Graceful failure handling | 100% | Enterprise requirement |
| Cost per debate | <$1.00 | Scalability |

---

## Alternative Approaches Considered

### **Alternative 1: No Preparation Phase** ❌

**Flow**: Setup → Start immediately, inject materials mid-debate

**Pros**:
- ✅ Instant start
- ✅ Simpler architecture

**Cons**:
- ❌ Agents start "cold"
- ❌ First few turns are low quality
- ❌ No research capability
- ❌ Users question: "Did agents see my docs?"

**Verdict**: **Rejected** - Doesn't meet quality bar

---

### **Alternative 2: Async Progressive Loading** ❌

**Flow**: Start debate immediately, materials/research arrive during debate

**Pros**:
- ✅ Zero wait time
- ✅ Progressive enhancement

**Cons**:
- ❌ Unpredictable quality (depends on timing)
- ❌ Complex state management (context changes mid-debate)
- ❌ Poor enterprise fit (non-deterministic)

**Verdict**: **Rejected** - UX confusion outweighs speed benefit

---

### **Alternative 3: User-Controlled Preparation** ⚠️

**Flow**: Setup → User decides: "Quick start" OR "Prepared start"

**Pros**:
- ✅ User control
- ✅ Supports both use cases

**Cons**:
- ⚠️ Decision fatigue
- ⚠️ Most users won't understand trade-off

**Verdict**: **Possible compromise** - Could offer as advanced option

---

## Recommended Decision

### **Build This (Your Proposed Flow)**:

```
✅ Stage 1: Setup
✅ Stage 2: Materials Ingestion (with progress UI)
✅ Stage 3: Agent Preflight (parallel, with retry/skip)
✅ Stage 4: Room (debate with full context)
```

### **Implementation Order**:

**Sprint 1-2 (2 weeks)**: Materials Pipeline (Phase 1)
- Get docs uploaded and extracted
- Basic injection into debate context
- Ship this, validate usage

**Sprint 3-4 (2 weeks)**: Smart Retrieval (Phase 2)
- Add AI categorization
- Add embeddings + vector search
- Dynamic context per turn

**Sprint 5-7 (3 weeks)**: Agent Preflight (Phase 3)
- Add research integration
- Add preparation orchestrator
- Add progress UI with retry/skip

**Sprint 8 (1 week)**: Custom Agents UI (Phase 4)
- Can be done in parallel with Sprint 1-2
- High value, low complexity

---

## Technical Dependencies

### Required Infrastructure

1. **Storage**: MinIO (already in docker-compose) or AWS S3
2. **Queue**: Redis (already in docker-compose) for job queue
3. **Worker**: Celery or custom async worker process
4. **Vector DB**: pgvector (already enabled in Supabase)
5. **WebSocket**: For real-time progress updates

### Required API Keys

1. **OpenRouter** (already required)
   - For: AI categorization, embeddings, briefing memos, debate
2. **Perplexity AI** (NEW)
   - For: Internet research with citations
   - Alternative: Tavily, Exa, or Google Custom Search

### Required Python Libraries

```txt
# Document processing
pypdf2>=3.0.0
pdfplumber>=0.10.0
python-docx>=1.1.0
beautifulsoup4>=4.12.0

# Embeddings & chunking
langchain>=0.1.0
openai>=1.0.0  # For embedding generation via OpenRouter
tiktoken>=0.5.0  # Token counting

# Job queue
celery>=5.3.0
redis>=5.0.0

# Research (if using Perplexity)
httpx>=0.26.0  # Already have this
```

---

## Success Metrics (Post-Launch)

### **Preparation Phase Adoption**
- % of debates that use material upload: Target >60%
- Avg documents per debate: Target 3-5
- % of debates with research enabled: Target >40%

### **Quality Metrics**
- Agent briefing quality (user survey): Target >4/5 stars
- Citation accuracy: Target >85% of claims cited
- Preparation failure rate: Target <5%

### **Performance Metrics**
- Avg material processing time: Target <60 sec
- Avg agent prep time (parallel): Target <180 sec
- P95 total wait time: Target <5 min

### **Cost Efficiency**
- Avg cost per debate: Target <$2.00
- Research query relevance: Target >80%
- Embedding reuse rate: Target >20% (cached results)

---

## Conclusion

### **Is Your Flow Strong?** 
✅ **YES** - It's the right architecture for enterprise-grade AI debates.

### **Is Your Flow Feasible?**
✅ **YES** - Technically sound, all components have proven implementations.

### **Should We Build It?**
✅ **YES** - But in phases to validate and iterate.

### **Timeline**
⏰ **6-8 weeks** for full implementation (all phases)
⏰ **2 weeks** for MVP (Phase 1: basic materials)

### **Your Design Decisions That Are EXCELLENT**:
1. ✅ Per-agent progress bars (transparency)
2. ✅ Retry/skip controls (graceful failure)
3. ✅ Unprepared fallback (debate never fully fails)
4. ✅ Complete picture before debate (quality over speed)

---

## Next Steps

**Decision Point**: Choose implementation approach:

**Option A - Fast MVP** (2 weeks):
- Materials upload + extraction only
- No AI processing, no research
- Simple context injection

**Option B - Full Vision** (6-8 weeks):
- Everything you described
- Full preparation pipeline
- Research integration

**Option C - Phased Rollout** (2+2+3 weeks):
- Week 1-2: Materials pipeline
- Week 3-4: Smart retrieval
- Week 5-7: Research + preflight

**Recommendation**: **Option C** (phased) - Validate incrementally, reduce risk.

---

**Document Status**: Design Complete, Ready for Implementation Planning  
**Next Document Needed**: Technical Implementation Spec (API contracts, DB migrations, component specs)
