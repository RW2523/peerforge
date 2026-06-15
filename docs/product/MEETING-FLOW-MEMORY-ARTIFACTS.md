# Meeting Flow, Memory Sharing, And Live Artifacts (2026 Spec)

Owner: Product (stakeholder-driven)
Status: Draft (ready for implementation tickets)
Last updated: 2026-02-09

## Goal
Deliver an enterprise-grade "Decision Room" where a user:
1. Creates a debate/meeting with a title and problem statement.
2. Adds materials (URLs, text, PDFs/files).
3. Assembles a panel of AI agents (templates + custom agents + personas).
4. Optionally enables imported memory from prior meetings (scoped per agent).
5. Runs a live, Slack-like debate with interventions and timeboxing.
6. Ends the meeting and receives high-quality outputs, including a collaborative artifact that feels like a live Figma doc (agents co-author, own sections, and visibly "type").

Non-negotiables:
- OpenRouter-only (BYOK). Never store raw OpenRouter keys server-side.
- Enterprise policy controls (internet access, citation mode, tool calling).
- Provenance-first: anything the system "knows" must be traceable to a source (material, prior artifact, meeting event, or approved web citation).
- Long-context quality: we will not “stuff everything into one prompt”. We use an RLM-style multi-pass approach (plan -> retrieve slices -> draft -> verify/merge) for prep packs, artifacts, and summaries. See: `arinar-v2/docs/design/RLM-APPLICATION-TO-ARINAR.md`.

## Realtime Transport Decision (Authoritative)
For all room and live artifact collaboration features, Arinar uses **WebSockets** as the primary realtime transport.

Scope:
- Debate room live feed
- Presence and typing
- Host controls (pause/resume/next/end)
- Live artifact deltas (including charts/diagrams blocks)

Rules:
- REST stays for setup/history/settings/materials.
- SSE may remain temporarily for backward compatibility only, but `/room` and live artifact UX must be WebSocket-first.
- Realtime messages must use one shared event envelope and ordered sequence numbers per debate.

Implementation reference:
- `arinar-v2/docs/design/WEBSOCKET-ROOM-AND-LIVE-BOARD-PLAN.md`

## Core Concepts
### A. Agents (Reusable Profiles)
Agents are reusable "people-like" profiles stored in a workspace.
Each agent has:
- `title/name` (display name)
- `role` (e.g., Legal Counsel, Architect, PM)
- `character/persona` (optional: "Jobs-inspired", "Musk-inspired", etc.)
- `system_prompt` (human-editable, previewable)
- `model_id` (OpenRouter model string)
- `model_config` (temperature, max_tokens, etc.)
- `policy_defaults` (internet/tool/citations defaults)

Product rule: Users must be able to create/edit these under Settings, then reuse them across meetings.

### B. Materials (Source Library Per Meeting)
Materials are the "evidence pack" for a meeting:
- URL (web page)
- Text (pasted notes)
- File (PDF, doc, image, etc.)

Materials are not passed raw to agents during live debate.
Instead, we ingest -> extract -> chunk -> index -> retrieve "context packs" with citations.

### C. Long-Context Strategy (RLM-Style)
Arinar meetings can have arbitrarily large context (many documents + prior meetings). To keep output quality high and enterprise-auditable:
- Agents and the host operate on the materials/memory as an external environment.
- They recursively pull only the relevant slices needed for each step.
- They synthesize in structured stages with explicit provenance.

Design note: this is an inference-time orchestration pattern, not a “special model”. Details: `arinar-v2/docs/design/RLM-APPLICATION-TO-ARINAR.md`.

### C. Memory Sharing (User-Enabled, Scoped)
Memory is not global. It is an explicit allowlist of knowledge sources that an agent can reference.

Memory sources can be:
1. Prior meeting artifacts (summary/brief/plan/etc.)
2. Prior meeting materials (optional, but high risk; default off)
3. Agent-specific persistent knowledge units (what this "person" learned previously)

Sharing controls:
- Default: "This meeting only"
- Optional: Import prior context:
  - Import for all agents
  - Import for selected agents only
  - Import selected meetings/artifacts only

Trust rule: An agent may only assert facts that are present in its allowed knowledge sources, or that it gathered via approved research during this meeting (with citations).

### D. Artifacts (High-Value Deliverables)
Artifacts are the end-user deliverables created from the meeting.
Examples:
- Executive Brief (board-ready)
- PRD / Plan
- Action Plan
- Legal memo / Risk assessment
- Architecture proposal

Artifacts must be:
- Structured (not just chat)
- Versioned (v1, v2…)
- Citable (link back to meeting events + ingested material chunks + web citations)

## User Flow (Screens)
### 1) Home / Dashboard
Plain English:
- "Create a debate"
- "History" (continue past debates)
- "Settings" (OpenRouter key, custom agents)

