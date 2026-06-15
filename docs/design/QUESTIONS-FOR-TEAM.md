# Questions for Team - Agent Preparation & Live Artifacts

**Date:** 2026-02-09  
**Context:** Review of updated design documents  
**Requested by:** Implementation planning  

---

## 🎯 1. SCOPE & PRIORITY QUESTIONS

### Q1.1: Live Artifacts - V1 or V2?
The `MEETING-FLOW-MEMORY-ARTIFACTS.md` introduces "Live Artifacts (Figma-Like)" with real-time collaboration, section ownership, and coherence pass.

**Question**: Is Live Artifacts a **must-have for V1**, or can we ship:
- V1: Basic artifacts (static sections, generated at end of debate)
- V2: Live collaboration (real-time typing, section ownership, coherence pass)

**Impact**: 
- Live Artifacts adds ~3-4 weeks to timeline
- Requires new SSE infrastructure, orchestration logic, and UI components

**Team Decision**: [ V1 / V2 / Partial (specify what's V1) ]

---

### Q1.2: Memory Import - V1 or V2?
The spec includes user-controlled memory sharing from prior meetings with per-agent scoping.

**Question**: Should V1 support memory import, or can we ship:
- V1: Materials ingestion + agent preflight only (single-meeting scope)
- V2: Memory import with allowlists and prior-meeting context

**Rationale**: Memory import requires:
- Import preview UI
- Allowlist management per agent
- Knowledge unit retrieval across debates
- Additional testing complexity

**Team Decision**: [ V1 / V2 / Partial (specify what's V1) ]

---

### Q1.3: Custom Agents UI - Priority?
Backend exists (`POST /agents`, `GET /agents`), but no UI in Settings page.

**Question**: Should Custom Agents UI be built:
- **In parallel with Phase 1** (materials pipeline) - can be done independently
- **After Phase 1** (sequential)
- **After Phase 3** (lower priority)

**Note**: User feedback suggests this is highly requested ("not limited to 10 presets").

**Team Decision**: [ Parallel / After Phase 1 / After Phase 3 ]

---

### Q1.4: Material Map - Required or Nice-to-Have?
The spec includes an AI-generated "Material Map" showing key topics, entities, dates, risk flags after ingestion.

**Question**: Is Material Map:
- **Required for V1** (critical UX validation)
- **Nice-to-have for V2** (can ship basic "X of Y processed" progress first)

**Cost**: ~$0.01-0.03 per debate (LLM call to generate map)

**Team Decision**: [ Required V1 / Nice-to-have V2 ]

---

## 🏗️ 2. TECHNICAL ARCHITECTURE QUESTIONS

### Q2.1: Coherence Pass - How Should This Work?
The Live Artifacts spec mentions a "coherence pass" where a host agent unifies tone and removes contradictions across sections.

**Question**: What's the technical implementation?
- **Option A**: Another LLM call (host/moderator agent reviews all sections, suggests edits)
  - Cost: ~$0.10-0.30 per artifact
  - Time: +30-60 seconds
- **Option B**: Template-based merge (fixed rules, no LLM)
  - Cost: $0
  - Time: <5 seconds
  - Limited intelligence
- **Option C**: User-driven review (no automatic coherence, user edits manually)
  - Cost: $0
  - Time: Variable

**Team Decision**: [ Option A / Option B / Option C / Other (specify) ]

---

### Q2.2: Artifact Section Assignment - Automatic or Manual?
Who decides which agent owns which artifact section?

**Question**: Should section assignment be:
- **Automatic** (host/orchestrator assigns based on agent role + section type)
- **User-controlled** (user explicitly assigns in setup wizard)
- **Hybrid** (automatic with user override)

**Example**: 
- Legal section → assigned to Legal Counsel agent
- Architecture section → assigned to Engineer agent

**Team Decision**: [ Automatic / User-controlled / Hybrid ]

---

### Q2.3: Vector Search Strategy
For material retrieval during agent preflight and live debate.

**Question**: Which pgvector indexing strategy?
- **Option A**: IVFFlat (faster build, good for <1M vectors)
  - Our use case: ~10-50 chunks per debate
- **Option B**: HNSW (slower build, better query performance at scale)
  - Overkill for our volume?

**Recommendation**: Start with IVFFlat, migrate to HNSW if we see performance issues at scale.

**Team Decision**: [ IVFFlat / HNSW / Start with IVFFlat ]

---

### Q2.4: Research API Choice
For internet research during agent preflight.

**Question**: Which research API should we integrate first?
- **Option A: Perplexity AI** (Recommended in spec)
  - ✅ Best citations
  - ✅ Reliable
  - Cost: $0.05-0.20 per query
  - Integration: Simple REST API
- **Option B: Tavily API**
  - ✅ Good for news/recent events
  - Cost: Similar to Perplexity
- **Option C: Custom (Google Custom Search)**
  - ✅ Cheapest ($0.005 per query)
  - ❌ Lower quality, needs post-processing
- **Option D: Start without research (Phase 1-2), add in Phase 3**

**Team Decision**: [ Perplexity / Tavily / Google / Start without ]

---

### Q2.5: Job Queue - Redis+Celery or Async Tasks?
For background processing of materials (extraction, chunking, embeddings).

**Question**: Should we use:
- **Option A: Redis + Celery** (production-grade, durable, retry logic)
  - ✅ Robust
  - ❌ More infrastructure
  - Redis already in docker-compose
- **Option B: FastAPI BackgroundTasks** (simple, in-process)
  - ✅ Zero additional infrastructure
  - ❌ Not durable (lost on server restart)
  - ❌ No retry logic
- **Option C: Hybrid** (BackgroundTasks for Phase 1, migrate to Celery for Phase 2+)

**Recommendation**: Option C (validate with simple approach, scale with Celery).

**Team Decision**: [ Celery / BackgroundTasks / Hybrid ]

---

## 🎨 3. USER EXPERIENCE QUESTIONS

### Q3.1: Preparation Wait Time - What's Acceptable?
Users will wait during materials processing + agent preflight.

**Question**: What's the acceptable maximum wait time?
- Materials processing: Currently estimated 30s - 3 min (5 docs)
- Agent preflight: Currently estimated 2-4 min (5 agents, parallel)
- **Total: 2.5 - 7 minutes**

Options:
- **Ship as-is** (with progress bars + skip option)
- **Add aggressive caching** (reuse embeddings for similar docs)
- **Add batch optimizations** (process multiple docs in one LLM call)

**Team Decision**: [ Ship as-is / Add caching / Add batch optimizations / Set hard limit: ___ minutes ]

---

### Q3.2: Failure Handling - Retry or Skip?
If 1-2 agents fail preparation (e.g., research timeout).

**Question**: Default behavior?
- **Option A**: Prompt user every time (Retry / Skip / Abort)
  - ✅ User control
  - ❌ Interrupts flow
- **Option B**: Auto-skip failed agents after 1 retry, show warning
  - ✅ Smoother flow
  - ❌ Less control
- **Option C**: Configurable (user sets preference in Settings)

**Current spec says**: "User controls: Retry, Skip, or Abort" (Option A)

**Team Decision**: [ Option A / Option B / Option C ]

---

### Q3.3: Cost Transparency - Show Before or After?
When should users see cost estimates?

**Question**: Display costs:
- **Before materials upload**: "Uploading 5 docs + research will cost ~$1.50. Continue?"
- **After debate ends**: "This debate cost $2.34. Details..."
- **Both** (estimate before, actual after)
- **Never** (BYOK users manage their own OpenRouter budget)

**Consideration**: BYOK means users pay OpenRouter directly. Do we need to show estimates?

**Team Decision**: [ Before / After / Both / Never ]

---

### Q3.4: Material Map UI - Where to Show It?
If we include Material Map in V1.

**Question**: Where should Material Map display?
- **Option A**: Inline after materials processing (Step 2 of setup wizard)
  - User sees: "5 docs processed. Key topics: Legal compliance, Pricing, Architecture..."
- **Option B**: Right panel during Room/debate (always visible)
- **Option C**: Modal/drawer (expandable on demand)
- **Option D**: All of the above (persistent in Room, summary in setup)

**Team Decision**: [ Option A / Option B / Option C / Option D ]

---

## 📅 4. IMPLEMENTATION TIMELINE QUESTIONS

### Q4.1: Timeline Commitment
Original estimate: 6-8 weeks for Phases 1-3.

**Question**: With the new requirements (Live Artifacts, Memory Import, Material Map), what's the realistic timeline?

**Rough Breakdown**:
- Phase 1 (Materials Pipeline): 2 weeks
- Phase 2 (Smart Retrieval): 2 weeks
- Phase 3 (Agent Preflight + Research): 3 weeks
- **+ Live Artifacts**: +3-4 weeks (if V1)
- **+ Memory Import**: +1-2 weeks (if V1)
- **+ Material Map**: +3-5 days (if V1)

**Total Range**: 7 weeks (no Live Artifacts) to 12 weeks (full V1)

**Team Decision**: [ 7 weeks (defer Live Artifacts) / 10 weeks (partial) / 12 weeks (full V1) / Other: ___ ]

---

### Q4.2: Parallel Work Streams
Can we parallelize to reduce timeline?

**Question**: Should we run these in parallel?
- **Stream A**: Materials + Preflight (backend-focused)
- **Stream B**: Custom Agents UI (Settings page, can be independent)
- **Stream C**: Live Artifacts UI (frontend-focused, depends on SSE infrastructure)

**Constraint**: Team size? (How many devs can work in parallel?)

**Team Decision**: [ Single stream / 2 parallel streams / 3 parallel streams ]  
**Team Size Available**: [ ___ developers ]

---

## 💰 5. COST & BUDGET QUESTIONS

### Q5.1: Research Default - On or Off?
Internet research via Perplexity adds $0.25-1.00 per debate.

**Question**: Should research be:
- **OFF by default** (user explicitly enables, with cost warning)
- **ON by default** (user explicitly disables)
- **Tiered** (Free tier: OFF, Paid tier: ON)

**Consideration**: Most users won't understand the value/cost trade-off.

**Team Decision**: [ OFF by default / ON by default / Tiered ]

---

### Q5.2: Per-Debate Budget Limits
Should we enforce hard limits to prevent runaway costs?

**Question**: Should we implement budget controls?
- **Option A**: Hard limits (reject operation if budget exceeded)
  - Example: Max $2.00 per debate
- **Option B**: Soft limits (warn user, allow override)
- **Option C**: No limits (user manages via OpenRouter dashboard)

**Note**: BYOK means users pay directly, but we can still enforce local limits.

**Team Decision**: [ Hard limits / Soft limits / No limits ]  
**If limits, what amount?**: [ $___  per debate ]

---

### Q5.3: Free Tier Document Limits
To control costs and processing time.

**Question**: What limits for non-paying users?
- **Documents**: [ Max ___ documents per debate ]
- **Pages**: [ Max ___ pages per document ]
- **Agents**: [ Max ___ agents per debate ]
- **Research**: [ Enabled: Yes / No ]

**Suggested**:
- Free: 3 docs, 20 pages/doc, 3 agents, no research
- Pro: 10 docs, 100 pages/doc, 5 agents, research enabled
- Enterprise: Unlimited

**Team Decision**: 
- Free tier: [ ___ docs / ___ pages / ___ agents / research: ___ ]
- Pro tier (if applicable): [ ___ docs / ___ pages / ___ agents / research: ___ ]

---

## 🚨 6. RISK MANAGEMENT QUESTIONS

### Q6.1: Scanned PDF Handling
If user uploads a scanned PDF (no text layer).

**Question**: Should we support OCR?
- **Phase 1**: Reject with clear error ("Scanned PDFs not supported. Please use text-based PDFs.")
- **Phase 2**: Add OCR (Tesseract or AWS Textract)
  - Cost: ~$0.01-0.05 per page
  - Time: +30-60 seconds per doc
- **User choice**: "This appears to be a scanned PDF. Run OCR? (+$0.10, +45 sec)"

**Team Decision**: [ Reject in Phase 1 / Add OCR in Phase 2 / User choice in Phase 1 ]

---

### Q6.2: Malicious File Uploads
Security concern: users uploading malware disguised as PDFs.

**Question**: Should we implement virus scanning?
- **Option A**: ClamAV (open-source, self-hosted)
  - ✅ Free
  - ❌ Maintenance overhead
- **Option B**: Cloud service (AWS S3 virus scan, VirusTotal API)
  - ✅ Managed
  - ❌ Cost per scan
- **Option C**: Skip for MVP (trust + basic file type validation only)

**Recommendation**: Option C for MVP, add in production hardening phase.

**Team Decision**: [ ClamAV / Cloud service / Skip for MVP ]

---

### Q6.3: Large Document Handling
User uploads a 200-page legal document.

**Question**: Should we:
- **Option A**: Hard limit (reject files >50 pages)
- **Option B**: Progressive processing (process first 50 pages immediately, queue rest)
- **Option C**: Tiered limits (Free: 20 pages, Pro: 100 pages, Enterprise: unlimited)
- **Option D**: Accept but warn about cost/time ("This will take ~3 minutes and cost ~$0.50")

**Team Decision**: [ Hard limit: ___ pages / Progressive processing / Tiered limits / Accept with warning ]

---

## 🔄 7. SCHEMA & DATABASE QUESTIONS

### Q7.1: Confirm Schema Reuse Strategy
The updated spec reuses `memory_chunks`, `agent_knowledge_units`, `meeting_materials` instead of creating new tables.

**Question**: Confirm this is the final approach?
- ✅ Reuse existing tables (as documented)
- ❌ Create dedicated tables (`document_chunks`, `agent_briefings`)

**Benefits of reuse**:
- Unified retrieval API
- Existing audit trail
- Less join complexity

**Downsides**:
- Nullable `agent_id` in `memory_chunks` (was always required before)
- Need to filter by `source_type` everywhere

**Team Decision**: [ Confirm reuse / Prefer dedicated tables ]

---

### Q7.2: Memory Import Storage - V1 Approach
For memory import allowlists (which prior meetings/artifacts can agents access).

**Question**: V1 storage strategy?
- **Option A**: Store in `debates.policy_config` JSONB (simple, no new tables)
- **Option B**: Create `debate_memory_grants` join table (more queryable, but overkill for V1?)

**Spec says**: "V1 (lowest complexity): store allowlists in debates.policy_config"

**Team Decision**: [ policy_config (V1) / debate_memory_grants / Other ]

---

## 🧪 8. TESTING & VALIDATION QUESTIONS

### Q8.1: How to Test Agent Preflight Without Real API Costs?
Agent preflight calls OpenRouter (embeddings, research, briefing generation).

**Question**: Testing strategy?
- **Option A**: Mock all OpenRouter calls in tests (fast, free, but doesn't validate real behavior)
- **Option B**: Use real OpenRouter calls with test budget (slow, costs money, validates end-to-end)
- **Option C**: Hybrid (mock for unit tests, real calls for integration tests with small inputs)

**Recommendation**: Option C

**Team Decision**: [ Mock all / Real calls / Hybrid ]

---

### Q8.2: What Defines "Success" for Phase 1?
Materials pipeline is complete when...?

**Question**: Phase 1 completion criteria?
- [ ] User can upload PDF/DOCX/TXT/URL
- [ ] System extracts text (no OCR required)
- [ ] System chunks text (fixed size, no AI categorization)
- [ ] Chunks stored in `memory_chunks` with provenance
- [ ] Progress UI shows "X of Y processed"
- [ ] Debate can start and agents receive concatenated chunks in system prompt
- [ ] All chunks <50 pages processed within 2 minutes
- [ ] Other: ___

**Team Decision**: Check all that apply ☑️

---

## 📋 9. OPEN DESIGN DECISIONS

### Q9.1: Agent Personas - How Detailed?
Current templates have `character` field (e.g., "Visionary - Jobs-inspired").

**Question**: How much character should influence behavior?
- **Light touch**: Character is a 1-line prompt addition ("Think like Steve Jobs")
- **Heavy influence**: Character affects tone, risk appetite, decision style (requires detailed prompt engineering)

**Consideration**: Heavy influence = more token usage, harder to control.

**Team Decision**: [ Light touch / Heavy influence / User-configurable ]

---

### Q9.2: Intervention During Artifact Drafting
If agents are drafting an artifact and user wants to intervene.

**Question**: Should user be able to:
- **Comment on sections** (non-blocking, agents see comments)
- **Edit sections directly** (overrides agent ownership)
- **Request rewrite** (agent redrafts)
- **Lock sections** (prevent further agent edits)
- **All of the above**

**Team Decision**: [ Comment only / Edit directly / Request rewrite / Lock / All of the above ]

---

### Q9.3: Artifact Versioning - Automatic or Manual?
If user/agent edits an artifact after it's generated.

**Question**: Should we create versions:
- **Automatically** (every edit creates a new version)
- **Manually** (user clicks "Save Version" when desired)
- **Hybrid** (auto-save drafts, user marks "final" versions)

**Storage consideration**: Artifacts can be large (5-10KB text). Many versions = storage cost.

**Team Decision**: [ Automatic / Manual / Hybrid ]

---

## ✅ 10. IMMEDIATE ACTION ITEMS

### Q10.1: Missing Technical Specs
Based on review, these specs are needed before implementation:

1. **LIVE-ARTIFACTS-TECHNICAL-SPEC.md**
   - API contracts (`POST /artifacts`, `GET /artifacts/{id}`)
   - SSE event types (`artifact_section_delta`, `artifact_section_committed`)
   - UI component breakdown
   - Coherence pass implementation
   
2. **MEMORY-IMPORT-UX-SPEC.md**
   - Import preview UI wireframes
   - Allowlist management per agent
   - "What will be imported" summary

3. **COST-ANALYSIS-UPDATE.md**
   - Add artifact generation costs to AGENT-PREPARATION-ARCHITECTURE.md
   - Break down by artifact type (brief, PRD, memo)

**Question**: Should we create these specs before starting implementation?
- **Yes, all 3 before any code** (slower start, but clear plan)
- **Create as needed** (start Phase 1, write Live Artifacts spec during Phase 2)
- **Skip for now** (iterate based on implementation learnings)

**Team Decision**: [ Yes, all 3 / Create as needed / Skip for now ]

---

### Q10.2: Who Writes These Specs?
**Question**: Who should write the missing specs?
- Product team
- Engineering team
- Collaborative (product drafts, engineering reviews)
- AI assistant (with team review)

**Team Decision**: [ Product / Engineering / Collaborative / AI assistant ]

---

## 📝 ANSWER TEMPLATE

To make it easy for your team to respond, here's a template:

```
## TEAM ANSWERS - [Date]

### 1. SCOPE & PRIORITY
Q1.1 Live Artifacts V1/V2: [Answer]
Q1.2 Memory Import V1/V2: [Answer]
Q1.3 Custom Agents UI Priority: [Answer]
Q1.4 Material Map Required: [Answer]

### 2. TECHNICAL ARCHITECTURE
Q2.1 Coherence Pass: [Answer]
Q2.2 Section Assignment: [Answer]
Q2.3 Vector Search: [Answer]
Q2.4 Research API: [Answer]
Q2.5 Job Queue: [Answer]

### 3. USER EXPERIENCE
Q3.1 Wait Time: [Answer]
Q3.2 Failure Handling: [Answer]
Q3.3 Cost Transparency: [Answer]
Q3.4 Material Map UI: [Answer]

### 4. TIMELINE
Q4.1 Timeline Commitment: [Answer]
Q4.2 Parallel Streams: [Answer], Team Size: [X devs]

### 5. COST & BUDGET
Q5.1 Research Default: [Answer]
Q5.2 Budget Limits: [Answer]
Q5.3 Free Tier Limits: [Answer]

### 6. RISK MANAGEMENT
Q6.1 Scanned PDFs: [Answer]
Q6.2 Virus Scanning: [Answer]
Q6.3 Large Documents: [Answer]

### 7. SCHEMA & DATABASE
Q7.1 Schema Reuse: [Answer]
Q7.2 Memory Import Storage: [Answer]

### 8. TESTING
Q8.1 Preflight Testing: [Answer]
Q8.2 Phase 1 Success: [Checklist]

### 9. OPEN DESIGN
Q9.1 Agent Personas: [Answer]
Q9.2 Intervention: [Answer]
Q9.3 Versioning: [Answer]

### 10. ACTION ITEMS
Q10.1 Missing Specs: [Answer]
Q10.2 Who Writes: [Answer]

### ADDITIONAL NOTES
[Any clarifications, concerns, or new requirements]
```

---

**Document Status**: Ready for team review  
**Next Step**: Team discussion and answers

---

## TEAM ANSWERS - 2026-02-09 (Product Lead Decisions)

These answers are chosen to maximize product quality and enterprise trust. We are not optimizing for minimal cost/time; we are optimizing for a premium, defensible system.

### 1. SCOPE & PRIORITY
Q1.1 Live Artifacts V1/V2: **Partial V1 (Must-have).**
- V1 includes: artifact templates, section ownership, live drafting with streaming deltas, coherence pass, versioning.
- V2 includes: true multi-human co-editing via CRDT (Yjs), offline, granular merge tools.

Q1.2 Memory Import V1/V2: **V1 (Must-have).**
- Must support: user-enabled prior context, scoped per agent (all agents or selected).
- Must be auditable: show "what was imported" preview and enforce allowlists in retrieval.

Q1.3 Custom Agents UI Priority: **Parallel.**
- This is a core product expectation and unblocks real use cases (not limited to presets).

Q1.4 Material Map Required: **Required V1.**
- Without it users won’t trust ingestion and agents won’t feel “prepared”.

### 2. TECHNICAL ARCHITECTURE
Q2.1 Coherence Pass: **Option A (LLM) + deterministic checks.**
- LLM performs tone/consistency/contradiction cleanup.
- Deterministic checks enforce: required sections present, citations exist, intended outcome explicitly addressed.

Q2.2 Section Assignment: **Hybrid.**
- System suggests owners by role/category, user/host can override.
- Host can reassign mid-draft.

Q2.3 Vector Search: **HNSW.**
- Default to HNSW for best retrieval quality and lower tuning burden.
- Our volume is small today but we want quality and future scaling without reindex surprises.

Q2.4 Research API: **Perplexity first + provider abstraction.**
- Implement `ResearchProvider` interface so enterprise can swap/disable providers.
- Require citations; research is an explicit policy toggle per meeting and per agent.

Q2.5 Job Queue: **Redis + Celery from day 1.**
- Materials + OCR + embeddings + preflight are background work and must be durable, retryable, observable.

### 3. USER EXPERIENCE
Q3.1 Wait Time: **Ship as-is with high-quality progress + “Start anyway”.**
- Target experience: 2-4 minutes typical; allow longer for large docs with clear ETA.

Q3.2 Failure Handling: **Option C (Configurable), default = 1 auto-retry then prompt.**
- Default behavior: auto retry once; if still failing, show Retry / Skip / Abort.

Q3.3 Cost Transparency: **Both (estimate before, actual after), but keep it optional UI.**
- BYOK means users pay OpenRouter, but enterprise stakeholders still want predictability.

Q3.4 Material Map UI: **Option D.**
- Summary in setup, persistent in room (right panel), and expandable drawer for details.

### 4. TIMELINE
Q4.1 Timeline Commitment: **12 weeks (full V1).**
- Includes live artifacts V1 (streaming drafting), memory import, materials map, preflight, research, and reliability hardening.

Q4.2 Parallel Streams: **3 parallel streams.**
- Stream A: materials ingestion + retrieval + preflight orchestrator
- Stream B: custom agents + persona generation UX
- Stream C: live artifacts engine + UI (streaming deltas + coherence pass)

### 5. COST & BUDGET
Q5.1 Research Default: **OFF by default (enterprise-safe), easy “Enable” in preflight.**
- Many orgs require explicit internet enablement and audit trails.

Q5.2 Budget Limits: **Soft limits with override (admin policy).**
- Default soft cap; enterprise admin can convert to hard caps.

Q5.3 Free Tier Limits: **Not a blocking decision for current build.**
- If needed later: Free tier is strict; Pro/Enterprise configurable.

### 6. RISK MANAGEMENT
Q6.1 Scanned PDFs: **User choice in Phase 1 (recommended ON when detected).**
- Detect “no text layer” and prompt: “Run OCR now?” with expected time.

Q6.2 Virus Scanning: **ClamAV.**
- This is table-stakes for enterprise file ingestion.

Q6.3 Large Documents: **Progressive processing + accept with warning.**
- Process first batch quickly, continue in background; retrieval uses what’s ready.

### 7. SCHEMA & DATABASE
Q7.1 Schema Reuse: **Confirm reuse.**
- Reuse `meeting_materials`, `memory_chunks`, `agent_knowledge_units`, `events`, `memory_access_log`.
- Do not create duplicate “document_chunks” or “agent_briefings” tables.

Q7.2 Memory Import Storage: **Join table (`debate_memory_grants`) (choose Option B).**
- We want queryability, auditability, and enforcement without JSON parsing pitfalls.

### 8. TESTING & VALIDATION
Q8.1 Preflight Testing: **Hybrid.**
- Mock for unit tests; small real-call integration tests behind an explicit flag for CI environments that allow it.

Q8.2 Phase 1 Success: **All listed boxes, plus “citations work end-to-end”.**
- Minimum: user sees that agents actually reference uploaded content with provenance.

### 9. OPEN DESIGN
Q9.1 Agent Personas: **User-configurable (default = light touch, optional “strong”).**
- Provide a “persona intensity” slider so users can decide how theatrical vs professional.

Q9.2 Intervention: **All of the above.**
- Comment, request rewrite, lock, and reassign ownership are required for enterprise workflows.

Q9.3 Versioning: **Hybrid.**
- Auto-save drafts; user marks “final” versions.

### 10. ACTION ITEMS
Q10.1 Missing Specs: **Yes, all 3 before starting implementation of those areas.**
- We can build materials ingestion in parallel, but do not start live artifacts or memory import without specs.

Q10.2 Who Writes: **AI assistant drafts + engineering review + product sign-off.**

### ADDITIONAL NOTES
- Internet research is not just a feature toggle; it is a policy + audit requirement.
- The "live artifact" V1 must still feel live: streaming deltas, presence, ownership, and host coherence pass.
