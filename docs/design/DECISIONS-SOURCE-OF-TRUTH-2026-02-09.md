# Decisions Source Of Truth (2026-02-09)

Status: Active (authoritative unless superseded by a newer decisions doc)
Owner: Product Lead
Last updated: 2026-02-09

## Purpose
This document is the single source of truth for the decisions made in the 2026-02-09 planning discussion.

Use this doc to:
- stop re-litigating decisions across tickets and chats
- unblock engineering execution
- make scope and product guarantees explicit

If a decision changes, do not edit history silently.
Create a new decisions doc with a new date and explicitly call out what changed and why.

## References (Context)
- Team questions: `arinar-v2/docs/design/QUESTIONS-FOR-TEAM.md`
- Team critique + product lead response: `arinar-v2/docs/design/TEAM-RESPONSE-ANALYSIS.md`
- Product spec (flow + memory + artifacts): `arinar-v2/docs/product/MEETING-FLOW-MEMORY-ARTIFACTS.md`
- Design specs:
  - `arinar-v2/docs/design/AGENT-PREPARATION-ARCHITECTURE.md`
  - `arinar-v2/docs/design/CUSTOM-AGENTS-UI-SPEC.md`
  - `arinar-v2/docs/design/WEBSOCKET-ROOM-AND-LIVE-BOARD-PLAN.md`

## Non-Negotiables
1. OpenRouter-only (BYOK).
   - Never store raw OpenRouter keys server-side.
   - Never put keys in URLs or logs.
2. Provenance-first truth.
   - Agents may only assert facts that are present in allowed sources.
   - Anything not sourced must be framed as a question/assumption.
3. Enterprise controls.
   - Internet access is policy-controlled and auditable.
   - Citations are required when internet or materials are used.
4. No duplicate storage systems.
   - Reuse existing tables for chunks/knowledge/audit where possible.
5. Premium outcomes.
   - The system must produce decision-grade outputs and artifacts, not just chat logs.

## Product Scope (V1 Guarantees)
V1 is the "full product" baseline (not a toy MVP), shipped in gated increments.

V1 includes:
1. Setup flow: title, problem statement (recommended), agenda, intended outcome, success criteria, timebox.
2. Materials ingestion: upload URLs/text/files, extraction, categorization, chunking, indexing, Material Map.
3. Panel: templates + custom agents + personas, per-agent model selection (OpenRouter catalog) and policy toggles.
4. Memory import (user-enabled):
   - import prior meeting context
   - scope: all agents or specific agents
   - explicit preview of what is imported
5. Agent preflight:
   - agent prep packs (briefings) with citations
   - optional research based on policy
   - progress visibility + retry/skip
6. Live room:
   - Slack-like timeline + intervention + timeboxing
   - retrieval with citations (materials + allowed memory + approved research)
7. Outputs:
   - summary + minutes + action items
8. Live artifacts (Figma-like) V1:
   - templates, section ownership, live drafting (streaming), review, coherence polish pass, versioning

Explicit V2 features (not required for V1):
- true multi-human co-editing using CRDT (Yjs)
- advanced merge tools and offline mode
- mid-draft reassignment without explicit pause/resume boundary

## Key Decisions (By Topic)

### Live Artifacts
- Decision: Ship Live Artifacts in V1 as a flagship feature.
- Shape: "Full V1" collaboration experience, with a de-risked implementation:
  - artifact can be generated immediately from owned sections
  - coherence pass runs asynchronously and produces a "polished" version
  - user can accept/reject coherence output

### Realtime Transport (Room + Artifacts)
- Decision: WebSocket-first for all realtime room and artifact collaboration.
- Scope:
  - room feed and state updates
  - presence/typing
  - host controls
  - artifact drafting deltas and quality events
- REST remains for setup/history/settings/materials.
- SSE is compatibility-only and must not be the primary path for `/room` or live artifact collaboration.
- Reference: `arinar-v2/docs/design/WEBSOCKET-ROOM-AND-LIVE-BOARD-PLAN.md`.

