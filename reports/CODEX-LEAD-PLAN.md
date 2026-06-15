# Codex Lead Plan (Do Not Edit In Cursor)

This file is maintained by **Codex only** as a running plan + checkpoints.
If Cursor needs to reference it, it may **read-only**. Cursor must not modify this file.

## North Star (Enterprise V1)

Decision Room product that reliably delivers:
- Setup: title, problem statement, agenda, intended outcome/success criteria.
- Materials ingestion: upload URLs/files (PDF/DOCX/TXT/MD) with provenance-first chunking and auditability.
- Agents/personas: templates + custom, each with OpenRouter model selection + policy toggles (internet, “thinking”, etc).
- Optional memory import from prior meetings (scoped per agent or all agents) with strict “only what it learned” behavior.
- Preflight: agent prep packs created from allowed materials + memory + research.
- Live room: Slack-like debate, interventions, timeboxing, streaming.
- End outputs: summary/minutes/action items + live collaborative artifact board (Figma-like blocks) with export PDF/DOCX.

Non-negotiables:
- OpenRouter-only.
- BYOK (do not persist raw OpenRouter keys server-side).
- No duplicate stores/schemas; reuse existing tables and extend minimally.
- Tests must be real (DB-backed); avoid service mocks for core flows.

## Current Reality Check (What Must Stay True)

- `make verify` is the canonical gate and must pass locally + in CI.
- DB schema + app code must not drift (contract + migration discipline).
- Keep files small; avoid “god modules”; prefer `src/routes/*`, `src/services/*`, `src/utils/*`.

## Next Execution Order (Locked)

0. **Immediate blocker: Setup Page Gate + Truthfulness**
   - Goal: bring `/apps/web/src/app/setup/page.tsx` back under the 300-line limit and ensure “Enter Room” is only enabled when preflight is actually ready (or explicitly skipped) for every participant.
   - Required: `make verify` must pass. No misleading UI controls.
   - Status: Completed via `TICKET-13B.1-2026-02-10-v1.md` (independently re-verified by Codex; `setup/page.tsx` is 282 lines; `make verify` PASS).

1. **TICKET-12 hard verification**
   - Goal: Materials pipeline verified end-to-end with real local services and a no-mock E2E test.
   - Required: `make verify` green in a clean environment and CI job provisions required services.

2. **TICKET-15 Memory Import V1**
   - Goal: Implement memory grants + enforcement and audit trail; UI toggle per debate.
   - Required: retrieval restrictions enforced; access logged; tests.

3. **TICKET-13 Preflight Orchestrator + Research**
   - Goal: background jobs produce per-agent prep packs with citations; research off by default.
   - Required: Celery-based orchestration, resumable jobs, visible progress.

4. **Live Artifacts Engine (V1)**
   - Goal: agent-owned sections + live deltas + coherence pass + export PDF/DOCX.
   - Required: provenance links back to sources; diff/versions.

## Known Risks To Monitor

- CI currently runs API tests without provisioning DB/services unless explicitly added.
- Local “PASS” reports are not trustworthy unless `make verify` output is attached.
- Materials ingestion introduces MinIO/Redis dependencies that must be present for tests.

## Reference Docs (Authoritative)

- Decisions: `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/docs/design/DECISIONS-SOURCE-OF-TRUTH-2026-02-09.md`
- Product flow: `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/docs/product/MEETING-FLOW-MEMORY-ARTIFACTS.md`
- Materials ticket: `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/docs/tickets/TICKET-12-MATERIALS-INGESTION-PHASE-1.md`
- Memory import UX: `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/docs/design/MEMORY-IMPORT-UX-SPEC.md`
- Live artifacts tech spec: `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/docs/design/LIVE-ARTIFACTS-TECHNICAL-SPEC.md`
