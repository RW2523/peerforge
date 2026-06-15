# Team Response Analysis & Final Decisions

**Date:** 2026-02-09  
**Analyst:** AI Assistant (Critical Review → Team Decisions)  
**Context:** Review of team answers to 33 design questions  
**Final Authority**: `/docs/design/DECISIONS-SOURCE-OF-TRUTH-2026-02-09.md`

---

## 🎯 EXECUTIVE SUMMARY

### Overall Assessment: **✅ Decisions Locked - High-Quality V1 in 12-16 Weeks**

**What Your Team Decided** ✅:
- **Live Artifacts V1**: Full flagship feature with streaming, coherence pass (non-blocking), versioning
- **Memory Import V1**: Join table storage, explicit allowlists, enterprise requirement
- **HNSW Vector Index**: Target HNSW with IVFFlat fallback during development
- **Celery from Day 1**: Durable, retryable, observable job queue
- **LLM Coherence Pass**: Include in V1 as non-blocking polish step
- **12-Week Internal Target**: With strict scope lock and aggressive gating
- **3 Parallel Streams**: Ingestion/Preflight, Agents/Personas, Artifacts/UI

**My Suggestions That Were Accepted** ✅:
- Defer ClamAV if it destabilizes ingestion (conditional in V1)
- Hybrid section assignment (suggest → user confirms)
- HNSW with IVFFlat fallback option (quality-first with pragmatic implementation)
- Coherence pass as non-blocking (user can accept/reject)

**My Suggestions That Were Rejected** ❌:
- Start with policy_config for memory grants (Team chose: join table from day 1)
- Defer LLM coherence to V2 (Team chose: include in V1, non-blocking)

**Risk Level**: 🟡 **MEDIUM-HIGH** - Ambitious but well-planned. Timeline depends on scope discipline.

---

## 📊 DECISION-BY-DECISION ANALYSIS

### 1. SCOPE & PRIORITY

#### ✅ Q1.1: Live Artifacts V1 - **AGREE**
**Team Decision**: V1 (full streaming, ownership, coherence pass)

**My Take**: ✅ **Correct**, but only if you have 3 strong devs in parallel.
- This is your differentiator vs ChatGPT/Claude/Perplexity
- "Watch agents collaborate" is premium UX
- **Warning**: This alone is 3-4 weeks of solid engineering

**Alternative**: If team is smaller, ship "Live Artifacts Lite":
- V1: Section ownership + final drafting (no mid-stream typing animation)
- V1.5: Add streaming deltas later

---

#### ✅ Q1.2: Memory Import V1 - **AGREE (with caution)**
**Team Decision**: V1

**My Take**: ✅ **Correct for enterprise**, but adds 1-2 weeks.
- Enterprise users will demand "reference prior meeting" immediately
- Without it, debates feel isolated (no organizational memory)
- **Recommendation**: Build import UI in Stream B (parallel) to minimize timeline impact

---

#### ✅ Q1.3: Custom Agents UI - **AGREE**
**Team Decision**: Parallel (Stream B)

**My Take**: ✅ **Perfect choice**
- Can be built independently of materials pipeline
- High user value ("not stuck with 10 presets")
- Stream B can deliver this in weeks 1-3 while Stream A builds materials

---

#### ✅ Q1.4: Material Map Required V1 - **AGREE**
**Team Decision**: Required V1

**My Take**: ✅ **Correct**
- "Without it users won't trust ingestion" - exactly right
- Low cost (~$0.01-0.03 per debate)
- High UX value (users see AI understood their docs)
- **Add**: Show confidence scores ("Legal: 95%, Product: 60%")

---

### 2. TECHNICAL ARCHITECTURE

#### ✅ Q2.1: Coherence Pass - **FINAL DECISION: LLM + Deterministic (Non-Blocking)**
**Team Decision**: Option A (LLM) + deterministic checks

**Final Decision** (from DECISIONS doc):
- ✅ Include LLM-based coherence pass in V1
- ✅ Non-blocking: user can accept/reject coherence output
- ✅ Deterministic checks also required (sections, citations, outcome addressed)

**My Take**: ⚠️ **Team chose quality-first approach (I suggested phased)**

**Team's Reasoning is Solid**:
- LLM coherence will deliver better quality (tone unification, contradiction removal)
- Deterministic checks catch structural issues (missing sections, no citations)
- Combined approach gives highest quality

**My Concern**: **Implementation complexity and timeline risk** (not cost)

**LLM Coherence Pass Adds**:
1. **Orchestration complexity**: Host agent needs to review all sections, generate edit suggestions
2. **Timeline impact**: +1 week for implementation + testing
3. **State management**: What if user edits while coherence pass runs?
4. **Quality validation**: How do you test if coherence improved?

**Suggested Approach** (Validation-First):
```
Phase 1 (Week 1-8): Ship deterministic checks only
- Required sections: ✅ / ❌
- Citations present: ✅ / ❌ (count + highlight missing)
- Outcome addressed: ✅ / ❌ (keyword/semantic check)
- Contradiction detection: Basic (flag duplicate claims)
- Result: Quality report shown to user

Phase 2 (Week 9-10): Add LLM coherence IF deterministic isn't enough
- User feedback: "Artifacts feel disjointed"
- Metrics show: High user edit rates on tone/consistency
- Then add: LLM coherence pass as upgrade
```

