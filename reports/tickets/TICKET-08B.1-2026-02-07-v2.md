# Ticket Report: TICKET-08B.1 - Backend + Contracts (Meeting Setup Primitives)

## Summary
- **Ticket(s):** TICKET-08B.1
- **Date:** 2026-02-07
- **Author:** Codex
- **Status:** `PASS`

This ticket delivers the backend primitives needed for a meeting setup wizard:
- Built-in agent/persona templates
- Persistent agent CRUD (per-workspace)
- One-call debate setup: create debate + participants + materials metadata
- Contracts updated so OpenAPI remains the source of truth

## What Changed

### Files Created
- `apps/api/src/agent_service.py` (persistent agent CRUD)
- `apps/api/src/meeting_setup_service.py` (setup flow orchestration)

### Files Modified
- `apps/api/src/main.py`
  - Added endpoints:
    - `GET /agent-templates`
    - `POST /agents`
    - `GET /agents?workspace_id=...`
    - `POST /debates/setup`
  - Fixed Pydantic v2 config collisions by using aliases so responses serialize `model_config` correctly.
- `packages/contracts/openapi/arinar-v1.yaml`
  - Added endpoints and schemas for meeting setup primitives.
  - Updated `DebateState` enum to `pending|running|paused|ended`.
  - Updated `CreateDebateRequest` and `DebateResponse` to match current API shape.
- `packages/contracts/scripts/validate-openapi.js` (required endpoints list expanded)
- `packages/contracts/tests/contracts.test.js` (required paths expanded)

## Commands Run

### Database
```bash
make db-up
make db-migrate
make db-seed
make db-smoke
```

### Full Gates
```bash
make verify
```

## Gate Checklist

| Gate | Status | Evidence |
|------|--------|----------|
| DB migration applied | YES | `20260206000004_meeting_setup_schema.sql` applied via `make db-migrate` |
| Templates endpoint works | YES | `apps/api/tests/test_meeting_setup.py::test_get_agent_templates` |
| Agent CRUD works | YES | `apps/api/tests/test_meeting_setup.py::test_create_and_list_agents` |
| Setup endpoint works | YES | `apps/api/tests/test_meeting_setup.py` setup cases PASS |
| Contract updated | YES | OpenAPI includes `/agent-templates`, `/agents`, `/debates/setup` |
| OpenAPI valid | YES | `npm run validate:openapi` (via `make verify`) |
| Types generated | YES | `npm run generate:types` (via `make verify`) |
| API tests pass | YES | `pytest` (via `make verify`) |
| Verify passes | YES | `make verify` |
| OpenRouter-only policy | YES | No provider SDKs added; only `model_id` strings stored/returned |
| File size limits | YES | `scripts/check_file_sizes.sh` (via `make verify`) |

## Blockers
- None

## Next Steps
1. **TICKET-08B.2 (Web Wizard)**: 4-step meeting setup UI that calls these endpoints and then opens `/operator` on the created debate.
2. **TICKET-08B.3 (Integration polish)**: materials display in operator room, better participant editing (prompt preview, model config toggles), and end-to-end flow tests.

