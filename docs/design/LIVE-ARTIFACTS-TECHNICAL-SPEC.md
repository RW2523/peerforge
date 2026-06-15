# Live Artifacts - Technical Specification

**Date:** 2026-02-09  
**Status:** Draft (Ready for Engineering Review)  
**Authority:** `/docs/design/DECISIONS-SOURCE-OF-TRUTH-2026-02-09.md`  
**Related:** `/docs/product/MEETING-FLOW-MEMORY-ARTIFACTS.md`
**Realtime Plan:** `arinar-v2/docs/design/WEBSOCKET-ROOM-AND-LIVE-BOARD-PLAN.md`

---

## Executive Summary

Live Artifacts enable AI agents to collaboratively draft structured deliverables (PRDs, briefs, memos) in real-time with section ownership, streaming updates, and coherence validation. This is the flagship "Figma-like" feature that differentiates Arinar from chat-based AI tools.

Long-context note: artifact drafting is implemented as an **RLM-style** multi-pass workflow (plan -> retrieve slices -> draft sections -> coherence/merge), rather than attempting to “fit the whole meeting” into a single prompt. See: `arinar-v2/docs/design/RLM-APPLICATION-TO-ARINAR.md`.

**V1 Scope** (This Spec):
- ✅ Templates with section definitions
- ✅ Section ownership and assignment
- ✅ Streaming drafts via WebSocket (agents "type" live)
- ✅ Coherence pass (LLM + deterministic checks, non-blocking)
- ✅ Versioning (draft auto-save + user-marked final versions)
- ✅ User interventions (comment, request rewrite, lock section)
- ❌ Deferred to V2: Multi-human CRDT co-editing, mid-draft reassignment without pause

---

## Table of Contents