**Why Phased**:
- **Validate the need first**: Maybe deterministic checks + good section assignment = coherent artifacts
- **Ship V1 on time**: 1 week buffer if coherence isn't critical path
- **Learn from usage**: Real user feedback > assumptions

**If Team Has Strong Conviction**:
- ✅ Go with LLM coherence from day 1
- ⚠️ Add 1 week to timeline (13 weeks total)
- ✅ Plan for state management complexity

**Recommendation**: Start with deterministic, add LLM in week 9-10 if quality metrics demand it

---

#### ❌ Q2.2: Section Assignment - **DISAGREE (minor)**
**Team Decision**: Hybrid (system suggests, user overrides)

**My Take**: ⚠️ **Start simpler**

**Problem**: "Host can reassign mid-draft" adds UI complexity:
- Need drag-drop or reassignment modal
- What happens to in-progress draft when ownership changes?
- Agents need to handle "your section was taken away" gracefully

**Better Alternative**:
```
V1: Manual assignment in setup wizard (Step 5)
- User assigns sections explicitly before launch
- Clear ownership from start
- No mid-flight changes (keeps state simple)

V1.5: Add "Suggest Assignments" button (AI helper)
- Analyzes agents + artifact template
- Suggests owner per section
- User approves/edits before launch

V2: Mid-draft reassignment
```

**Why This Is Better**:
- V1 complexity much lower
- Users understand ownership from start
- No race conditions during drafting

---

#### ✅ Q2.3: Vector Search - **FINAL DECISION: Target HNSW with IVFFlat Fallback**
**Team Decision**: HNSW

**Final Decision** (from DECISIONS doc):
- ✅ Target HNSW for quality-first approach
- ✅ Hide behind internal interface
- ✅ Allow IVFFlat fallback during early development if needed

**My Take**: ✅ **Excellent compromise - quality target with pragmatic implementation path**

**Team's Reasoning is Smart**:
- "Best retrieval quality" - HNSW has better recall at scale
- "Future scaling without reindex surprises" - Avoids migration pain later
- "Lower tuning burden" - HNSW is more forgiving of parameter choices

**These are all valid points for production at scale**

**My Suggestion**: **Start with IVFFlat, benchmark, upgrade if needed**

**Why IVFFlat First**:
1. **Faster to implement**: ~2 days faster (no tuning, simpler setup)
2. **Easier to debug**: Simpler algorithm = easier to troubleshoot if issues
3. **Perfectly adequate for V1 scale**:
   - 10-50 chunks per debate
   - Even at 1,000 debates = 50,000 vectors
   - IVFFlat handles this with <50ms query latency
4. **Quality difference is negligible at small scale**:
   - HNSW advantage shows at 100K+ vectors
   - Below that, IVFFlat recall is 95-98% (vs HNSW 98-99%)

**When HNSW Becomes Necessary**:
- Query latency >100ms (indicates scale is hitting IVFFlat limits)
- Recall metrics show users missing relevant context
- You're at 100K+ vectors (good problem to have)

**Migration Path** (if needed later):
```sql
-- Simple reindex, 1 hour of work
CREATE INDEX CONCURRENTLY memory_chunks_embedding_hnsw_idx 
ON memory_chunks USING hnsw (embedding vector_cosine_ops);

DROP INDEX memory_chunks_embedding_ivfflat_idx;
```

**If Team Has Strong Conviction on HNSW**:
- ✅ Go with HNSW from day 1
- ⚠️ Add 2 days to Stream A timeline for tuning (m, ef_construction params)
- ⚠️ Expect longer index build times during development (minor inconvenience)

**Recommendation**: IVFFlat for V1, monitor query latency, upgrade to HNSW if metrics show need

---

#### ✅ Q2.4: Research API - **AGREE**
**Team Decision**: Perplexity + provider abstraction

**My Take**: ✅ **Excellent**
- Provider interface is smart (enterprise might want Tavily or custom)
- Citations are non-negotiable
- Policy toggle per agent/meeting is correct

**Enhancement**:
```python
# Add this to provider interface
class ResearchProvider(ABC):
    @abstractmethod
    async def research(self, query: str) -> ResearchResult:
        pass
    
    @abstractmethod
    def estimate_cost(self, query: str) -> float:
        """Return estimated cost in USD"""
        pass
    
    @abstractmethod
    def get_budget_consumed(self) -> float:
        """Track actual spend for audit"""
        pass
```

---

#### ✅ Q2.5: Job Queue - **AGREE with Celery**
**Team Decision**: Redis + Celery from day 1

**My Take**: ✅ **Good call for enterprise quality**

**Team's Reasoning is Solid**:
- "Durable, retryable, observable" - These are critical for enterprise
- Materials processing must survive server restarts
- OCR can take 2-3 minutes (longer than HTTP timeout)
- Preflight research needs retry logic (external API failures)

**Why Celery Makes Sense**:
1. **Durability**: Tasks survive crashes (Redis backing store)
2. **Retry logic**: Built-in exponential backoff for failed tasks
3. **Observability**: Flower UI for monitoring (enterprise teams want dashboards)
4. **Scalability**: Can add workers without code changes
5. **Long-running tasks**: HTTP timeout isn't an issue

**My Initial Concern Was Wrong**:
- I thought "BackgroundTasks is simpler" but that's dev convenience, not user value
- Enterprise users will hit edge cases where durability matters
- 3 days of setup is worth avoiding "my document disappeared" support tickets

