# Architecture Review: WebSocket Pivot & Progress Assessment

**Date**: 2026-02-11
**Reviewer**: Senior Architect
**Scope**: SSE-to-WebSocket migration, pipeline fixes, setup wizard enhancements
**Status**: Review complete — action items identified

---

## Executive Summary

The codebase has undergone three significant changes since the last checkpoint:

1. **SSE replaced with WebSocket** for all room transport (events, controls, presence, typing)
2. **Prep pack pipeline gap closed** — agents now receive their preparation context during turns
3. **Setup wizard enhanced** with agenda and desired outcomes fields wired end-to-end

The WebSocket pivot is architecturally sound and solves real transport problems. The prep pack pipeline fix is critical and working. Several items remain open (detailed below).

---

## 1. WebSocket Pivot Assessment

### 1.1 Why the Pivot Happened

Evidence of 14 debug/fix markdown files in the repo root documents repeated SSE transport struggles:
- `DEBUG_SSE_FINDINGS.md`, `FINAL-FIX-PLAN.md`, `URGENT-FIX-SUMMARY.md`
- `REAL-FIX-NOW.md`, `FIX-COMPLETE-INSTRUCTIONS.md`, `SSE_ISSUE_RESOLVED.md`
- Plus test files: `test_sse.py`, `test_frontend_sse.html`, `monitor_sse.py`

Root issues:
- `EventSource` API cannot send custom auth headers — forced a fetch-based SSE workaround
- Fetch-based SSE is fragile with no native reconnect semantics
- Bidirectional needs (pause/resume/next/end controls) required separate REST calls alongside SSE, creating race conditions

**Verdict: The pivot to WebSocket is the correct architectural decision.**

### 1.2 New Files Introduced

| File | Lines | Role |
|------|-------|------|
| `apps/api/src/websocket_service.py` | 439 | ConnectionManager + WebSocketService (command routing, broadcast, event persistence) |
| `apps/api/src/routes/websocket.py` | 117 | WebSocket endpoint with JWT auth, workspace isolation, event loop |
| `apps/web/src/lib/wsClient.ts` | 338 | Production WS client: reconnect, heartbeat, dedup, typed commands |
| `apps/web/src/hooks/useDebateRoom.ts` | 110 | React hook wrapping WSClient lifecycle |

### 1.3 What's Working Well

**Backend (websocket_service.py)**
- Clean `ConnectionManager` with per-debate room sets and connection metadata
- Workspace isolation enforced at connection time (before accept)
- Events persisted before broadcast — durability guarantee
- Command routing is centralized and extensible
- `_handle_next_turn` delegates to `TurnOrchestrator` without double-inserting events

**Frontend (wsClient.ts)**
- Production-grade reconnect with exponential backoff: `[1s, 2s, 4s, 8s, 16s, 30s]`
- Heartbeat ping every 30s to detect dead sockets
- Event deduplication by `event_id` (keeps last 1000 IDs)
- Promise-based `sendCommand()` with 15s timeout — clean async contract
- Well-defined TypeScript types: `WSEventEnvelope`, `WSCommandMessage`, `WSAckMessage`

**React Hook (useDebateRoom.ts)**
- Clean React lifecycle management — connect on mount, disconnect on cleanup
- Double deduplication layer (client-level + hook-level by event_id)
- Minimal API surface: `events`, `connectionStatus`, `sendCommand`, `clearEvents`

**Room Page (room/page.tsx)**
- Uses `useDebateRoom` hook — single WebSocket for all room functionality
- `EventFeed` receives events as prop (no longer manages own connection)
- `DebateControls` and `InterveneComposer` use `sendCommand` (no separate REST calls)

**Design Document (WEBSOCKET-ROOM-AND-LIVE-BOARD-PLAN.md)**
- Clear transport boundary: WebSocket for room, REST for everything else
- Strict event envelope contract with `sequence_number` + `event_id`
- Replay support via `since` sequence parameter
- Figma-like live board vision scoped for V2

### 1.4 Items Requiring Attention

