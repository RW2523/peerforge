# TICKET-15: Memory Import V1 (Grants + Preview + Enforcement Hooks)

Status: Ready
Owner: Engineering
Last updated: 2026-02-09

## Goal
Implement user-controlled memory import so a user can:
- select prior debates/artifacts to import
- choose scope: all agents or specific agents
- preview what will be imported
- enforce that agents can only retrieve from allowed sources
- audit retrieval for compliance

## References
- Decisions: `arinar-v2/docs/design/DECISIONS-SOURCE-OF-TRUTH-2026-02-09.md`
- Spec: `arinar-v2/docs/design/MEMORY-IMPORT-UX-SPEC.md`

## Non-negotiables
- No global memory.
- Explicit grants only (default is isolated debate).
- Join table storage: `debate_memory_grants` (V1 decision).
- Audit retrieval:
  - Extend `memory_access_log` (no new audit table).
  - Record which chunk IDs were returned for each retrieval.

## Scope

### 1) DB Migrations
Add migration(s) for:
1. `debate_memory_grants` table (per spec).
2. Extend `memory_access_log` to support compliance audit:
   - `chunk_ids UUID[]`
   - `metadata JSONB DEFAULT '{}'`

### 2) Backend API
Implement endpoints (names can match spec exactly):
- `GET /workspaces/{workspace_id}/memory/importable`
  - list recent debates + available artifacts with summary counts
- `GET /debates/{debate_id}/memory/preview`
  - returns topics + chunk counts + titles + date range
- `POST /debates/{debate_id}/memory/import`
  - creates grants
- `GET /debates/{debate_id}/memory/grants`
  - lists active grants
- `DELETE /debates/{debate_id}/memory/grants/{grant_id}`
  - revoke, but only if debate not running (immutable after start)

### 3) Enforcement Hook (Minimal, but real)
Implement a single retrieval helper that will be used by preflight and later by debate turns:
- `retrieve_allowed_chunks(debate_id, participant_id, query, top_k)`

Rules:
- Always include current debate materials.
- Include imported sources only if a matching grant exists for participant (or all_agents scope).
- Log retrieval to `memory_access_log` including returned `chunk_ids` and `metadata.grant_ids` used.

This ticket does NOT need to build full vector search.
It can do:
- simple keyword scoring over `memory_chunks.chunk_text`
- and later swap behind an interface.

### 4) Web UI (Setup step)
Add Memory Import step to setup wizard after Participants:
- toggle: off by default
- pick sources
- choose scope (all agents vs selected)
- show preview panel

## Testing
- DB migration tests via `make db-migrate` and `make db-smoke` updates.
- API tests:
  - create grant -> appears in list
  - preview returns expected shape
  - revoke forbidden after debate started
  - enforcement: participant without grant cannot retrieve chunks from imported debate

## Gates
1) `make verify` PASS
2) `cd apps/web && npm run build` PASS
3) `cd apps/web && npm run lint` PASS

## Report
Write:
- `arinar-v2/reports/tickets/TICKET-15-2026-02-09-v1.md`