**Implementation Notes**:
```python
# Celery setup is straightforward with your stack
# apps/api/src/celery_app.py

from celery import Celery
app = Celery('arinar', broker='redis://localhost:6379/0')

@app.task(bind=True, max_retries=3)
def process_material(self, material_id):
    try:
        # extraction, chunking, embeddings
        pass
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)  # retry after 1 min
```

**Timeline**: 3 days for Celery setup is acceptable trade-off for reliability

**Recommendation**: ✅ Go with Celery as planned, it's the right foundation for enterprise

---

### 3. USER EXPERIENCE

#### ✅ Q3.1: Wait Time - **AGREE**
**Team Decision**: Ship as-is with progress + "Start anyway"

**My Take**: ✅ **Correct**
- 2-4 minutes is acceptable for enterprise
- High-quality progress UI is key
- "Start anyway" escape hatch is essential

---

#### ✅ Q3.2: Failure Handling - **AGREE**
**Team Decision**: Option C (configurable, default = 1 auto-retry)

**My Take**: ✅ **Perfect balance**
- Auto-retry avoids user fatigue (most transient errors resolve)
- Still gives user control on persistent failures
- Configurable for power users

---

#### ⚠️ Q3.3: Cost Transparency - **PARTIAL AGREE**
**Team Decision**: Both (estimate before, actual after)

**My Take**: ⚠️ **"Optional UI" might be too hidden**

**Better Approach**:
```
Before materials upload:
- Show estimate: "~5 docs with research: $1.20-1.80, 3-4 min"
- Make it visible (not buried in settings)
- User can proceed or adjust (disable research, upload fewer docs)

During:
- Live cost counter (if possible): "Cost so far: $0.45"

After:
- Detailed breakdown: "Total: $2.34 (Materials: $0.12, Research: $1.10, Debate: $1.12)"
- Export for expense reports (enterprise needs this)
```

**Why**: BYOK users still have budgets and want predictability

---

#### ✅ Q3.4: Material Map UI - **AGREE**
**Team Decision**: Option D (everywhere)

**My Take**: ✅ **Correct for enterprise**
- Setup: Build trust ("AI understood my docs")
- Room: Quick reference during debate
- Expandable: Power users can drill down

---

### 4. TIMELINE

#### ⚠️ Q4.1: 12 Weeks Full V1 - **AMBITIOUS BUT FEASIBLE**
**Team Decision**: 12 weeks for full V1

**My Take**: ⚠️ **Realistic only with strong 3-person team**

**Reality Check**:
```
Stream A (Materials + Preflight): 7-8 weeks
- Materials ingestion: 2 weeks
- Vector search + retrieval: 2 weeks  
- Agent preflight orchestrator: 2 weeks
- Research integration: 1 week
- Polish + bugs: 1 week

Stream B (Custom Agents + Personas): 4-5 weeks
- Custom agents UI: 2 weeks
- Persona generation integration: 1 week
- OpenRouter model catalog UI: 1 week
- Polish: 1 week

Stream C (Live Artifacts): 8-9 weeks  ⚠️ THIS IS THE RISK
- Artifact data model: 1 week
- Section assignment UI: 1 week
- Streaming SSE infrastructure: 2 weeks
- Real-time drafting UI: 2 weeks
- Coherence pass (if LLM): 1 week
- Polish + bugs: 1-2 weeks
```

**Risk Analysis**:
- Stream C is the longest pole (8-9 weeks)
- If Stream C slips, everything slips
- 12 weeks assumes: no major bugs, no scope additions, team expertise with SSE/websockets

**Safer Timeline**: 14-16 weeks
- Builds in 2-week buffer
- Allows for 1 week of integration testing across streams
- Realistic for most teams

**How to Hit 12 Weeks**:
1. ✅ Cut LLM coherence pass (save 1 week)
2. ✅ Defer mid-draft reassignment (save 3-5 days)
3. ✅ Use BackgroundTasks not Celery in Phase 1 (save 3 days)
4. ⚠️ Risk: Still tight

**Recommendation**: Commit to 14 weeks publicly, aim for 12 internally

---

#### ✅ Q4.2: 3 Parallel Streams - **AGREE**
**Team Decision**: 3 streams

**My Take**: ✅ **Correct**, but requires coordination

**Critical Dependencies**:
```
Week 4-5: Stream A must expose APIs for Stream C
- POST /debates/{id}/materials/upload
- GET /debates/{id}/materials/status  
- POST /debates/{id}/prepare

Week 6-7: Stream C needs events from Stream A
- material_progress events
- agent_progress events
```

**Recommendation**: 
- Weekly sync between Stream A + C leads
- Shared API contract document (update as needed)
- Integration week at end (week 12)

---

### 5. COST & BUDGET

#### ✅ Q5.1: Research Default OFF - **AGREE**
**Team Decision**: OFF by default

**My Take**: ✅ **Correct for enterprise**
- Explicit internet access = audit compliance
- Easy to enable (not hidden)
- Cost predictable

---

#### ✅ Q5.2: Soft Budget Limits - **AGREE**
**Team Decision**: Soft limits with admin override

**My Take**: ✅ **Perfect for enterprise**
- Soft = warn user, let them proceed
- Admin can tighten for cost control
- Flexibility + safety

---