| # | Issue | Severity | Details |
|---|-------|----------|---------|
| WS-1 | `websocket_service.py` at 439 lines | Medium | Over 400-line service limit. `ConnectionManager` should be extracted to its own module. |
| WS-2 | In-memory connection state | Low (V1) | `active_connections: Dict[str, Set[WebSocket]]` — works for single process. Design doc mentions Redis pub/sub for multi-node; acceptable for V1. |
| WS-3 | Auth token in query params | Low | Standard for WebSocket (no custom headers on handshake). Ensure Supabase JWTs are short-lived and access logs aren't exposed. |
| WS-4 | No graceful shutdown | Low | Server restart drops all connections silently. Client reconnects (good), but stale server-side metadata persists until next interaction. |
| WS-5 | SSE code still present | Medium | Design doc says SSE is "temporary fallback." Dead transport code is maintenance liability. Plan removal timeline. |
| WS-6 | 14 debug markdown files in repo root | High (hygiene) | Must be cleaned up. These are noise and signal disorder to the team. See cleanup list below. |

---

## 2. Prep Pack Pipeline Fix

### 2.1 The Problem (Identified at CP8)

Preflight correctly generated prep packs and stored them in `agent_knowledge_units`, but `turn_orchestrator.py` never queried them. Agents entered debates with zero preparation context — a critical product gap.

### 2.2 The Fix (Confirmed in turn_orchestrator.py)

Lines 91-131 of `turn_orchestrator.py` now:

1. **Queries prep packs**: `SELECT content, metadata FROM agent_knowledge_units WHERE agent_id = %s ORDER BY created_at DESC LIMIT 1`
2. **Reads agenda/outcomes**: Extracts from `policy_config` JSONB
3. **Builds structured context**: Topic + problem + agenda items + desired outcomes as system message
4. **Injects prep pack**: `"Your preparation notes:\n{prep_pack}"` as separate system message
5. **Uses role context**: Agent's description for persona-aware turn instruction

**Full message chain per agent turn:**
```
[system] Agent system prompt (persona)
[system] Topic + problem + agenda + outcomes (context)
[system] Preparation notes from prep pack (if available)
[history] Last 10 conversation messages
[user]   Turn instruction with role context
```

**Status: FIXED AND VERIFIED**

---

## 3. Setup Wizard Enhancements

### 3.1 New Fields Added

| Field | UI Component | API Schema | Storage | Consumption |
|-------|-------------|------------|---------|-------------|
| Agenda items | `BasicInfoStep.tsx` (add/remove list) | `agenda: Optional[List[str]]` | `policy_config.agenda` | `turn_orchestrator.py` line 104 |
| Desired outcomes | `BasicInfoStep.tsx` (add/remove list) | `desired_outcomes: Optional[List[str]]` | `policy_config.desired_outcomes` | `turn_orchestrator.py` line 105 |

**End-to-end flow verified:**
UI (BasicInfoStep) -> API (schemas/setup.py) -> Service (meeting_setup_service.py) -> DB (debates.policy_config JSONB) -> Turn Orchestrator -> Agent messages

### 3.2 Current Setup Wizard Steps

| Step | Label | Component | Status |
|------|-------|-----------|--------|
| 1 | Basic Info | BasicInfoStep | Title + purpose + agenda + outcomes |
| 2 | Materials | MaterialsStep | File upload only (no website scraping) |
| 3 | Participants | ParticipantsStep | Agent selection + custom creation |
| 4 | Memory | MemoryStep | Import from prior debates |
| 5 | Prepare | PreflightStep | Agent preparation with status tracking |
| 6 | Review | ReviewStep | Summary before launch |

---

## 4. Open Gaps

### 4.1 Critical

| # | Gap | Impact | Effort |
|---|-----|--------|--------|
| GAP-1 | **Prep pack viewer shows placeholder text** | Users cannot verify agent preparation quality | Medium |
| | `PreflightStep.tsx` lines 167-178 show hardcoded fake content | | |
| | No API endpoint exists: `GET /preflight/{run_id}/prep-pack/{knowledge_id}` | | |

### 4.2 Important

| # | Gap | Impact | Effort |
|---|-----|--------|--------|
| GAP-2 | **Website link scraping not implemented** | Materials step is file-upload only, user asked for URL ingestion | Medium-Large |
| GAP-3 | **Speaking order verification needed** | User asked for drag-to-reorder turn order; ParticipantsStep needs audit | Small |
| GAP-4 | **Legacy debate_engine.py still ignores prep packs** | Only turn_orchestrator.py reads them; if any path uses debate_engine directly, agents get no context | Small |

