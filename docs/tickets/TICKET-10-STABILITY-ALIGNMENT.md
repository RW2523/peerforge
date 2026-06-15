# TICKET-10: Stability + Alignment (Stop Drift)

Status: Ready
Owner: Engineering
Last updated: 2026-02-09

## Goal
Restore a clean, coherent baseline so new feature work is not built on drift:
- `make verify` must PASS
- web pages must use consistent workspace defaults
- agent templates changes must not break API tests/contracts
- no hardcoded `http://localhost:8000` calls in web

This ticket is intentionally not “new feature work”. It is “stop the bleeding”.

## Context
Recent UI/agent template updates were applied outside the ticket system and currently break the gate suite.

Key reference decisions:
- `arinar-v2/docs/design/DECISIONS-SOURCE-OF-TRUTH-2026-02-09.md`
- `arinar-v2/docs/design/QUESTIONS-FOR-TEAM.md`

## Scope

### 1) Restore `make verify` PASS
Fix the failing API test that assumes legacy template IDs (`pm`, `engineer`, `designer`) while templates now use curated IDs.

Choose one approach (preferred is A):
- A) Update `apps/api/tests/test_meeting_setup.py` to assert on structure and category coverage, not specific IDs.
- B) Add backwards-compatible alias templates for the legacy IDs (avoid if possible).

### 2) Keep agent templates consistent and contract-safe
If templates now include `category` and `character`, ensure:
- API response schema matches (`apps/api/src/schemas/agents.py`)
- Web setup UI supports it (it already does)
- OpenAPI is updated if the `/agent-templates` response shape changed
- Generated types remain in sync (contracts package)

### 3) Unify demo workspace ID and remove magic strings
Use the seeded workspace id everywhere in web defaults:
- Demo workspace_id: `00000000-0000-0000-0000-000000000101`

Eliminate conflicting defaults like:
- `ws_demo_001`
- `00000000-0000-0000-0000-000000000001` (tenant id, not workspace id)

Targets:
- `apps/web/src/app/page.tsx`
- `apps/web/src/app/history/page.tsx`
- `apps/web/src/components/room/DebateSelector.tsx`
- `apps/web/src/app/setup/page.tsx` (already uses `...0101`, keep)

### 4) Remove remaining hardcoded localhost API calls
Web must never call `http://localhost:8000` directly.
All network calls must go through `apps/web/src/lib/api.ts` and respect `NEXT_PUBLIC_API_URL`.

## Non-negotiables
- Keep file sizes within existing repo gates.
- No provider SDKs (OpenRouter-only policy).
- No secrets in code or reports.
- Do not introduce duplicate systems.

## Gates (Definition of Done)
Run from `arinar-v2`:
1. `make verify` PASS
2. `cd apps/web && npm run build` PASS
3. `cd apps/web && npm run lint` PASS

## Report
Cursor must write:
- `arinar-v2/reports/tickets/TICKET-10-2026-02-09-v1.md`

Include:
- changed files list
- commands run (summarized)
- gates table (YES/NO)
- any follow-ups discovered