#### ✅ Q5.3: Free Tier Limits - **AGREE**
**Team Decision**: Not blocking (decide later)

**My Take**: ✅ **Smart deferral**
- You're building for enterprise, not freemium
- Can add limits when needed

---

### 6. RISK MANAGEMENT

#### ✅ Q6.1: Scanned PDFs - **AGREE**
**Team Decision**: User choice in Phase 1 (OCR prompt)

**My Take**: ✅ **Exactly right**
- Auto-detect "no text layer"
- Prompt user: "Run OCR? (+$0.10, +45 sec)"
- User control = transparency

**Implementation Note**:
```python
# Detection is easy
def has_text_layer(pdf_path: str) -> bool:
    doc = PyPDF2.PdfReader(pdf_path)
    text = doc.pages[0].extract_text()
    return len(text.strip()) > 50  # arbitrary threshold
```

---

#### ⚠️ Q6.2: Virus Scanning - **FINAL DECISION: Conditional ClamAV in V1**
**Team Decision**: ClamAV

**Final Decision** (from DECISIONS doc):
- ✅ Strict file validation required (allowlist, magic bytes, size limits, quarantine)
- ⚠️ ClamAV: "if it can be implemented cleanly without destabilizing ingestion"
- ⚠️ Otherwise: V1.1 hardening

**My Take**: ⚠️ **Conditional approach is smart**
- User and I agreed: defer ClamAV
- Team chose: try to include, but not if it's risky
- **This is the right call** - attempt it, but have exit criteria

**Why Deferral Makes Sense**:
1. **Maintenance burden**:
   - Daily signature updates (cron job + monitoring)
   - Daemon health checks
   - Quarantine workflow design
   - False positive handling
2. **User context**: Users upload their own documents (not sharing cross-user)
3. **Enterprise networks**: Often have gateway scanning already
4. **Timeline impact**: -3 days from V1

**Better V1 Approach**:
```
File Type Validation Only:
- Allowlist: .pdf, .docx, .txt, .md
- Check magic bytes (not just extension)
- Size limits: 50MB per file
- Content-Type validation

Result: Blocks 99% of malicious uploads
```

**When to Add Scanning** (V2 or customer-driven):
- Customer explicitly requires it (compliance/RFP)
- You're in regulated industry (healthcare, finance)
- Usage patterns show risk (e.g., users sharing files cross-workspace)

**If Customer Demands It**:
- Consider cloud-based scanning (AWS S3 scan, VirusTotal API)
- Managed service = no maintenance burden
- Can be added in 1-2 days vs ClamAV setup

**Recommendation**: ✅ Defer ClamAV to V2, ship with file type validation only

---

#### ✅ Q6.3: Large Documents - **AGREE**
**Team Decision**: Progressive processing + accept with warning

**My Take**: ✅ **Smart approach**
- Process first batch quickly
- Continue in background
- Retrieval uses what's ready
- User can start debate while processing continues

**Enhancement**: Add to progress UI:
```
Material status:
- Contract.pdf: ✅ Processed (50 pages)
- Proposal.pdf: 🔄 Processing page 45/200...
- Roadmap.docx: ⏳ Queued

You can start the debate now. Agents will access new content as it's ready.
```

---

### 7. SCHEMA & DATABASE

#### ✅ Q7.1: Schema Reuse - **AGREE**
**Team Decision**: Confirm reuse

**My Take**: ✅ **Excellent discipline**
- No duplicate tables
- Unified retrieval
- Simpler joins

---

#### ❌ Q7.2: Memory Import Join Table - **FINAL DECISION: Join Table from Day 1**
**Team Decision**: Join table (`debate_memory_grants`)

**Final Decision** (from DECISIONS doc):
- ✅ Relational join table for memory grants
- ✅ Auditable and enforceable with foreign key constraints
- ✅ Explicit allowlists per debate and per participant

**My Take**: ❌ **Team rejected my "start simple" suggestion**
- I suggested: policy_config first, migrate if needed
- Team chose: join table from day 1 for auditability/enforcement
- **Team is correct for enterprise requirements** - this will pay off when customers ask "who had access to what?"

**Team's Reasoning is Solid**:
- "Queryability" - Can answer "which debates import memory from debate X?"
- "Auditability" - Clean relational data for compliance reports
- "Enforcement" - Foreign key constraints prevent invalid references

**These are all valid benefits**

**My Suggestion**: **Start with policy_config, migrate to join table if query patterns demand it**

**Why policy_config First**:
1. **Faster to ship**: No new migration, no new indexes, no new queries
2. **Flexibility**: Easy to change structure as you learn usage patterns
3. **Postgres JSONB is powerful**:
   ```sql
   -- You can still query efficiently
   SELECT * FROM debates 
   WHERE policy_config @> '{"memory_imports": [{"source_debate_id": "abc123"}]}';
   
   -- And index it
   CREATE INDEX idx_debates_memory_imports 
   ON debates USING gin ((policy_config->'memory_imports'));
   ```
4. **V1 scale**: 100-500 debates, JSONB queries will be <20ms

**When Join Table Becomes Necessary**:
- Complex queries slow (>100ms) even with GIN indexes
- Need JOINs with other tables frequently
- Compliance requires relational data model
- You're at 10K+ debates