### 2) Create Debate (Step 1)
Inputs:
- Title (required)
- Problem statement (recommended)
- Agenda (optional but strongly encouraged)
- Intended outcome (required for enterprise quality): "What should be true at the end?"
- Success criteria (1-3 bullets)
- Timebox (optional)

### 3) Materials (Step 2)
User adds:
- URLs
- Pasted text
- Files (PDFs etc.)

AI element (ingestion review) runs after materials are added:
- Classify each material (e.g., legal, financial, technical, market)
- Extract text
- Chunk + index
- Generate "Material Map":
  - key topics
  - entities
  - dates/figures
  - risk flags

UI shows:
- Material list with status: Pending -> Processed -> Failed
- A "Material Map" panel (auto-generated)
- A "Suggested questions" panel (optional)

### 4) Panel (Step 3)
User selects participants:
- Templates
- Existing custom agents
- Create a new custom agent (inline or deep link to Settings)

Per participant:
- Optional display name
- Role title
- Character/persona (optional)
- Model selection from OpenRouter catalog (BYOK)
- "Extended thinking" (stored as preference/metadata; only applied if the selected model supports it)
- Policy toggles (internet on/off, strict citations, tool calling)

### 5) Memory Import (Step 4, Optional)
User chooses whether agents can use prior context:
- Off (default)
- On:
  - choose meetings/artifacts to import
  - choose scope: all agents vs selected agents
  - preview what will be imported (topics + counts)

### 6) Preflight (Step 5)
Before the live debate begins, each agent prepares.
This is a "prep round" where they:
- Read problem statement + agenda + intended outcome
- Review material map + top relevant chunks
- Optionally do internet research if allowed

Output: "Agent Prep Pack" per agent (stored as knowledge units with citations):
- Key facts (with citations)
- Initial stance and rationale
- Risks/unknowns
- Questions for the group

Product effect: the actual meeting starts with higher-quality contributions and less wandering.

### 7) Live Room (Step 6)
Slack-like timeline:
- Agents speak in turns (host orchestrates)
- Human can intervene at any time:
  - tag agents
  - ask clarifying questions
  - pause/resume/end
- Live status shows who is "typing" and what they are doing (debating vs drafting artifact)

Internet access:
- Must be policy-controlled (off/limited/on)
- Any research result must be posted as a cited event.

### 8) End Meeting -> Outputs + Artifact (Step 7)
On end:
- Summary
- Minutes
- Action items
- One or more artifacts

Artifacts should be editable and versioned.

## Live Artifact (Figma-Like) Specification
This is the "premium" requirement: the artifact must feel like a collaborative doc where:
- Each agent owns a section.
- The host assigns sections based on specialty.
- Users can watch agents type and revise.
- The final artifact is cohesive, not stitched together.

### 0. Visual Blocks (Charts, Graphs, Diagrams) (V1)
Artifacts must support more than text. In V1, we support *rendered blocks* inside sections that agents can generate live while drafting.

Block types (V1):
1. `rich_text` (default)
   - Markdown with citations and callouts.
2. `diagram_mermaid`
   - Mermaid code block rendered in the UI.
   - Use cases: architecture, workflows, state machines, sequence diagrams, decision trees.
3. `chart`
   - Deterministic chart rendering from a structured JSON payload (no freehand drawing).
   - Supported charts (V1): bar, line, stacked bar, pie (optional).
   - Use cases: scoring matrices, budget breakdowns, prioritization charts, timelines (as bar/line).
4. `table`
   - Markdown table rendered as a styled grid.
   - Use cases: decision matrix, options comparison, action items.

Why this is the right V1 trade:
- Feels "Figma-like" (live + visual) without requiring a full canvas editor and CRDT.
- Auditable: every visual has a source payload (Mermaid code or chart JSON) and citations.
- Exportable: blocks can be rendered consistently to PDF/DOCX.

Constraints (enterprise + trust):
- Visual blocks must be reproducible: no opaque images generated without a source payload.
- If a chart is based on numbers inferred by an agent, it must be clearly labeled as an estimate and cite assumptions.

#### Chart JSON Contract (V1)
Chart blocks are represented as:
```json
{
  "type": "chart",
  "chart_type": "bar",
  "title": "Option Scorecard",
  "x_label": "Option",
  "y_label": "Score",
  "series": [
    { "name": "Total", "data": [ { "x": "A", "y": 72 }, { "x": "B", "y": 61 } ] }
  ],
  "notes": "Scores based on the decision matrix criteria weights."
}
```

Rendering requirements:
- UI renders charts deterministically from JSON.
- Agent drafts charts by streaming JSON payload updates (same as typing text).
- The host can lock a block to prevent further edits.

