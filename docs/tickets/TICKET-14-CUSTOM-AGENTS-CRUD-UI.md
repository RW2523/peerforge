# TICKET-14: Custom Agents (Full CRUD + Premium Settings UI)

Status: Ready
Owner: Engineering
Last updated: 2026-02-09

## Goal
Users must be able to create, edit, delete, and reuse custom agents from Settings.

This unlocks the core workflow:
- Setup uses curated templates OR custom agents
- Each agent has a title, role, optional character/persona, prompt, and OpenRouter model selection
- Prompt preview is required before saving/using

## References
- Decisions: `arinar-v2/docs/design/DECISIONS-SOURCE-OF-TRUTH-2026-02-09.md`
- UI spec: `arinar-v2/docs/design/CUSTOM-AGENTS-UI-SPEC.md`
- Persona endpoints: `POST /personas/generate-draft`, `POST /personas/validate`
- Models endpoint: `GET /openrouter/models`

## Non-negotiables
- OpenRouter-only. BYOK key is client-side only (use Settings key store).
- No duplicate key inputs in agent builder: it must reuse the existing Settings key store.
- No duplicate “compiled prompt” storage. Preview is UI-only or derived.
- File sizes and repo gates must remain green (`make verify`).

## Scope

### 1) Backend: Agent CRUD
Today we have:
- `POST /agents`
- `GET /agents?workspace_id=...`

Add:
- `PUT /agents/{agent_id}`
- `DELETE /agents/{agent_id}`

Rules:
- Workspace access enforced (same pattern as existing endpoints).
- Update must be partial (PATCH semantics acceptable but keep `PUT` contract).
- Delete should be soft delete only if required; otherwise hard delete is acceptable for V1.
- `model_id` is required for agent, but updates may omit it if not changing.

### 2) Data Model
Custom agents must support an explicit `character` field (optional).

Implement one of:
- A) Add `character TEXT` column to `agents` table (preferred).
- B) Store character in `role_description` (not preferred; mixes semantics).

If A:
- add migration
- update schemas and OpenAPI

### 3) Web: Settings -> Custom Agents
Create a “Custom Agents” section under `/settings`:
- List existing agents (cards)
- Create new agent (modal or dedicated sub-page)
- Edit and delete with confirmation
- Prompt preview drawer (shows compiled prompt)

Model selection:
- Default UX is a searchable dropdown powered by `GET /openrouter/models` using the stored OpenRouter key.
- Provide advanced “enter model_id manually” escape hatch.

Persona draft:
- Optional helper: “Generate draft” calls `POST /personas/generate-draft`.
- After generation, show:
  - persona fields
  - compiled prompt
  - run `POST /personas/validate` and show inline errors/warnings

### 4) Setup integration
Ensure setup Participants step can add:
- curated templates
- existing custom agents

This is already partially present; validate end-to-end.

## Testing
- Backend tests:
  - create -> update -> list -> delete -> list (agent disappears)
  - auth: cross-workspace denied
- Web tests (light):
  - build + lint must pass

## Gates (Definition of Done)
From `arinar-v2`:
1) `make verify` PASS
2) `cd apps/web && npm run build` PASS
3) `cd apps/web && npm run lint` PASS
4) Manual smoke documented:
  - Settings -> create agent -> appears in setup -> add to debate

## Report
Write:
- `arinar-v2/reports/tickets/TICKET-14-2026-02-09-v1.md`