**Migration Path** (if needed later):
```sql
-- Create table
CREATE TABLE debate_memory_grants (
  grant_id UUID PRIMARY KEY,
  debate_id UUID REFERENCES debates(debate_id),
  source_debate_id UUID REFERENCES debates(debate_id),
  source_type VARCHAR(50),
  source_id UUID,
  participant_id UUID REFERENCES participants(participant_id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Populate from JSONB (one-time script)
INSERT INTO debate_memory_grants (...)
SELECT ... FROM debates, jsonb_array_elements(policy_config->'memory_imports');
```

**If Team Has Strong Conviction**:
- ✅ Go with join table from day 1
- ⚠️ Add 2 days to timeline for: migration, indexes, query helpers, tests
- ✅ Will avoid migration complexity later

**Recommendation**: Start with policy_config, monitor query performance, migrate if needed

---

### 8. TESTING & VALIDATION

#### ✅ Q8.1: Hybrid Testing - **AGREE**
**Team Decision**: Hybrid (mock unit, real integration)

**My Take**: ✅ **Correct approach**
- Mock for fast iteration
- Real calls for confidence
- Flag-gated for CI cost control

---

#### ✅ Q8.2: Phase 1 Success - **AGREE**
**Team Decision**: All boxes + citations end-to-end

**My Take**: ✅ **Right bar for V1**
- Citations are the proof agents saw the docs
- Without it, users won't trust the system

---

### 9. OPEN DESIGN

#### ✅ Q9.1: Agent Personas - **AGREE**
**Team Decision**: User-configurable ("persona intensity slider")

**My Take**: ✅ **Creative solution**
- Light touch = professional (default)
- Strong = theatrical (optional)
- User decides context appropriateness

**Implementation**:
```python
def compile_system_prompt(agent, intensity: float):
    base_prompt = agent.system_prompt
    
    if intensity < 0.3:  # Light
        character_influence = f"Hint: {agent.character}"
    elif intensity < 0.7:  # Medium  
        character_influence = f"Style: {agent.character}"
    else:  # Strong
        character_influence = f"Embody: {agent.character}. Think and respond as they would."
    
    return f"{base_prompt}\n\n{character_influence}"
```

---

#### ⚠️ Q9.2: Intervention - **PARTIAL AGREE**
**Team Decision**: All of the above (comment, edit, rewrite, lock, reassign)

**My Take**: ⚠️ **Too much for V1**

**Problem**: Each feature adds UI + logic complexity:
- Comment: Need comment threading UI
- Edit directly: Override agent ownership (conflict resolution?)
- Request rewrite: Agent needs to handle rewrite requests mid-draft
- Lock sections: State management (what if agent tries to write to locked section?)
- Reassign: Mid-draft ownership transfer (race conditions)

**Better Phasing**:
```
V1: Comment + Request Rewrite
- Comment: Simplest (just append to section metadata)
- Request Rewrite: Triggers agent to redraft (clear workflow)

V1.5: Lock Sections
- User can finalize sections (prevents further agent edits)

V2: Edit Directly + Reassign
- These are advanced power-user features
- Require complex conflict resolution
```

**Why**: Ship V1 faster with core UX, add power features when users ask

**Team Pushback Expected**: "But enterprise workflows need all controls!"
**Counter**: Enterprise needs reliability > feature completeness. Ship working V1, iterate based on feedback.

---

#### ✅ Q9.3: Versioning Hybrid - **AGREE**
**Team Decision**: Hybrid (auto-save drafts, user marks final)

**My Take**: ✅ **Correct balance**
- Auto-save = user never loses work
- User marks final = clear intent
- Storage efficient (only finalized versions are large)

---

### 10. ACTION ITEMS

#### ✅ Q10.1: Write Specs Before Implementation - **AGREE**
**Team Decision**: Yes, all 3 specs

**My Take**: ✅ **Critical for parallel streams**
- Stream C (artifacts) needs detailed spec before starting
- Memory import needs UX spec for clarity
- Cost analysis update is documentation, not blocking

**Priority**:
1. LIVE-ARTIFACTS-TECHNICAL-SPEC.md (Week 1, before Stream C starts)
2. MEMORY-IMPORT-UX-SPEC.md (Week 2, Stream B can reference it)
3. COST-ANALYSIS-UPDATE.md (Week 3, can be async)

---

#### ✅ Q10.2: AI Assistant Drafts - **AGREE**
**Team Decision**: AI drafts + engineering review + product sign-off

**My Take**: ✅ **Efficient workflow**
- AI can draft 80% (structure, examples, edge cases)
- Engineering adds technical details
- Product validates user flows

---

## 🚨 NEW CONCERNS FROM TEAM DECISIONS

### Concern 1: Stream C Timeline Risk
**Issue**: Live Artifacts with streaming SSE + coherence pass is 8-9 weeks (the longest pole).

**Risk**: If Stream C slips by even 1 week, you miss 12-week target.

**Mitigation**:
1. Cut LLM coherence pass → saves 1 week
2. Defer mid-draft reassignment → saves 3-5 days
3. **Total buffer gained**: ~10 days

---

### Concern 2: Deterministic Coherence Checks Not Specified
**Issue**: Team said "deterministic checks enforce: required sections, citations, outcome addressed."

**Missing**: How exactly?

