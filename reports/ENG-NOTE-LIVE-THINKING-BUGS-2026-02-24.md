# Engineering Note: Live Chain-of-Thought — Root Cause & Fix Plan

**Date:** 2026-02-24
**Severity:** P1 (feature non-functional)
**Reporter:** Architecture Review
**Status:** 4 of 7 bugs fixed — 3 critical bugs remain

---

## Fix verification

All 4 bugs from the original note have been applied and confirmed in code:

| # | Bug | File | Status |
|---|-----|------|--------|
| 1 | `active_participants` NameError on regeneration | `turn_orchestrator.py:1665` | ✅ Fixed |
| 2 | DB polling missing auth header | `useDebateRoom.ts:41` | ✅ Fixed |
| 3 | 1s broadcast timeout too short | `agent_thinking_service.py:150` | ✅ Fixed (5s) |
| 4 | Sequence window of 10 too tight | `EventFeed.tsx:142` | ✅ Fixed (80) |

However, the feature is still broken. Three additional bugs were uncovered during deeper analysis.

---

## Why it still doesn't work — the 3 remaining bugs

### Bug 5 — WebSocket broadcast sends `sequence_number: None` → JavaScript null coercion kills live display (CRITICAL)

**File:** `apps/api/src/agent_thinking_service.py:122`

The WebSocket envelope for every thinking event hard-codes the sequence number as `None`:

```python
envelope = {
    "type": "agent_thinking",
    "debate_id": debate_id,
    "sequence_number": None,   # ← THE BUG
    "event_id": step.get("step_id"),
    ...
}
```

`None` in Python serialises to `null` in JSON. On the frontend, the EventFeed checks whether a thinking event still has a later agent message (to decide whether to show it live):

```typescript
// EventFeed.tsx — live thinking filter
const hasLaterMessage = allMessages.some(m =>
  m.payload?.agent_name === agentName &&
  m.sequence_number > thinkEvent.sequence_number   // ← null coercion here
);
```

In JavaScript: `someNumber > null` coerces `null` to `0`, giving `someNumber > 0`.

Any agent who has spoken in a previous turn has an existing `agent_message` event with `sequence_number >= 1`. So that comparison evaluates `1 > 0` → `true`. `hasLaterMessage` is incorrectly `true`, and the live thinking block is **never rendered** for that agent — even though no message has arrived yet for the current turn.

**Impact:** Real-time (WebSocket) thinking display is broken for every turn after turn 1 for every agent who has previously spoken. Turn 1, first agent only works.

**Fix — EventFeed.tsx** (2 lines change):
```typescript
// Before: one comparison
m.sequence_number > thinkEvent.sequence_number

// After: guard against null
thinkEvent.sequence_number != null
  ? m.sequence_number > thinkEvent.sequence_number
  : new Date(m.occurred_at) > new Date(thinkEvent.occurred_at)
```

When the sequence number is null, fall back to timestamp comparison. Prior agent messages always have `occurred_at` before the current thinking event, so this correctly returns `false` until the current message lands.

---

### Bug 6 — DB polling query uses `ASC LIMIT 20` — misses current turn after ~3 turns (CRITICAL)

**File:** `apps/api/src/routes/events.py:62–66` and `apps/web/src/hooks/useDebateRoom.ts:39`

The polling fetch is:
```
/debates/{id}/events?event_type=agent_thinking&limit=20
```

The events endpoint processes this as:
```sql
WHERE debate_id = ? AND event_type = 'agent_thinking'
ORDER BY sequence_number ASC
LIMIT 20
```

This returns the 20 **oldest** thinking events, not the 20 most recent. Over the course of a debate:
- Turn 1 (6 steps): poll returns steps 1–6 ✓
- Turn 2 (6 steps): poll returns steps 1–12 ✓
- Turn 3 (6 steps): poll returns steps 1–18 ✓
- **Turn 4 (6 steps): poll returns steps 1–20 — steps 21–24 are NEVER returned ✗**
- Turn 5+: current turn's thinking steps are all outside the LIMIT 20 window ✗

The DB polling fallback — which is the only working path for turn 2+ thinking (because Bug 5 breaks WebSocket display) — silently returns zero new events while an agent is actively thinking.

**Fix — useDebateRoom.ts** (track last seen sequence):
```typescript
// Track the highest sequence number we've already polled
const [lastThinkingSeq, setLastThinkingSeq] = useState(0);

// In pollThinkingEvents:
const response = await fetch(
  `${API_URL}/debates/${debateId}/events?event_type=agent_thinking&since=${lastThinkingSeq}&limit=20`,
  { headers: ... }
);

// After adding new events, update the watermark
if (newEvents.length > 0) {
  const maxSeq = Math.max(...newEvents.map((e: any) => e.sequence_number ?? 0));
  if (maxSeq > 0) setLastThinkingSeq(maxSeq);
  return [...prev, ...newEvents];
}
```

