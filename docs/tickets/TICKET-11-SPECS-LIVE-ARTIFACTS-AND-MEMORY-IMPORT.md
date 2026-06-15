# TICKET-11: Missing Specs (Artifacts + Memory Import)

Status: Ready
Owner: Product Lead (drafted by AI) + Engineering review
Last updated: 2026-02-09

## Goal
Write the missing specs that must exist *before* engineering starts implementation for:
- Live artifacts (Figma-like board)
- Memory import (prior meeting context scoping)

This is a documentation ticket. No production code changes beyond doc links/cleanup.

## Context / Inputs
Authoritative decisions:
- `arinar-v2/docs/design/DECISIONS-SOURCE-OF-TRUTH-2026-02-09.md`

Related docs:
- `arinar-v2/docs/product/MEETING-FLOW-MEMORY-ARTIFACTS.md`
- `arinar-v2/docs/design/AGENT-PREPARATION-ARCHITECTURE.md`
- `arinar-v2/docs/design/TEAM-RESPONSE-ANALYSIS.md`

## Deliverables

### 1) Live Artifacts Technical Spec
Create:
- `arinar-v2/docs/design/LIVE-ARTIFACTS-TECHNICAL-SPEC.md`

Must include:
- API contracts (OpenAPI-level) for:
  - create artifact from template
  - get artifact
  - update section block payload
  - request rewrite
  - lock/unlock section
  - assign/reassign owner (pause -> reassign -> resume)
  - run coherence pass (non-blocking) -> produces polished version
- SSE event types:
  - `artifact_section_delta`
  - `artifact_section_committed`
  - `artifact_presence`
  - `artifact_quality_report`
- Block model requirements:
  - `rich_text`, `diagram_mermaid`, `chart`, `table`
  - chart JSON contract and rendering rules
- Deterministic quality checks:
  - required sections present
  - citations present (or “needs source” markers)
  - intended outcome addressed
  - version labeling rules
- Data model and storage strategy (no duplicates):
  - reuse `events`, `memory_chunks`, `agent_knowledge_units`
- Export requirements:
  - PDF + DOCX from canonical HTML

### 2) Memory Import UX + Enforcement Spec
Create:
- `arinar-v2/docs/design/MEMORY-IMPORT-UX-SPEC.md`

Must include:
- Setup UI design:
  - pick sources (prior debates/artifacts)
  - preview “what will be imported” (topics + counts + last updated)
  - scope sharing:
    - all agents
    - selected agents only
- Enforcement rules:
  - retrieval allowlist per participant
  - audit: log every retrieval and which sources contributed
- Storage:
  - join table `debate_memory_grants` (V1 decision)
  - what fields it contains and how it is queried
- Failure modes:
  - missing sources, revoked permissions, deleted debates

## Gates (Definition of Done)
- Both docs exist and have:
  - clear definitions
  - explicit non-goals
  - edge cases
  - acceptance criteria
- Updated docs do not contradict `DECISIONS-SOURCE-OF-TRUTH-2026-02-09.md`.

## Report
Write:
- `arinar-v2/reports/tickets/TICKET-11-2026-02-09-v1.md`

Include:
- links to created specs
- a checklist confirming the required sections are present