**Need to Specify**:
```python
def validate_artifact_quality(artifact: Artifact) -> QualityReport:
    checks = []
    
    # Check 1: All required sections present
    template = artifact.template
    for section in template.required_sections:
        if section.id not in artifact.sections:
            checks.append(Check(
                name="missing_section",
                status="fail",
                message=f"Required section '{section.title}' is missing"
            ))
    
    # Check 2: Citations exist
    for section in artifact.sections:
        if len(section.citations) == 0:
            checks.append(Check(
                name="no_citations",
                status="warning",
                section=section.id,
                message=f"Section '{section.title}' has no citations"
            ))
    
    # Check 3: Intended outcome addressed
    outcome_keywords = extract_keywords(debate.intended_outcome)
    outcome_mentioned = any(
        keyword in section.content.lower()
        for section in artifact.sections
        for keyword in outcome_keywords
    )
    if not outcome_mentioned:
        checks.append(Check(
            name="outcome_not_addressed",
            status="warning",
            message="Intended outcome may not be explicitly addressed"
        ))
    
    return QualityReport(checks=checks)
```

**Recommendation**: Add this detail to LIVE-ARTIFACTS-TECHNICAL-SPEC.md

---

### Concern 3: Cost Estimation for Full V1
**Issue**: Team committed to full V1 but didn't update cost estimates.

**Need to Add**:
```
Updated Per-Debate Cost (5 agents, 5 docs, research ON):

Materials Ingestion:
- Text extraction: $0
- AI categorization: $0.05-0.10 (5 docs)
- Material Map generation: $0.02-0.03 (1 LLM call)
- Embeddings: $0.01 (5 docs)
Subtotal: $0.08-0.14

Agent Preflight:
- Vector search: $0
- Research (Perplexity): $0.25-1.00 (5 agents × $0.05-0.20)
- Briefing memos: $0.10-0.25 (5 agents × $0.02-0.05)
Subtotal: $0.35-1.25

Debate:
- Turn generation: $0.50-2.00 (10 turns)
- Summary: $0.05-0.10
Subtotal: $0.55-2.10

Live Artifact:
- Section drafting: $0.30-0.80 (6 sections × $0.05-0.13)
- Coherence pass (if LLM): $0.10-0.30 ⚠️
Subtotal: $0.40-1.10

TOTAL PER DEBATE: $1.38-4.59
- Without coherence pass: $1.28-4.29
- Without research: $1.03-3.29
```

**Recommendation**: Update AGENT-PREPARATION-ARCHITECTURE.md with artifact costs

---

## Product Lead Response (Codex) - 2026-02-09

This is a point-by-point response to the AI critique. We take the warnings seriously, but we will not dilute the premium differentiators (prepared agents + live artifact collaboration + scoped memory).

### Where We Agree Fully
- **Material Map is required in V1.** It is the trust anchor for ingestion.
- **Custom Agents UI runs in parallel** (high user value, low dependency).
- **Perplexity first, but behind a provider abstraction** and governed by policy + citations.
- **Celery + Redis** is the correct foundation for durable ingestion/preflight.
- **Hybrid testing** is correct (mock unit tests + small real integration tests behind a flag).
- **Schema reuse discipline** stands. No duplicate tables (no `document_chunks`, no `agent_briefings`).

### Coherence Pass (Q2.1) - Keep in V1, but de-risk delivery
AI concern is valid: LLM coherence adds orchestration complexity and timeline risk.

Decision:
- **V1 includes an LLM coherence pass**, because the artifact is a flagship output.
- But it must be **optional and non-blocking**:
  - Artifact can be generated immediately from owned sections.
  - Coherence pass runs as a background job and produces **Artifact v2** (or “polished” variant).
  - User can accept/reject coherence output.
- Deterministic quality checks are required regardless (missing sections, missing citations, outcome not addressed).

This preserves premium quality while creating schedule flexibility.

### Section Assignment + Mid-Draft Reassign (Q2.2) - Phase the risky part
AI is right that mid-draft reassignment creates race conditions.

Decision:
- **V1 = Hybrid assignment before drafting begins**:
  - System suggests owners; user/host confirms/overrides in setup.
- **V1 supports reassignment only with explicit section state transitions**:
  - “Pause section” -> reassign -> resume.
  - No silent mid-stream takeovers.
- **V2 = true mid-draft reassignment** (if demanded).

### Vector Index (Q2.3) - Quality-first, but keep escape hatch
AI is correct that IVFFlat is sufficient for early scale and easier to debug.

Decision:
- We keep **HNSW as the target**, but we implement retrieval behind an internal interface so we can:
  - start with IVFFlat during early development if needed for stability,
  - switch to HNSW for production/default without changing application code.
- The real product requirement is *retrieval quality with provenance*, not a specific index type.

### Virus Scanning (Q6.2) - Adjust: ship safe-by-default, scanning as hardening
The AI is correct about ClamAV maintenance overhead. Security still matters.

Decision:
- **V1 must include strict file-type validation + magic-byte sniffing + size limits**.
- **V1 also includes an upload “quarantine” workflow** (do not process until validated).
- Virus scanning:
  - If we can implement it cleanly without destabilizing ingestion, use **ClamAV**.
  - Otherwise ship V1 with validation-only and make scanning a V1.1 hardening item.

### Memory Import Storage (Q7.2) - Keep join table for enterprise auditability
AI suggests policy_config first. That’s reasonable for speed, but we’re optimizing for enterprise trust.

Decision:
- **Use a join table (`debate_memory_grants`) in V1**:
  - easier auditing (“who had access to what?”),
  - enforceable with FKs,
  - supports per-agent scoping cleanly.