### 4.3 Maintenance

| # | Gap | Impact | Effort |
|---|-----|--------|--------|
| GAP-5 | **14 debug/fix markdown files polluting repo root** | Signals disorder, confuses onboarding | Trivial |
| GAP-6 | **SSE test artifacts still present** | `test_sse.py`, `test_frontend_sse.html`, `monitor_sse.py` | Trivial |
| GAP-7 | **File size violations growing** | See Section 5 below | Ongoing |

---

## 5. File Size Discipline Report

Engineering standards: UI components ≤300 lines, services ≤400 lines, route controllers ≤500 lines.

### Violations

| File | Lines | Limit | Over By | Action Required |
|------|-------|-------|---------|-----------------|
| `apps/web/src/lib/api.ts` | 931 | — | Growing fast | Split by domain (setup, debates, preflight, artifacts) |
| `apps/api/src/routes/artifacts.py` | 581 | 500 | +81 | Extract helper functions |
| `apps/api/src/routes/preflight.py` | 521 | 500 | +21 | Extract validation logic |
| `apps/api/src/routes/debates.py` | 513 | 500 | +13 | Extract helper functions |
| `apps/api/src/websocket_service.py` | 439 | 400 | +39 | Extract ConnectionManager to own module |
| `apps/api/src/tasks/preflight.py` | 432 | 400 | +32 | Extract prep prompt builder |
| `apps/api/src/services/memory_retrieval.py` | 417 | 400 | +17 | Extract embedding logic |
| `apps/web/src/components/setup/PreflightStep.tsx` | 405 | 300 | +105 | Extract AnimatedStatus, participant card, action buttons |
| `apps/web/src/app/setup/page.tsx` | 321 | 300 | +21 | Extract step navigation logic |
| `apps/web/src/components/setup/PreflightDialogs.tsx` | 303 | 300 | +3 | Borderline — monitor |

### Compliant

| File | Lines | Limit | Status |
|------|-------|-------|--------|
| `apps/web/src/lib/wsClient.ts` | 338 | — | OK |
| `apps/web/src/app/room/page.tsx` | 250 | 300 | OK |
| `apps/api/src/turn_orchestrator.py` | 239 | 400 | OK |
| `apps/api/src/debate_engine.py` | 251 | 400 | OK |
| `apps/api/src/routes/websocket.py` | 117 | 500 | OK |
| `apps/web/src/hooks/useDebateRoom.ts` | 110 | — | OK |

---

## 6. Codebase Metrics Snapshot

| Metric | Count |
|--------|-------|
| Python source files (API) | ~53 (app code, excl. venv) |
| TypeScript/TSX files (Web) | 50 |
| React hooks | 9 |
| Design documents | 26 |
| Recent commits (since CP5) | 5+ |

---

## 7. Debug Trail — Files to Remove

The following files should be deleted from the repo root. They are SSE debug artifacts that no longer apply after the WebSocket pivot:

```
arinar-v2/URGENT-FIX-SUMMARY.md
arinar-v2/QUICK-FIX-LOG.md
arinar-v2/DEBUG_SSE_FINDINGS.md
arinar-v2/AUTO-TRIGGER-FIX.md
arinar-v2/PRE-LAUNCH-CHECKLIST.md
arinar-v2/REAL-FIX-NOW.md
arinar-v2/OPENROUTER-AUTH-FIX.md
arinar-v2/FIX-COMPLETE-INSTRUCTIONS.md
arinar-v2/CORE-FIX-SUMMARY.md
arinar-v2/HOW_TO_DEBUG_SSE.md
arinar-v2/FINAL-FIX-PLAN.md
arinar-v2/SSE_ISSUE_RESOLVED.md
arinar-v2/QUICK-START-CHECKLIST.md
```

Also remove SSE test artifacts:
```
arinar-v2/apps/api/test_sse.py (if exists)
arinar-v2/test_frontend_sse.html (if exists)
arinar-v2/monitor_sse.py (if exists)
```

