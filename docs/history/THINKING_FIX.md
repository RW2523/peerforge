# Agent Thinking Display Fix

## Issues Found & Fixed

### Issue 1: Missing Import ❌
**Problem**: `turn_orchestrator.py` line 38 was using `AgentThinkingService()` but the import was missing.

**Fix**: Added the import:
```python
from .agent_thinking_service import AgentThinkingService
```

**File**: `apps/api/src/turn_orchestrator.py` line 16

---

### Issue 2: Wrong Database Column Name ❌  
**Problem**: The `agent_thinking_service.py` was trying to use column `occurred_at` but the events table uses `created_at`.

**Error**:
```
⚠️ Thinking persistence error: column "occurred_at" of relation "events" does not exist
```

**Fix**: Changed all references from `occurred_at` to `created_at` in 4 places:
- Line 146: INSERT statement
- Line 230: SELECT statement (with agent_name filter)
- Line 240: SELECT statement (without agent_name filter)
- Line 259: Result timestamp access

**File**: `apps/api/src/agent_thinking_service.py`

---

### Issue 3: Improper WebSocket Event Format ❌
**Problem**: The `_broadcast_thinking` method was sending raw data instead of proper WebSocket event envelopes.

**Before**:
```python
event_data = {
    "type": "agent_thinking",
    "agent_name": agent_name,
    **step
}
```

**After**:
```python
envelope = {
    "type": "agent_thinking",
    "debate_id": debate_id,
    "sequence_number": None,
    "event_id": step.get("step_id"),
    "occurred_at": step.get("timestamp"),
    "sender_type": "agent",
    "sender_id": agent_name,
    "payload": {
        "agent_name": agent_name,
        "thinking_type": step.get("thinking_type"),
        "stage": step.get("stage"),
        "status": step.get("status"),
        "details": step.get("details", []),
        "timestamp": step.get("timestamp")
    }
}
```

**File**: `apps/api/src/agent_thinking_service.py` lines 101-137

---

## How It Works Now

1. **Agent Turn Triggered**: User clicks "Next Turn"
2. **Thinking Session Started**: `start_thinking_session()` creates session tracking
3. **Thinking Steps Emitted**: As Constitutional AI runs (Reasoning → Response → Validation):
   - Each step is broadcasted via WebSocket **in real-time**
   - Each step is persisted to database `events` table
4. **Frontend Groups Thinking**: `EventFeed.tsx` filters out `agent_thinking` events and attaches them to the corresponding `agent_message`
5. **UI Display**: Below each agent message, a collapsible button shows:
   - "🧠 Show thinking process (X steps)"
   - Click to expand and see all thinking steps
6. **Session Completed**: When turn finishes, session summary is saved to `agent_memories` table

---

## What You'll See

When you click "Next Turn", you should now see:

1. **Real-time thinking in feed** (grouped with agent message):
   - Purple colored thinking events
   - Agent name with "(thinking)" label
   - Stage names: "Reasoning", "Response Generation", "Constitutional Validation"

2. **Expandable thinking section** below agent messages:
   - Button: "🧠 Show thinking process (3 steps)"
   - Each step shows:
     - Stage name
     - Status (✅ complete, ⚠️ warning, ❌ error)
     - Details (what the agent read, analyzed, etc.)
     - Timestamp

3. **Database persistence**:
   - All thinking steps in `events` table with `event_type = 'agent_thinking'`
   - Session summaries in `agent_memories` table with `memory_type = 'thinking_session'`

---

## Test It Now!

1. Open the debate room: http://localhost:3000/room?debate_id=011fe524-af70-4519-84b3-0ba99046479c
2. Click "Next Turn"
3. Watch for thinking events in real-time
4. After agent responds, click "🧠 Show thinking process"
5. Expand to see Constitutional AI pipeline stages

---

## Technical Notes

- **WebSocket Event Type**: `agent_thinking`
- **Event Envelope Format**: Standard format with `type`, `debate_id`, `sender_type`, `sender_id`, `payload`
- **Frontend Filtering**: Events are filtered from main feed but attached to `agent_message` events
- **Persistence**: Both individual steps (events table) and session summaries (agent_memories table)
- **Non-blocking**: All broadcasts are async and won't slow down agent turns
