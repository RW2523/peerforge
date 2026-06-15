# TICKET-13: Preflight Orchestrator + Research Provider (Phase 3 Core)

Status: Ready
Owner: Engineering
Last updated: 2026-02-09

## Goal
Implement agent preflight so agents enter the room prepared:
- Each agent reviews relevant ingested materials
- Optional internet research under explicit policy controls
- Produces an Agent Prep Pack (stored as knowledge units) with citations
- Shows progress per agent with retry/skip

## References
- Decisions: `arinar-v2/docs/design/DECISIONS-SOURCE-OF-TRUTH-2026-02-09.md`
- Product flow: `arinar-v2/docs/product/MEETING-FLOW-MEMORY-ARTIFACTS.md`
- Architecture: `arinar-v2/docs/design/AGENT-PREPARATION-ARCHITECTURE.md`

## Non-negotiables
- Preflight outputs are stored as `agent_knowledge_units` (no duplicate briefing tables).
- Retrieval is provenance-first and auditable (log to `memory_access_log`).
- Internet research:
  - OFF by default
  - explicit per debate/per agent policy
  - citations required
  - provider behind `ResearchProvider` interface (Perplexity first)
- Durable orchestration via Celery.

## Scope
1) State machine additions:
- Add states:
  - `materials_processing`, `materials_ready`, `preparing_agents`, `ready`
- Add endpoints:
  - `POST /debates/{debate_id}/prepare`
  - `GET /debates/{debate_id}/preparation/status`
  - `POST /debates/{debate_id}/preparation/retry`
  - `POST /debates/{debate_id}/preparation/skip`

2) Material retrieval for preflight:
- Use chunks in `memory_chunks` where `source_debate_id=debate_id` and `source_type='material'`.
- Phase 1 preflight can do:
  - category filtering (if available)
  - simple keyword scoring
- Later: vector retrieval (HNSW/IVFFlat behind interface).

3) Research provider:
- Implement `ResearchProvider` interface.
- Implement Perplexity provider first.
- Store research outputs as cited knowledge units and/or events.

4) Prep pack generation:
- For each participant:
  - generate a memo (200-400 words)
  - include: key facts with citations, risks, open questions, initial stance
- Persist:
  - `agent_knowledge_units` with `metadata.type='preflight_briefing'`

5) UI:
- Add a “Prepare Panel” step with per-agent progress cards and controls.

## Testing
- Unit tests for:
  - policy enforcement (research off/on)
  - provider interface behavior
  - prep pack formatting validation
- Integration tests for:
  - prepare -> status changes
  - retry/skip behavior
- No real Perplexity calls in default CI; allow optional integration tests behind flag.

## Gates (Definition of Done)
From `arinar-v2`:
1) `make verify` PASS
2) In a demo debate with 3 agents and ingested materials:
  - preflight produces 3 prep packs (knowledge units) with citations
  - status endpoint shows per-agent progress
  - skip/retry works

## Report
Write:
- `arinar-v2/reports/tickets/TICKET-13-2026-02-09-v1.md`