### A. Artifact Template And Section Ownership
Host selects an artifact template (or user provides one).
Template defines:
- Artifact type (e.g., PRD)
- Section outline (e.g., Goals, Non-goals, Risks, Legal, Architecture, Timeline)
- Required vs optional sections
- Quality bars per section (length, citations, format)

Host assigns each section to:
- One agent owner (primary)
- Optional reviewer agent(s)

### B. Real-Time Collaboration Experience
UI must show:
- Artifact outline (left)
- Live document editor (center)
- Agent activity (right): "PM drafting Goals", "Legal drafting Risks", etc.

Agents "type" into their section in real time:
- Streaming text (token stream) into the doc
- Cursor/presence indicator per agent
- "Drafting" vs "Reviewing" status

Human can:
- Comment on a section
- Request rewrite
- Reassign ownership
- Lock a section

### C. How We Avoid A Franken-Doc
We need a host-driven merge and coherence pass.
Recommended workflow:
1. Section owners draft
2. Reviewer agents comment
3. Host runs "coherence pass":
   - ensure consistent terminology
   - remove contradictions
   - unify tone
   - ensure intended outcome and success criteria are explicitly addressed

### D. Artifact Quality And Citations
Artifact content must cite sources:
- Meeting events (event IDs)
- Material chunks (chunk IDs + provenance)
- Approved web citations (URL + retrieval timestamp)

If a section includes an uncited claim, mark it as "Needs source" rather than presenting as fact.

### E. Data Model (Product-Level)
Artifact:
- `artifact_id`, `debate_id`, `type`, `title`, `version`, `status`
- `template_id` and `template_snapshot`
- `sections[]`: { `section_id`, `title`, `owner_agent_id`, `content`, `citations[]`, `status` }
- `events[]` linkage (for traceability)

Block model (recommended):
- Each section contains an ordered list of blocks:
  - `blocks[]`: { `block_id`, `block_type`, `payload`, `citations[]`, `status` }
- `payload` is:
  - Markdown string for `rich_text`
  - Mermaid string for `diagram_mermaid`
  - JSON object for `chart`
  - Markdown table (or structured rows/cols) for `table`

### F. Implementation Note (Engineering-Friendly)
V1 can be "single-writer per section" with server-authoritative section text.
V2 can adopt CRDT (e.g., Yjs) for true collaborative editing with humans.
For AI-only coauthoring, streaming patch events are sufficient:
- `artifact_section_delta` events via WebSocket
- `artifact_section_committed` events when an agent finishes a chunk

## Export / Download (PDF + Word) (V1)
Artifacts must be downloadable for real teams.

V1 export targets:
1. PDF (for distribution)
2. DOCX / Word (for collaboration and internal editing)

Export requirements:
- Exports preserve:
  - section structure
  - block rendering (Mermaid -> rendered diagram, chart -> rendered chart)
  - citations (footnotes or endnotes, plus a sources section)
  - version label and generation timestamp

Implementation note (no UI details here):
- Render artifact to a canonical HTML representation first.
- From HTML:
  - PDF: headless browser print (server-side)
  - DOCX: HTML-to-DOCX pipeline or DOCX template fill

Product rule:
- Export is always versioned: user downloads "Artifact v3", not a moving target.

## Internet Research Policy (Enterprise)
Internet access must be explicit and auditable.
Per meeting and per agent:
- `internet_mode`: off | limited | on
- limited mode includes allowlist and required citations.
Host can require approval for live research:
- Agent requests -> host approves -> result posted with citations.

## What We Must Document Next (for build tickets)
1. Materials ingestion pipeline:
   - extraction (PDF/text/HTML)
   - chunking strategy
   - indexing (vector + keyword)
   - provenance/citations model
2. Memory import and scoping:
   - knowledge unit allowlists per agent
   - import preview UX
3. Preflight:
   - agent prep pack format
   - storage and retrieval
4. Live artifact engine:
   - templates, assignment, WebSocket streaming deltas, coherence pass
5. Policies:
   - internet mode
   - tool calling (future MCP)
   - citation strictness
6. Realtime transport implementation details:
   - `arinar-v2/docs/design/WEBSOCKET-ROOM-AND-LIVE-BOARD-PLAN.md`

## Acceptance Criteria (Product)
The system is "working" when a non-technical user can:
- Create a custom agent in Settings with title/character/prompt/model.
- Create a meeting, add materials (URL + PDF), and see the materials auto-classified and chunked.
- Enable memory import for only 1 agent and verify other agents cannot reference that imported context.
- Run preflight and see each agent produce a prep pack with citations.
- Start the live debate and watch agents reference materials with citations.
- End the debate and receive an artifact that:
  - has owned sections,
  - shows visible real-time drafting,
  - includes citations,
  - and directly addresses the intended outcome and success criteria.
- Download the artifact as:
  - PDF
  - DOCX / Word