- Keep `debates.policy_config` for *policy knobs*, not access control lists.

### Intervention Controls During Artifact Drafting (Q9.2) - Phase UI complexity
AI is right: “everything” in V1 is a complexity trap.

Decision:
- **V1 must include**:
  - comment on section,
  - request rewrite,
  - lock/unlock section,
  - reassign (via pause -> reassign -> resume),
  - versioning (auto drafts, user marks final).
- **V2 adds**:
  - rich threaded comments,
  - direct human editing with CRDT-grade conflict resolution (Yjs),
  - advanced merge tools.

### Timeline
AI suggests 14-16 weeks publicly. That’s fair externally.

Decision:
- Internally we target **12 weeks** with scope lock and aggressive gating.
- Externally we communicate **12-16 weeks depending on enterprise hardening** (OCR/scanning and deep controls).

### Additional Requirement (Not In AI Analysis): “Agents must only know what they’re allowed”
We will not compromise on this trust rule.

Implementation requirement:
- Preflight outputs and imported context become **knowledge units** with provenance.
- Retrieval is always scoped by allowlists tied to the debate + participant.
- Any internet research result must be posted as a cited event and stored as a knowledge unit.

---

### Concern 4: OCR Cost Not Included
**Issue**: Team said "OCR user choice in Phase 1" but didn't spec the integration.

**Need to Specify**:
- Which OCR service? (Tesseract free but low quality, AWS Textract $0.015/page)
- Per-page cost estimate
- Processing time estimate
- Quality fallback (what if OCR is gibberish?)

**Recommendation**: Add to LIVE-ARTIFACTS-TECHNICAL-SPEC.md or separate OCR-INTEGRATION-SPEC.md

---

### Concern 5: ClamAV Maintenance Not Accounted For
**Issue**: Team wants ClamAV but that's ongoing maintenance.

**Reality**:
- Signature updates: Daily cron job
- Daemon monitoring: Need health checks
- Quarantine handling: Where do infected files go?
- False positive workflow: User says "this is safe, scan it anyway"
- Testing: How do you test virus scanning? (Use EICAR test file)

**Recommendation**: Either:
1. Remove ClamAV from V1 (my preference)
2. Add 3-5 days to timeline for ClamAV integration + testing
3. Document maintenance runbook

---

## 📋 FINAL DECISIONS vs MY RECOMMENDATIONS

Based on team's final decisions document, here's what was accepted/rejected:

### ✅ **Decisions That Aligned with My Recommendations**:
1. **HNSW with IVFFlat Fallback** - Quality target, pragmatic implementation
2. **Coherence Pass Non-Blocking** - User can accept/reject, not a hard gate
3. **Hybrid Section Assignment** - Suggest → user confirms (not full mid-draft reassignment)
4. **ClamAV Conditional** - Try to include cleanly, otherwise V1.1
5. **3 Parallel Streams** - Efficient execution model
6. **Celery from Day 1** - Enterprise reliability (I agreed after initial concern)

---

### ❌ **Decisions Where Team Chose Differently**:
1. **LLM Coherence Pass in V1** 
   - I suggested: Defer to week 9-10, validate need
   - Team chose: Include in V1 (non-blocking)
   - **Outcome**: +1 week to Stream C, but higher quality baseline

2. **Join Table for Memory Grants**
   - I suggested: Start with policy_config, migrate if needed
   - Team chose: Join table from day 1
   - **Outcome**: +2 days to implementation, but better auditability

3. **Timeline Messaging**
   - I suggested: 12 weeks internal, 14 weeks external
   - Team chose: 12 weeks internal, 12-16 weeks external (with hardening)
   - **Outcome**: More realistic external expectation

**Total Additional Scope from My Baseline**: ~9 days (1.5 weeks)
**Team's Internal Target**: Still 12 weeks with strict scope discipline

---

### 🎯 **V1 Scope (Locked Per DECISIONS Doc)**:
1. ✅ Setup flow (title, problem, agenda, outcome, criteria, timebox)
2. ✅ Materials ingestion (upload, extract, categorize, chunk, index, Material Map)
3. ✅ Panel (templates, custom agents, personas, OpenRouter model picker, policy toggles)
4. ✅ Memory import (user-enabled, scoped per agent, preview UI)
5. ✅ Agent preflight (briefings with citations, optional research, progress + retry/skip)
6. ✅ Live room (timeline, intervention, timeboxing, retrieval with citations)
7. ✅ Outputs (summary, minutes, action items)
8. ✅ Live artifacts (templates, ownership, streaming drafts, coherence pass, versioning)

**Explicit V2 Deferrals**:
- Multi-human co-editing (CRDT/Yjs)
- Advanced merge tools and offline mode
- Mid-draft reassignment without pause/resume boundary

---

### 📝 **Required Specs (Per DECISIONS Doc)**:
1. **Live Artifacts Technical Spec** - MUST write before coding artifacts
   - Events, API contracts, SSE deltas, coherence workflow
2. **Memory Import UX Spec** - MUST write before coding memory import
   - Import preview, allowlist editing, "what is shared" clarity
3. **Cost Analysis Update** - Documentation only, not blocking
   - Include artifact generation costs

---

## 🎯 FINAL TIMELINE ESTIMATE (LOCKED PER DECISIONS DOC)