1. [Data Model](#data-model)
2. [API Contracts](#api-contracts)
3. [WebSocket Event Types](#websocket-event-types)
4. [Block Types & Rendering](#block-types--rendering)
5. [Quality Checks](#quality-checks)
6. [Coherence Pass Workflow](#coherence-pass-workflow)
7. [User Interventions](#user-interventions)
8. [Export Formats](#export-formats)
9. [Edge Cases](#edge-cases)
10. [Non-Goals](#non-goals)

---

## Data Model

### No Duplicate Storage (Reuse Existing Tables)

Per DECISIONS doc: Reuse `events`, `memory_chunks`, `agent_knowledge_units`.

### Primary Storage

#### 1. **Artifacts Metadata** (New Minimal Table)
```sql
CREATE TABLE artifacts (
    artifact_id UUID PRIMARY KEY,
    debate_id UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    template_id VARCHAR(100) NOT NULL,  -- e.g. "prd", "brief", "memo"
    title TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(50) NOT NULL,  -- 'drafting', 'review', 'final'
    quality_report JSONB,  -- Deterministic checks result
    coherence_version_id UUID,  -- Links to polished version if coherence pass ran
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    finalized_at TIMESTAMPTZ,
    UNIQUE(debate_id, version)
);

CREATE INDEX idx_artifacts_debate ON artifacts(debate_id);
CREATE INDEX idx_artifacts_status ON artifacts(status);
```

#### 2. **Sections** (Stored as Knowledge Units)
Sections are stored in `agent_knowledge_units` with special metadata:

```json
// agent_knowledge_units row for a section
{
  "knowledge_id": "uuid",
  "agent_id": "owner_agent_id",
  "source_debate_id": "debate_id",
  "content": "Section text content (rich text JSON or markdown)",
  "metadata": {
    "type": "artifact_section",
    "artifact_id": "uuid",
    "section_id": "goals",  // From template
    "section_title": "Goals",
    "block_type": "rich_text",
    "owner_participant_id": "uuid",
    "status": "committed",  // 'drafting', 'review', 'committed', 'locked'
    "version": 1,
    "citations": [
      {"type": "event", "event_id": "uuid"},
      {"type": "material_chunk", "chunk_id": "uuid"},
      {"type": "web", "url": "https://...", "retrieved_at": "..."}
    ],
    "word_count": 240,
    "quality_flags": ["missing_citations", "outcome_addressed"]
  },
  "created_at": "...",
  "updated_at": "..."
}
```

**Why This Works**:
- ✅ Searchable (existing memory retrieval)
- ✅ Auditable (memory_access_log)
- ✅ Versionable (create new knowledge unit per version)
- ✅ No duplicate storage system

#### 3. **Section Drafting Deltas** (Stored in Events)
Real-time updates are stored in `events` table:

```json
// Event type: artifact_section_delta
{
  "event_id": "uuid",
  "debate_id": "uuid",
  "event_type": "artifact_section_delta",
  "created_at": "...",
  "payload": {
    "artifact_id": "uuid",
    "section_id": "goals",
    "owner_participant_id": "uuid",
    "delta_type": "append",  // 'append', 'replace', 'insert', 'delete'
    "content": "New text being added...",
    "position": 0,  // For insert operations
    "length": 25  // For delete operations
  }
}
```

---

## API Contracts

### Artifact Lifecycle Endpoints

#### **POST /debates/{debate_id}/artifacts**
Create artifact from template.

**Request**:
```json
{
  "template_id": "prd",
  "title": "Q1 Product Roadmap",
  "section_assignments": [
    {
      "section_id": "goals",
      "owner_participant_id": "uuid",
      "reviewer_participant_ids": ["uuid", "uuid"]
    },
    {
      "section_id": "risks",
      "owner_participant_id": "uuid"
    }
  ]
}
```

**Response** (201):
```json
{
  "artifact_id": "uuid",
  "template_id": "prd",
  "title": "Q1 Product Roadmap",
  "status": "drafting",
  "sections": [
    {
      "section_id": "goals",
      "title": "Goals",
      "required": true,
      "owner_participant_id": "uuid",
      "owner_name": "Senior PM",
      "status": "pending"
    },
    {
      "section_id": "risks",
      "title": "Risks & Mitigations",
      "required": true,
      "owner_participant_id": "uuid",
      "owner_name": "Legal Counsel",
      "status": "pending"
    }
  ],
  "created_at": "2026-02-09T20:00:00Z"
}
```

---

#### **GET /debates/{debate_id}/artifacts/{artifact_id}**
Get current artifact state.

**Response** (200):
```json
{
  "artifact_id": "uuid",
  "debate_id": "uuid",
  "template_id": "prd",
  "title": "Q1 Product Roadmap",
  "version": 1,
  "status": "drafting",
  "sections": [
    {
      "section_id": "goals",
      "title": "Goals",
      "owner_participant_id": "uuid",
      "owner_name": "Senior PM (Visionary)",
      "status": "committed",
      "content": [
        {
          "type": "rich_text",
          "text": "Our Q1 goals are to...",
          "citations": [
            {"type": "material_chunk", "chunk_id": "uuid", "title": "Market Research"}
          ]
        }
      ],
      "word_count": 240,
      "last_updated": "2026-02-09T20:15:30Z"
    },
    {
      "section_id": "risks",
      "title": "Risks & Mitigations",
      "owner_participant_id": "uuid",
      "owner_name": "Legal Counsel",
      "status": "drafting",
      "content": [],
      "presence": {
        "participant_id": "uuid",
        "activity": "drafting",
        "last_seen": "2026-02-09T20:16:00Z"
      }
    }
  ],
  "quality_report": {
    "checks": [
      {"name": "required_sections", "status": "pass"},
      {"name": "citations_present", "status": "warning", "details": "Section 'risks' has no citations"},
      {"name": "outcome_addressed", "status": "pass"}
    ],
    "overall": "warning"
  },
  "created_at": "2026-02-09T20:00:00Z",
  "updated_at": "2026-02-09T20:16:00Z"
}
```

---

#### **POST /debates/{debate_id}/artifacts/{artifact_id}/sections/{section_id}/commit**
Agent commits a section draft.

**Request**:
```json
{
  "participant_id": "uuid",
  "content": [
    {
      "type": "rich_text",
      "text": "Our primary goals for Q1 are...",
      "citations": [
        {"type": "material_chunk", "chunk_id": "uuid"},
        {"type": "event", "event_id": "uuid"}
      ]
    }
  ]
}
```

**Response** (200):
```json
{
  "section_id": "goals",
  "status": "committed",
  "knowledge_id": "uuid",  // Points to agent_knowledge_units row
  "committed_at": "2026-02-09T20:17:00Z"
}
```

**Behavior**:
- Creates `agent_knowledge_units` row with section content
- Emits `artifact_section_committed` WebSocket event
- Updates artifact `updated_at` timestamp

---

#### **POST /debates/{debate_id}/artifacts/{artifact_id}/sections/{section_id}/rewrite**
User requests section rewrite.

**Request**:
```json
{
  "feedback": "Focus more on risks, less on opportunities",
  "requested_by": "operator"
}
```

**Response** (202):
```json
{
  "rewrite_job_id": "uuid",
  "estimated_duration_seconds": 30,
  "status": "queued"
}
```

**Behavior**:
- Queues rewrite task (Celery)
- Agent redrafts section
- Emits new `artifact_section_delta` events as redrafting
- Emits `artifact_section_committed` when done

---

#### **POST /debates/{debate_id}/artifacts/{artifact_id}/sections/{section_id}/lock**
Lock section to prevent further agent edits.

**Request**:
```json
{
  "locked_by": "operator",
  "reason": "Approved by stakeholders"
}
```

**Response** (200):
```json
{
  "section_id": "goals",
  "status": "locked",
  "locked_at": "2026-02-09T20:20:00Z"
}
```

---

#### **POST /debates/{debate_id}/artifacts/{artifact_id}/coherence**
Run coherence pass (non-blocking).

**Request**:
```json
{
  "openrouter_api_key": "sk-or-...",  // BYOK
  "model_id": "anthropic/claude-3.5-sonnet",
  "pass_type": "full"  // 'full' or 'deterministic_only'
}
```

**Response** (202):
```json
{
  "coherence_job_id": "uuid",
  "estimated_duration_seconds": 45,
  "status": "processing"
}
```

**Behavior**:
- Runs deterministic checks first
- If `pass_type: "full"`, LLM reviews all sections for:
  - Tone consistency
  - Contradiction removal
  - Terminology unification
  - Transition smoothness
- Creates new artifact version (version+1) with polished content
- User can accept/reject polished version

---

#### **GET /debates/{debate_id}/artifacts/{artifact_id}/coherence/{job_id}/status**
Check coherence pass status.

**Response** (200):
```json
{
  "job_id": "uuid",
  "status": "complete",  // 'queued', 'processing', 'complete', 'failed'
  "result": {
    "polished_artifact_id": "uuid",
    "changes_made": [
      {"section_id": "goals", "change_type": "tone_adjustment", "description": "Unified voice from first-person to third-person"},
      {"section_id": "risks", "change_type": "contradiction_removed", "description": "Removed conflicting risk assessment"}
    ],
    "quality_improvement": {
      "before": {"citations": 8, "contradictions": 2, "tone_consistency": "medium"},
      "after": {"citations": 8, "contradictions": 0, "tone_consistency": "high"}
    }
  },
  "completed_at": "2026-02-09T20:22:00Z"
}
```

---

#### **POST /debates/{debate_id}/artifacts/{artifact_id}/accept-coherence**
User accepts polished version.

**Request**:
```json
{
  "coherence_job_id": "uuid"
}
```

**Response** (200):
```json
{
  "artifact_id": "uuid",  // Now points to polished version
  "version": 2,
  "status": "final"
}
```

---

#### **POST /debates/{debate_id}/artifacts/{artifact_id}/export**
Export artifact to PDF or DOCX.

**Request**:
```json
{
  "format": "pdf",  // 'pdf' or 'docx'
  "include_citations": true,
  "include_metadata": true
}
```

**Response** (200):
```json
{
  "export_url": "https://storage.../artifacts/uuid/export.pdf",
  "expires_at": "2026-02-10T20:00:00Z"
}
```

---

## WebSocket Event Types

### **artifact_section_delta**
Streamed as agent drafts section content.

Transport envelope:
- Event payloads are sent over `/ws/debates/{debate_id}`.
- Every event must include debate-scoped ordering (`sequence_number`) and an `event_id`.

**JSON Schema** (to be added to `packages/contracts/schemas/events/`):
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "artifact_section_delta",
  "type": "object",
  "required": ["artifact_id", "section_id", "owner_participant_id", "delta_type", "content"],
  "properties": {
    "artifact_id": {"type": "string", "format": "uuid"},
    "section_id": {"type": "string"},
    "owner_participant_id": {"type": "string", "format": "uuid"},
    "delta_type": {
      "type": "string",
      "enum": ["append", "replace", "insert", "delete"]
    },
    "content": {"type": "string"},
    "position": {"type": "integer"},
    "length": {"type": "integer"},
    "timestamp": {"type": "string", "format": "date-time"}
  }
}
```

**UI Behavior**:
- Append deltas to section content in real-time
- Show "typing" indicator for owner agent
- Smooth scroll to keep latest content visible

---

### **artifact_section_committed**
Emitted when agent finalizes a section.

**JSON Schema**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "artifact_section_committed",
  "type": "object",
  "required": ["artifact_id", "section_id", "owner_participant_id", "knowledge_id"],
  "properties": {
    "artifact_id": {"type": "string", "format": "uuid"},
    "section_id": {"type": "string"},
    "owner_participant_id": {"type": "string", "format": "uuid"},
    "knowledge_id": {"type": "string", "format": "uuid"},
    "word_count": {"type": "integer"},
    "citation_count": {"type": "integer"},
    "committed_at": {"type": "string", "format": "date-time"}
  }
}
```

**UI Behavior**:
- Stop showing "typing" indicator
- Mark section as "committed" (checkmark)
- Enable "Request Rewrite" button

---

### **artifact_presence**
Agent activity indicator (who is working on what).

**JSON Schema**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "artifact_presence",
  "type": "object",
  "required": ["artifact_id", "participant_id", "activity"],
  "properties": {
    "artifact_id": {"type": "string", "format": "uuid"},
    "section_id": {"type": "string"},
    "participant_id": {"type": "string", "format": "uuid"},
    "participant_name": {"type": "string"},
    "activity": {
      "type": "string",
      "enum": ["drafting", "reviewing", "idle"]
    },
    "last_seen": {"type": "string", "format": "date-time"}
  }
}
```

**UI Behavior**:
- Show agent avatar/name next to section being drafted
- "Legal Counsel is drafting Risks..." status text
- Fade out after 30 seconds of inactivity

---

### **artifact_quality_report**
Emitted after deterministic quality checks run.

**JSON Schema**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "artifact_quality_report",
  "type": "object",
  "required": ["artifact_id", "checks", "overall"],
  "properties": {
    "artifact_id": {"type": "string", "format": "uuid"},
    "checks": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "status"],
        "properties": {
          "name": {"type": "string"},
          "status": {"type": "string", "enum": ["pass", "warning", "fail"]},
          "section_id": {"type": "string"},
          "message": {"type": "string"}
        }
      }
    },
    "overall": {"type": "string", "enum": ["pass", "warning", "fail"]},
    "generated_at": {"type": "string", "format": "date-time"}
  }
}
```

**UI Behavior**:
- Display quality report in right panel
- Highlight sections with warnings/failures
- Block finalization if overall = "fail"

---

## Block Types & Rendering

Sections contain blocks (rich content units).

### **Supported Block Types (V1)**

#### 1. **rich_text**
```json
{
  "type": "rich_text",
  "text": "Our primary goal is to increase user engagement by 30%.",
  "formatting": ["bold", "italic"],  // Optional
  "citations": [
    {"type": "material_chunk", "chunk_id": "uuid", "title": "User Research Q4"}
  ]
}
```

**Rendering**: Standard markdown + citation links

---

#### 2. **diagram_mermaid**
```json
{
  "type": "diagram_mermaid",
  "title": "System Architecture",
  "mermaid_code": "graph TD\n  A[User] --> B[API]\n  B --> C[Database]",
  "citations": []
}
```

**Rendering**: Use mermaid.js to render diagram

---

#### 3. **table**
```json
{
  "type": "table",
  "title": "Q1 Milestones",
  "headers": ["Milestone", "Owner", "Due Date", "Status"],
  "rows": [
    ["Beta Launch", "PM", "2026-03-15", "On Track"],
    ["Security Audit", "Legal", "2026-03-01", "Complete"]
  ],
  "citations": [
    {"type": "event", "event_id": "uuid"}
  ]
}
```

**Rendering**: HTML table with citations footer

---

#### 4. **chart**
```json
{
  "type": "chart",
  "chart_type": "bar",  // 'bar', 'line', 'pie'
  "title": "Revenue Projections",
  "data": {
    "labels": ["Q1", "Q2", "Q3", "Q4"],
    "datasets": [
      {
        "label": "Projected",
        "values": [100, 150, 200, 300],
        "color": "#58A6FF"
      }
    ]
  },
  "citations": [
    {"type": "material_chunk", "chunk_id": "uuid", "title": "Financial Model"}
  ]
}
```

**Rendering**: Use Chart.js or similar library

**Validation Rules**:
- Max 5 datasets per chart
- Max 20 data points per dataset
- Labels and values must match length

---

## Quality Checks

### Deterministic Checks (Always Run)

#### 1. **Required Sections Present**
```python
def check_required_sections(artifact: Artifact, template: Template) -> Check:
    """Ensure all required sections have content"""
    missing = []
    for section_def in template.sections:
        if section_def.required:
            section = artifact.get_section(section_def.section_id)
            if not section or not section.content:
                missing.append(section_def.title)
    
    if missing:
        return Check(
            name="required_sections",
            status="fail",
            message=f"Missing required sections: {', '.join(missing)}"
        )
    return Check(name="required_sections", status="pass")
```

---

#### 2. **Citations Present**
```python
def check_citations(artifact: Artifact) -> List[Check]:
    """Warn if sections lack citations"""
    checks = []
    for section in artifact.sections:
        citation_count = sum(
            len(block.citations) 
            for block in section.content 
            if hasattr(block, 'citations')
        )
        
        if citation_count == 0:
            checks.append(Check(
                name="citations_present",
                status="warning",
                section_id=section.section_id,
                message=f"Section '{section.title}' has no citations"
            ))
    
    if not checks:
        return [Check(name="citations_present", status="pass")]
    return checks
```

---

#### 3. **Intended Outcome Addressed**
```python
def check_outcome_addressed(artifact: Artifact, debate: Debate) -> Check:
    """Check if intended outcome is explicitly mentioned"""
    outcome = debate.policy_config.get("intended_outcome", "")
    if not outcome:
        return Check(name="outcome_addressed", status="skip", message="No outcome defined")
    
    # Extract keywords from outcome
    keywords = extract_keywords(outcome)
    
    # Check if any section mentions outcome keywords
    full_text = " ".join(
        block.text.lower() 
        for section in artifact.sections 
        for block in section.content 
        if block.type == "rich_text"
    )
    
    matches = sum(1 for kw in keywords if kw.lower() in full_text)
    coverage = matches / len(keywords) if keywords else 0
    
    if coverage >= 0.5:
        return Check(name="outcome_addressed", status="pass")
    elif coverage > 0:
        return Check(
            name="outcome_addressed", 
            status="warning", 
            message=f"Outcome partially addressed ({int(coverage*100)}% keyword coverage)"
        )
    else:
        return Check(
            name="outcome_addressed", 
            status="warning",
            message="Intended outcome not explicitly mentioned"
        )
```

---

#### 4. **Version Labeling**
```python
def check_version_label(artifact: Artifact) -> Check:
    """Ensure version is properly labeled"""
    if artifact.version == 1 and artifact.status == "drafting":
        return Check(name="version_label", status="pass", message="Draft v1")
    elif artifact.status == "final":
        return Check(name="version_label", status="pass", message=f"Final v{artifact.version}")
    else:
        return Check(name="version_label", status="pass", message=f"Draft v{artifact.version}")
```

---

## Coherence Pass Workflow

### Non-Blocking User Flow

```
User clicks "Run Coherence Pass" in UI
    ↓
POST /artifacts/{id}/coherence (returns job_id)
    ↓
UI polls GET /coherence/{job_id}/status
    ↓
Backend (Celery task):
    1. Run deterministic checks (always)
    2. If pass_type="full":
       - LLM reviews all sections
       - Generates polished version
       - Creates artifact v+1
    ↓
Job complete, UI shows:
    "Coherence pass complete. Review changes."
    [Side-by-side: Original vs Polished]
    [Accept Polished] [Keep Original]
    ↓
User accepts → artifact_id now points to v2
User rejects → stays on v1
```

### LLM Coherence Prompt

```python
async def run_llm_coherence_pass(artifact: Artifact) -> Artifact:
    """Generate polished version via LLM"""
    
    sections_text = "\n\n".join([
        f"## {section.title}\n{section.get_text()}"
        for section in artifact.sections
    ])
    
    prompt = f"""You are an editorial assistant. Review this collaborative document for coherence.

Original Document:
{sections_text}

Task:
1. Unify tone and voice across sections (keep professional, remove inconsistencies)
2. Remove contradictions between sections
3. Ensure consistent terminology (pick one term per concept)
4. Improve transitions between sections
5. DO NOT change factual content or remove citations
6. DO NOT add new claims (only edit existing)

Output the improved document with the same section structure.
For each change, explain what you fixed and why.

Format:
## Section Title
<improved content>

---
Changes Made:
- <section>: <what you changed>
"""
    
    # Cost: ~$0.10-0.30 depending on artifact size
    response = await openrouter_client.complete(
        prompt,
        model_id=model_id,
        max_tokens=4000
    )
    
    # Parse response, create new artifact version
    return parse_polished_artifact(response, original_artifact)
```

---

## User Interventions

### V1 Supported Interventions

#### 1. **Comment on Section** (Always Allowed)
- User adds comment to section metadata
- Comment shown to owner agent in next turn
- Non-blocking (doesn't stop drafting)

**Implementation**:
```json
// Add to section metadata in agent_knowledge_units
{
  "comments": [
    {
      "comment_id": "uuid",
      "author": "operator",
      "text": "Great analysis. Can you add quantitative data?",
      "created_at": "2026-02-09T20:18:00Z",
      "resolved": false
    }
  ]
}
```

---

#### 2. **Request Rewrite** (After Commit)
- User provides feedback
- Agent redrafts section
- Original version preserved in history

**Workflow**:
```
Section status: committed
    ↓
User clicks "Request Rewrite"
    ↓
Modal: "What should be changed?"
    ↓
POST /sections/{id}/rewrite
    ↓
Section status → drafting
    ↓
Agent redrafts with feedback
    ↓
New deltas stream to UI
    ↓
Agent commits → status: committed (v2)
```

---

#### 3. **Lock Section** (Prevent Further Edits)
- User finalizes section
- Agent can no longer edit
- Can be unlocked by user if needed

**State Transition**:
```
committed → locked (user action)
locked → committed (user unlock)
```

---

### V2 Interventions (Deferred)
- ❌ Edit section directly (overrides agent)
- ❌ Mid-draft reassignment without pause
- ❌ Merge/split sections

---

## Export Formats

### Canonical Format: HTML
Artifacts are stored as structured JSON but have a canonical HTML representation.

**HTML Template**:
```html
<!DOCTYPE html>
<html>
<head>
  <title>{{artifact.title}}</title>
  <style>/* Arinar artifact styling */</style>
</head>
<body>
  <header>
    <h1>{{artifact.title}}</h1>
    <div class="metadata">
      <span>Debate: {{debate.title}}</span>
      <span>Version: {{artifact.version}}</span>
      <span>Generated: {{artifact.finalized_at}}</span>
    </div>
  </header>
  
  {{#each sections}}
  <section id="{{section_id}}">
    <h2>{{title}}</h2>
    <div class="owner">Owner: {{owner_name}}</div>
    
    {{#each content}}
      {{#if type == "rich_text"}}
        <p>{{text}}</p>
        {{#if citations}}
          <div class="citations">
            {{#each citations}}
              <cite>[{{@index}}] {{title}}</cite>
            {{/each}}
          </div>
        {{/if}}
      {{/if}}
      
      {{#if type == "table"}}
        <table>...</table>
      {{/if}}
      
      {{#if type == "diagram_mermaid"}}
        <img src="data:image/svg+xml;base64,{{mermaid_svg_base64}}" />
      {{/if}}
      
      {{#if type == "chart"}}
        <img src="data:image/png;base64,{{chart_png_base64}}" />
      {{/if}}
    {{/each}}
  </section>
  {{/each}}
  
  <footer>
    <h3>Citations</h3>
    <!-- Full citation list -->
  </footer>
</body>
</html>
```

---

### PDF Export
Use headless Chrome (Puppeteer) or WeasyPrint to convert HTML → PDF.

**Requirements**:
- Include all citations
- Preserve formatting (tables, charts, diagrams)
- Add page numbers and header/footer
- Embed metadata (debate ID, version, date)

**Cost**: ~5-10 seconds processing time per artifact

---

### DOCX Export
Use python-docx or pandoc to convert HTML → DOCX.

**Requirements**:
- Preserve heading hierarchy
- Include citations as footnotes
- Tables and charts as embedded images
- Metadata in document properties

**Cost**: ~3-5 seconds processing time per artifact

---

## Edge Cases

### Edge Case 1: Agent Fails Mid-Drafting
**Scenario**: Agent crashes or times out while drafting section.

**Handling**:
- Section status remains "drafting" (not committed)
- UI shows: "Draft incomplete. Request rewrite?"
- User can retry or reassign section to different agent

---

### Edge Case 2: User Locks Section While Agent Is Drafting
**Scenario**: Agent is streaming deltas, user clicks "Lock Section".

**Handling**:
- Accept lock request
- Emit `artifact_section_locked` event
- Agent's next delta attempt returns 409 Conflict
- Agent gracefully handles: "Section was locked, stopping draft"
- UI shows partial draft as "interrupted"

---

### Edge Case 3: Coherence Pass Changes Factual Claims
**Scenario**: LLM coherence pass accidentally alters a fact or removes a critical citation.

**Handling**:
- Always show side-by-side comparison (original vs polished)
- User reviews before accepting
- Deterministic check: Citation count before/after must match
- If citations removed: Auto-flag as "Review Required"

---

### Edge Case 4: Multiple Sections Reference Same Material
**Scenario**: Goals and Risks both cite "Market Research" document.

**Handling**:
- Citations are by chunk_id (not material_id)
- Each section can independently cite chunks
- Citation deduplication in export (show once in footer, reference by number)

---

### Edge Case 5: Template Doesn't Match Debate Type
**Scenario**: User picks "Legal Memo" template for a product strategy debate.

**Handling**:
- Allow it (user knows best)
- Show warning: "This template is typically used for legal topics"
- Suggest alternative: "Consider 'Product Brief' template"
- User can proceed or switch

---

### Edge Case 6: Agent Assigned to Section Outside Their Expertise
**Scenario**: CFO assigned to "Technical Architecture" section.

**Handling**:
- Allow assignment (user/host decision)
- Show warning: "CFO is typically not assigned architecture sections"
- Agent will do their best (might reference other agents' inputs)
- Quality check will flag if section lacks domain expertise markers

---

## Non-Goals (V1)

### Explicitly Out of Scope

1. **Multi-Human Co-Editing (CRDT)**
   - V1: Agents draft, humans comment/rewrite
   - V2: Humans can directly edit with Yjs CRDT

2. **Offline Mode**
   - V1: Requires active connection for streaming
   - V2: Can draft offline, sync later

3. **Mid-Draft Reassignment Without Pause**
   - V1: Must pause section → reassign → resume
   - V2: Seamless reassignment with content preservation

4. **Advanced Merge Tools**
   - V1: Accept/reject coherence pass as whole
   - V2: Granular merge (accept some changes, reject others)

5. **Real-Time Collaboration Between Multiple Humans**
   - V1: One operator controls artifact
   - V2: Multiple humans can co-edit

6. **Artifact Forking/Branching**
   - V1: Linear versions (v1, v2, v3)
   - V2: Branch off versions ("marketing variant", "legal variant")

7. **Custom Template Builder UI**
   - V1: Predefined templates only (PRD, Brief, Memo, Plan)
   - V2: Users can create custom templates

---

## Templates

### Built-In Templates (V1)

#### **Template 1: Executive Brief**
```json
{
  "template_id": "executive-brief",
  "title": "Executive Brief",
  "description": "Board-ready decision brief",
  "sections": [
    {
      "section_id": "situation",
      "title": "Situation",
      "required": true,
      "suggested_owner_role": "PM",
      "word_count_target": 200,
      "description": "What decision needs to be made and why now?"
    },
    {
      "section_id": "recommendation",
      "title": "Recommendation",
      "required": true,
      "suggested_owner_role": "PM",
      "word_count_target": 150,
      "description": "What should we do?"
    },
    {
      "section_id": "rationale",
      "title": "Rationale",
      "required": true,
      "suggested_owner_role": "Strategy",
      "word_count_target": 300,
      "description": "Why this is the right choice"
    },
    {
      "section_id": "risks",
      "title": "Risks & Mitigations",
      "required": true,
      "suggested_owner_role": "Legal",
      "word_count_target": 250
    },
    {
      "section_id": "financials",
      "title": "Financial Impact",
      "required": true,
      "suggested_owner_role": "CFO",
      "word_count_target": 200,
      "description": "Cost, revenue impact, ROI"
    },
    {
      "section_id": "next_steps",
      "title": "Next Steps",
      "required": true,
      "suggested_owner_role": "PM",
      "word_count_target": 150
    }
  ]
}
```

---

#### **Template 2: Product Requirements Document (PRD)**
```json
{
  "template_id": "prd",
  "title": "Product Requirements Document",
  "sections": [
    {"section_id": "overview", "title": "Overview", "required": true, "suggested_owner_role": "PM"},
    {"section_id": "goals", "title": "Goals", "required": true, "suggested_owner_role": "PM"},
    {"section_id": "non_goals", "title": "Non-Goals", "required": true, "suggested_owner_role": "PM"},
    {"section_id": "user_stories", "title": "User Stories", "required": true, "suggested_owner_role": "Design"},
    {"section_id": "requirements", "title": "Functional Requirements", "required": true, "suggested_owner_role": "PM"},
    {"section_id": "technical", "title": "Technical Approach", "required": false, "suggested_owner_role": "Engineer"},
    {"section_id": "success_metrics", "title": "Success Metrics", "required": true, "suggested_owner_role": "PM"},
    {"section_id": "timeline", "title": "Timeline & Milestones", "required": true, "suggested_owner_role": "PM"},
    {"section_id": "risks", "title": "Risks", "required": false, "suggested_owner_role": "Legal"}
  ]
}
```

---

#### **Template 3: Decision Memo**
Shorter, action-focused.

```json
{
  "template_id": "decision-memo",
  "title": "Decision Memo",
  "sections": [
    {"section_id": "decision", "title": "Decision", "required": true, "word_count_target": 100},
    {"section_id": "context", "title": "Context", "required": true, "word_count_target": 200},
    {"section_id": "options_considered", "title": "Options Considered", "required": true},
    {"section_id": "rationale", "title": "Rationale", "required": true, "word_count_target": 250},
    {"section_id": "action_items", "title": "Action Items", "required": true}
  ]
}
```

---

#### **Template 4: Architecture Proposal**
```json
{
  "template_id": "architecture-proposal",
  "title": "Architecture Proposal",
  "sections": [
    {"section_id": "problem", "title": "Problem Statement", "required": true, "suggested_owner_role": "Engineer"},
    {"section_id": "current_state", "title": "Current Architecture", "required": true, "suggested_owner_role": "Engineer"},
    {"section_id": "proposed", "title": "Proposed Architecture", "required": true, "suggested_owner_role": "Engineer"},
    {"section_id": "trade_offs", "title": "Trade-offs", "required": true, "suggested_owner_role": "Engineer"},
    {"section_id": "migration", "title": "Migration Plan", "required": true, "suggested_owner_role": "Engineer"},
    {"section_id": "security", "title": "Security Considerations", "required": false, "suggested_owner_role": "Security"},
    {"section_id": "cost", "title": "Cost Impact", "required": true, "suggested_owner_role": "CFO"}
  ]
}
```

---

## Acceptance Criteria

### User Can:
- ✅ Create artifact from template at end of debate
- ✅ See sections assigned to agents
- ✅ Watch agents draft in real-time (streaming text)
- ✅ See "who is working on what" presence indicators
- ✅ Comment on sections while agents draft
- ✅ Request section rewrite with feedback
- ✅ Lock sections to prevent further agent edits
- ✅ Run coherence pass and see polished version
- ✅ Accept or reject coherence output
- ✅ Mark artifact as final
- ✅ Export to PDF/DOCX with citations

### System Ensures:
- ✅ All sections have clear ownership
- ✅ Required sections must be completed before finalization
- ✅ Citations are tracked and displayed
- ✅ Intended outcome is addressed (checked)
- ✅ Versions are preserved (can see artifact history)
- ✅ Audit trail exists (who wrote what, when)

### Quality Bars:
- ✅ Deterministic checks catch 90% of structural issues
- ✅ LLM coherence improves tone consistency (measurable via user survey)
- ✅ Streaming feels responsive (<500ms latency from agent to UI)
- ✅ Export quality is production-ready (suitable for stakeholder distribution)

---

## Implementation Notes

### Phase 1: Static Artifact (Optional Simplification)
If WebSocket streaming proves complex, V1.0 can ship with:
- Sections are drafted by agents (backend)
- UI polls for updates every 5 seconds
- Once all sections committed, show full artifact
- V1.5 adds true streaming

**Decision**: Team chose full streaming for V1. Keep this as fallback if timeline slips.

---

### Backend Service Structure

```python
# apps/api/src/services/artifact_service.py

class ArtifactService:
    async def create_artifact(
        self,
        debate_id: str,
        template_id: str,
        title: str,
        section_assignments: List[Dict]
    ) -> Artifact:
        """Create artifact and assign sections to agents"""
        pass
    
    async def stream_section_draft(
        self,
        artifact_id: str,
        section_id: str,
        owner_participant_id: str
    ):
        """Agent streams section content via WebSocket"""
        pass
    
    async def commit_section(
        self,
        artifact_id: str,
        section_id: str,
        content: List[Block],
        participant_id: str
    ) -> str:
        """Finalize section, store in agent_knowledge_units"""
        pass
    
    async def run_quality_checks(
        self,
        artifact_id: str,
        debate: Debate
    ) -> QualityReport:
        """Run deterministic checks"""
        pass
    
    async def run_coherence_pass(
        self,
        artifact_id: str,
        model_id: str,
        openrouter_key: str
    ) -> str:
        """LLM coherence pass, returns new artifact_id (polished version)"""
        pass
```

---

## Success Metrics

| Metric | Target | Why |
|--------|--------|-----|
| Artifact completion rate | >80% | Users finish artifacts they start |
| Coherence acceptance rate | >60% | LLM polish is valuable |
| Export usage | >50% | Artifacts are shared externally |
| Avg artifact quality score | >4/5 | User survey after each artifact |
| Streaming latency P95 | <1 second | Real-time feels responsive |
| Section rewrite requests | <20% | Agents get it right first time |

---

**Document Status**: Complete, ready for implementation  
**Next Step**: Engineering review and API contract finalization