### Memory Import
- Decision: Ship in V1 (enterprise requirement).
- Enforcement: explicit allowlists per debate and per participant (no global memory).
- Storage: relational join table `debate_memory_grants` (auditable, enforceable).

### Custom Agents UI
- Decision: build in parallel with ingestion/preflight.
- Requirement: prompt preview and OpenRouter model picker powered by `GET /openrouter/models`.
- No key inputs inside Custom Agents. Use Settings’ centralized key store only.

### Materials "Material Map"
- Decision: required in V1 (trust anchor).
- Placement: summary in setup + persistent right panel in room + expandable details.

### Coherence Pass
- Decision: include an LLM-based coherence pass in V1, but make it non-blocking.
- Also required: deterministic quality checks (required sections, citations, intended outcome addressed).

### Section Assignment
- Decision: hybrid (suggest -> user/host confirm/override) before drafting begins.
- Mid-draft changes: V1 supports reassignment only through explicit state transitions:
  - pause section -> reassign -> resume

### Retrieval / Vector Index
- Decision: quality-first. Target HNSW, but hide behind an internal interface.
- Allow early development fallback to IVFFlat if needed without product-level changes.

### Long-Context Strategy (RLM-Style)
- Decision: Use an **RLM-style** inference-time approach for long context across:
  - agent preflight prep packs
  - live artifacts (section drafting + coherence merge)
  - end-of-meeting synthesis (summary/minutes/action items)
- Meaning: plan -> retrieve slices -> draft -> verify/merge (bounded passes, no “stuff everything into one prompt”).
- Rationale: improves quality and auditability for many-material + memory-import meetings.
- Reference: `arinar-v2/docs/design/RLM-APPLICATION-TO-ARINAR.md`.

### Research Provider
- Decision: Perplexity first, behind a provider abstraction.
- Policy: internet research is OFF by default; explicitly enable per meeting/per agent.
- Requirement: citations and audit trail for any research result.

### Job Queue / Orchestration
- Decision: Redis + Celery from day 1 (durable, retryable, observable).

### OCR
- Decision: Phase 1 includes detection + user choice to run OCR when scanned PDFs are detected.

### Virus Scanning
- Decision: V1 must include strict file validation (allowlist + magic bytes + size limits + quarantine).
- Scanning: ClamAV if it can be implemented cleanly without destabilizing ingestion; otherwise V1.1 hardening.

### Failure Handling
- Decision: default = 1 automatic retry, then prompt user (retry/skip/abort).
- Configurable preference is allowed.

### Versioning
- Decision: hybrid.
  - auto-save drafts
  - user marks a version as final

### Timeline / Streams
- Internal target: 12 weeks with strict scope lock and aggressive gating.
- External messaging: 12-16 weeks depending on enterprise hardening requirements.
- Execution: 3 parallel streams (Ingestion/Preflight, Agents/Personas, Artifacts/UI).

## Single-Source Storage Strategy (No Duplicates)
We will not introduce parallel chunk/briefing tables.

Reuse and extend:
- `meeting_materials`: material metadata + processing status
- `memory_chunks`: all chunks (materials, artifacts, etc.) with provenance in metadata
- `agent_knowledge_units`: durable prep packs, imported knowledge, finalized artifact commits
- `events`: immutable event ledger (including WebSocket-streamed deltas)
- `memory_access_log`: audit retrieval

Avoid:
- `document_chunks`
- `agent_briefings`

## Open Items (Must Be Spec’d Before Coding Those Areas)
1. Live artifacts technical spec (events, API contracts, WebSocket deltas, coherence workflow).
2. Memory import UX spec (import preview, allowlist editing, “what is shared” clarity).
3. Cost analysis update including artifact generation (documentation only; not a blocker for early pipeline work).