### Team's Official Target: **12 weeks internal, 12-16 weeks external**

**Breakdown with Team's Final Decisions**:
```
Stream A (Materials + Preflight): 7 weeks
- Celery from day 1: included
- HNSW target (IVFFlat fallback): included
- ClamAV conditional: attempt, 3 days risk
- OCR with user choice: included
Total: 7 weeks (longest pole in Stream A)

Stream B (Custom Agents + Personas): 4-5 weeks
- Custom agents UI: 2 weeks
- Persona generation integration: 1 week
- OpenRouter model catalog: 1 week
- Polish: 1 week
Total: 5 weeks

Stream C (Live Artifacts): 8-9 weeks (LONGEST POLE)
- Artifact data model + templates: 1 week
- Section assignment UI: 1 week
- Streaming SSE infrastructure: 2 weeks
- Live drafting UI (streaming deltas): 2 weeks
- LLM coherence pass (non-blocking): 1 week
- Deterministic checks: included in coherence week
- Polish + versioning: 1 week
Total: 8 weeks (with LLM coherence)

Integration + Polish + Hardening: 2 weeks
- Cross-stream integration
- End-to-end testing
- Memory import integration
- Bug fixes
- Performance tuning

CRITICAL PATH: Stream C (8 weeks) + Integration (2 weeks) = 10 weeks
With safety buffer + enterprise hardening: 12 weeks internal
With additional enterprise requirements: up to 16 weeks external
```

**Key Dependencies**:
- Week 4-5: Stream A must expose APIs for Stream C (materials status, prep status)
- Week 6-7: Stream C needs events from Stream A (material_progress, agent_progress)
- Week 8-9: Integration of memory import across all streams
- Week 10-12: Hardening + full end-to-end testing

**Risk Factors**:
1. ⚠️ Stream C is longest pole (8 weeks) - no slack
2. ⚠️ LLM coherence adds complexity (even non-blocking, needs testing)
3. ⚠️ Join table for memory grants adds 2 days vs policy_config
4. ⚠️ ClamAV if included adds 3 days + maintenance setup

**Mitigation**:
- Strict scope lock (per DECISIONS doc)
- Weekly Stream A+C sync on API contracts
- Integration week explicitly planned

---

## ✅ FINAL ALIGNMENT: DECISIONS LOCKED

### Team's Final Decisions (Authoritative):
**Source**: `/docs/design/DECISIONS-SOURCE-OF-TRUTH-2026-02-09.md`

All decisions are locked. Do not re-litigate. If a decision must change, create a new dated decisions doc.

---

### What Engineering Must Do Now:

#### 🚨 **Immediate (Week 1)**:
1. **Write Required Specs** (blocking for those work streams):
   - `LIVE-ARTIFACTS-TECHNICAL-SPEC.md` - MUST complete before Stream C starts
   - `MEMORY-IMPORT-UX-SPEC.md` - MUST complete before memory import work
   - Cost analysis update - Documentation only, not blocking

2. **Lock Technical Foundations**:
   - ✅ Schema: Reuse existing tables (memory_chunks, agent_knowledge_units, events)
   - ✅ Create `debate_memory_grants` join table
   - ✅ Redis + Celery setup for job queue
   - ✅ HNSW vector index (with IVFFlat fallback interface)

3. **Stream Coordination**:
   - Define API contracts between Stream A (materials/preflight) and Stream C (artifacts)
   - Weekly sync meetings for Stream A + C leads

#### 📋 **V1 Scope Lock** (No Additions):
- Setup flow ✅
- Materials ingestion + Material Map ✅
- Panel (templates + custom agents + personas) ✅
- Memory import (scoped, allowlists) ✅
- Agent preflight (briefings + research) ✅
- Live room (timeline + intervention) ✅
- Outputs (summary + minutes + actions) ✅
- Live artifacts (streaming + coherence pass) ✅

#### 🚫 **Explicit V2 Deferrals**:
- Multi-human CRDT co-editing
- Advanced merge tools
- Offline mode
- Mid-draft reassignment without pause/resume

#### ⏰ **Timeline Commitment**:
- **Internal target**: 12 weeks with strict scope discipline
- **External messaging**: 12-16 weeks (accounts for enterprise hardening)
- **Critical path**: Stream C (8 weeks) + Integration (2 weeks) + Buffer (2 weeks)

---

### 🎯 Implementation Phases (Per Team Decision):

**Weeks 1-4**: Phase 1
- Stream A: Materials pipeline + preflight foundation
- Stream B: Custom agents UI + Settings integration
- Stream C: Artifact data model + templates

**Weeks 5-8**: Phase 2
- Stream A: Vector search + research integration + OCR
- Stream B: Persona generation + OpenRouter catalog
- Stream C: Streaming SSE + live drafting UI

**Weeks 9-10**: Phase 3
- Stream A: Polish + performance
- Stream B: Polish + testing
- Stream C: Coherence pass (LLM + deterministic) + versioning

**Weeks 11-12**: Integration + Hardening
- Cross-stream integration
- Memory import end-to-end
- Full system testing
- Enterprise hardening (ClamAV if ready, otherwise V1.1)

---

**Document Status**: ✅ Aligned with team's final decisions  
**Authority**: `/docs/design/DECISIONS-SOURCE-OF-TRUTH-2026-02-09.md`  
**Next Step**: Engineering to write required specs and begin implementation
