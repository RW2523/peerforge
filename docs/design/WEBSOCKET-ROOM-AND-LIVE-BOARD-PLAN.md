# WebSocket Room And Live Board Plan

Status: Active design plan  
Owner: Product + Architecture  
Last updated: 2026-02-12

## Purpose
Define one production path for realtime collaboration:
- Slack-like room behavior
- Figma-like live artifact drafting

This replaces split transport assumptions. For realtime collaboration, the primary transport is WebSocket.

## Scope
In scope:
- Debate room event stream
- Presence and typing
- Host control commands (pause/resume/next/end)
- Live artifact section deltas and quality signals
- Shared event envelope and sequence model

Out of scope:
- Setup/history/settings/material ingestion transport (remains REST)
- Multi-human CRDT editing (V2)

## Transport Decision
For `/room` and live artifact collaboration, use:
- `ws://.../ws/debates/{debate_id}`

REST remains for:
- Setup wizard
- Materials upload and processing status
- Settings and workspace defaults
- History and reports

SSE:
- Allowed only as temporary compatibility fallback.
- Not the primary UX path.

## Realtime Contract
All messages follow one envelope:

```json
{
  "type": "string",
  "debate_id": "uuid",
  "sequence_number": 123,
  "event_id": "uuid",
  "occurred_at": "2026-02-12T10:20:30Z",
  "sender_type": "system|user|agent",
  "sender_id": "uuid|null",
  "payload": {},
  "request_id": "optional-client-correlation-id"
}
```

Rules:
- `sequence_number` is debate-scoped and monotonic.
- Events are persisted before broadcast.
- Clients must dedupe by `event_id` and guard ordering by `sequence_number`.

## Command Channels
Client -> server command messages:
- `join_presence`
- `leave_presence`
- `typing`
- `intervene`
- `control.pause`
- `control.resume`
- `control.next_turn`
- `control.end`
- `artifact.section.delta`
- `artifact.section.commit`
- `artifact.section.lock`

Server -> client response messages:
- `ack`
- `error`
- domain events (`agent_message`, `presence_update`, `artifact_section_delta`, etc.)

## Figma-Like Live Board Plan
The board is document-first with visual blocks, not freehand canvas-first.

### Board Layout
- Left rail: template outline and section ownership
- Center: active section document stream (rich text + visual blocks)
- Right rail: activity, quality checks, citations, controls

### Live Collaboration Behavior
- Section owner streams drafts in real time.
- Reviewers comment or request rewrite.
- Host can lock sections and trigger coherence pass.
- Presence/typing shown per section and per participant.

### Visual Blocks (V1)
- `rich_text`
- `diagram_mermaid`
- `chart` (deterministic JSON rendering)
- `table`

All visual blocks require reproducible source payload and citations.

### Artifact Quality Workflow
1. Draft section deltas stream live.
2. Section commits create durable knowledge units.
3. Deterministic quality checks run continuously.
4. Host runs coherence pass for polished version.
5. User accepts/rejects polished artifact.

## Data And Audit Model
- `events`: immutable room and artifact event ledger
- `agent_knowledge_units`: committed section content and prep packs
- `memory_chunks`: searchable chunks with provenance metadata
- `memory_access_log`: retrieval and grant usage audit

Audit guarantees:
- Every realtime action has actor + timestamp + debate scope.
- Artifacts are traceable to source chunks/events/web citations.

## Reliability Requirements
- Reconnect with exponential backoff
- Heartbeat/ping to detect dead sockets
- Replay support using `since` sequence
- Idempotent command handling with `request_id`
- Multi-node fanout readiness (Redis pub/sub path)

## Security Requirements
- Supabase JWT validation at connection time
- Workspace access enforcement before room join
- No OpenRouter key storage server-side
- BYOK only via headers/client memory per existing policy

## Rollout Plan
1. Backend WS parity:
   - room events, controls, presence, typing
2. Frontend room migration:
   - remove SSE dependency from `/room`
3. Live artifact WS migration:
   - section delta and presence events over same room socket
4. Compatibility window:
   - keep SSE endpoint as fallback only
5. Decommission:
   - remove SSE from active room UX once WS demo and gates are green

## Acceptance Criteria
1. Room feed updates in realtime via WebSocket only.
2. No `System/UNKNOWN/N/A` cards for valid events.
3. Presence/typing are visible and accurate.
4. Controls produce ACK/error and consistent state updates.
5. Live artifact drafting streams section deltas with ordering.
6. All realtime actions are persisted and auditable.
7. Build/lint/tests/gates pass with no new skipped tests.