**Fix — events.py** (support `since` param):
```python
@router.get("/debates/{debate_id}/events")
async def get_debate_events(
    debate_id: str,
    current_user: ...,
    limit: Optional[int] = None,
    event_type: Optional[str] = None,
    since: Optional[int] = 0          # ← add this param
):
    # In the query builder:
    if since:
        query += " AND sequence_number > %s"
        params.append(since)
    query += " ORDER BY sequence_number ASC"
```

---

### Bug 7 — WebSocket `event_id` and DB `event_id` are different UUIDs for the same thinking step (LOW)

**Files:** `agent_thinking_service.py:71,123` and `agent_thinking_service.py:168`

`emit_thinking_step` creates a `step_id` for the in-memory step object and uses it as the event envelope's `event_id` in the WebSocket broadcast:
```python
step = { "step_id": str(uuid.uuid4()), ... }    # e.g. "aaa-111"
envelope = { "event_id": step.get("step_id"), ... }  # broadcast uses "aaa-111"
```

But `_persist_thinking_step` generates a **separate** UUID for the DB row:
```python
event_id = str(uuid.uuid4())   # e.g. "bbb-222" — different!
cursor.execute("INSERT INTO events (event_id, ...) VALUES (%s, ...)", (event_id, ...))
```

When the same thinking step arrives via both paths (WebSocket `"aaa-111"` and DB poll `"bbb-222"`), the client-side deduplication (`existingIds.has(e.event_id)`) sees two different IDs and adds both. The same thinking stage appears twice in the "View reasoning" section.

**Fix — agent_thinking_service.py** (1 line in `_persist_thinking_step`):
```python
# Pass the step's own ID to the DB insert instead of generating a new one
def _persist_thinking_step(self, debate_id, agent_name, step):
    # Remove: event_id = str(uuid.uuid4())
    event_id = step["step_id"]   # ← use the same ID that was broadcast
    ...
```

---

## Signal path — current state

```
Turn 2+ (after someone has spoken before):

WebSocket path:
  emit_thinking_step → broadcast(sequence_number=None)
  → Frontend: hasLaterMessage = (prevMsg.seq > null) = (prevMsg.seq > 0) = true
  → isLiveThinking = false → NOT SHOWN  ❌  [Bug 5]

DB polling path:
  emit_thinking_step → persist to DB (sequence 47, 48, 49...)
  → Poll: GET /events?event_type=agent_thinking&limit=20
  → DB returns events at sequence 1–20 (oldest 20, never the current turn)
  → No new events found → NOT SHOWN  ❌  [Bug 6]
```

```
Turn 1, first agent only:

WebSocket path:
  emit_thinking_step → broadcast(sequence_number=None)
  → Frontend: allMessages is empty → hasLaterMessage = false
  → isLiveThinking = true → SHOWN  ✓

DB polling path:
  persist to DB → poll returns 1–6 → all new → SHOWN  ✓
```

This precisely matches the reported symptom: works once (if at all), then stops.

---

## Fix priority

| # | Bug | File:Line | Effort | Blocks |
|---|-----|-----------|--------|--------|
| 5 | null sequence → JS coercion suppresses live display | `EventFeed.tsx:157` | 3 lines | Real-time WebSocket path |
| 6 | ASC LIMIT 20 misses current-turn events | `useDebateRoom.ts:39` + `events.py:62` | 8 lines | DB polling fallback |
| 7 | event_id mismatch → duplicates | `agent_thinking_service.py:168` | 1 line | Clean display |

Fix bugs 5 and 6 together — they are two halves of the same broken fallback strategy. Bug 7 is a cleanup item.

---

## Quick verification after fixes

Open browser DevTools → Console and server stdout when hitting "Next Turn":

**Should see on server:**
```
🧠 Emitting thinking step: reasoning - Stage 1: Reasoning
📡 Broadcasting thinking to debate <id>: Stage 1: Reasoning
   Active WebSocket connections for debate: 1
✅ Thinking broadcast via WebSocket
```

**Should see in browser console:**
```
🟢 THINKING EVENT RECEIVED: Stage 1: Reasoning at 14:32:01
📥 Polled 1 new thinking events from DB   ← (within 1s)
🟢 THINKING EVENT RECEIVED: Stage 1: Complete at 14:32:03
...
💬 MESSAGE EVENT RECEIVED at 14:32:15
```

If server shows broadcast OK but browser shows no `🟢 THINKING EVENT RECEIVED`, the WebSocket connection is the problem.
If server shows `⚠️ Thinking broadcast failed`, the 5s timeout is still expiring.
If browser shows events but nothing renders, the EventFeed processing or CSS is hiding them.