---

## 8. Recommended Priorities

### Immediate (This Sprint)

1. **GAP-1: Wire real prep pack viewer**
   - Add `GET /api/v1/preflight/{debate_id}/prep-pack/{participant_id}` endpoint
   - Query `agent_knowledge_units` by agent_id + source_debate_id
   - Update `PreflightStep.tsx` to fetch and display real content
   - Estimated scope: 1 new route handler + 1 frontend fetch call

2. **GAP-5 + GAP-6: Clean debug trail**
   - Delete all 13 debug markdown files and SSE test artifacts
   - Single commit, no logic changes

3. **WS-1: Extract ConnectionManager**
   - Move `ConnectionManager` class from `websocket_service.py` to `connection_manager.py`
   - Brings both files under their respective limits

### Next Sprint

4. **GAP-2: Website link scraping** — Add URL input to MaterialsStep, backend scraping + chunking
5. **GAP-3: Speaking order** — Verify/add drag-to-reorder in ParticipantsStep
6. **File size splits** — `api.ts` (split by domain), `PreflightStep.tsx` (extract sub-components), route files (extract helpers)

### Backlog

7. **WS-2: Redis pub/sub** for multi-worker WebSocket fanout
8. **WS-5: SSE removal** — Remove SSE endpoint and fetch-based client code
9. **GAP-4: Deprecate debate_engine.py** — All room paths should use turn_orchestrator.py

---

## 9. Architecture Diagram — Current Transport Model

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                │
│                                                     │
│  Setup Wizard ──── REST ────► /api/v1/setup/*       │
│  Materials    ──── REST ────► /api/v1/materials/*    │
│  Settings     ──── REST ────► /api/v1/settings/*    │
│  History      ──── REST ────► /api/v1/debates/*     │
│                                                     │
│  Room Page    ──── WS ──────► /ws/debates/{id}      │
│    ├─ EventFeed       (receives events prop)        │
│    ├─ DebateControls  (sendCommand)                 │
│    ├─ InterveneComposer (sendCommand)               │
│    └─ Presence        (join/leave/typing)           │
│                                                     │
│  useDebateRoom hook                                 │
│    └─ WSClient (reconnect, heartbeat, dedup)        │
└─────────────────────────────────────────────────────┘
                         │
                    WebSocket
                         │
┌─────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                  │
│                                                     │
│  routes/websocket.py                                │
│    └─ JWT auth via query param                      │
│    └─ Workspace isolation check                     │
│    └─ Historical event replay                       │
│                                                     │
│  websocket_service.py                               │
│    ├─ ConnectionManager (per-debate rooms)           │
│    └─ WebSocketService                              │
│        ├─ Command handlers (presence, controls)     │
│        ├─ Event persistence (before broadcast)      │
│        └─ TurnOrchestrator delegation               │
│                                                     │
│  turn_orchestrator.py                               │
│    ├─ Reads prep packs from agent_knowledge_units   │
│    ├─ Reads agenda + outcomes from policy_config    │
│    ├─ Builds full message chain                     │
│    └─ Calls OpenRouter, persists event              │
└─────────────────────────────────────────────────────┘
```

---

## 10. Event Envelope Contract (Reference)

All WebSocket messages follow this envelope:

```json
{
  "type": "string",
  "debate_id": "uuid",
  "sequence_number": 123,
  "event_id": "uuid",
  "occurred_at": "2026-02-12T10:20:30Z",
  "sender_type": "system | user | agent",
  "sender_id": "uuid | null",
  "payload": {},
  "request_id": "optional-client-correlation-id"
}
```

**Client commands**: `join_presence`, `leave_presence`, `typing`, `intervene`, `control.pause`, `control.resume`, `control.next_turn`, `control.end`

**Server responses**: `ack`, `error`, domain events (`agent_message`, `presence_update`, etc.)

**Rules**:
- `sequence_number` is debate-scoped and monotonic
- Events persisted before broadcast
- Clients dedupe by `event_id` and guard ordering by `sequence_number`

---

*Report generated 2026-02-10. For questions, reference the design document at `docs/design/WEBSOCKET-ROOM-AND-LIVE-BOARD-PLAN.md`.*
