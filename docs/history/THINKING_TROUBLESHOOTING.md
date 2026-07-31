# Thinking Display Troubleshooting Guide

## What Was Fixed

### 3 Critical Bugs Fixed ✅

1. **Missing Import** - `AgentThinkingService` wasn't imported in `turn_orchestrator.py`
2. **Wrong Column Name** - Used `occurred_at` instead of `created_at` for events table
3. **Improper WebSocket Format** - Wasn't sending proper event envelopes

All fixes are now live - server auto-reloaded.

---

## How to Test

### Step 1: Open Browser Console
1. Open debate room: http://localhost:3000/room?debate_id=011fe524-af70-4519-84b3-0ba99046479c
2. Open browser DevTools (F12 or Cmd+Option+I)
3. Go to Console tab

### Step 2: Click "Next Turn"
Watch the console for these debug messages:

```
🧠 Found thinking events: X [...]
🧠 Attaching N thinking events to message from Agent Name
```

### Step 3: Check the Feed
After the agent responds, you should see:
- Agent message appears
- Below it: **"🧠 Show thinking process (X steps)"** button
- Click to expand and see thinking stages

---

## What You Should See

### In the Console:
```javascript
🧠 Found thinking events: 3 
[
  {
    type: "agent_thinking",
    debate_id: "...",
    sender_id: "Trend Forecaster",
    payload: {
      agent_name: "Trend Forecaster",
      thinking_type: "constitutional_ai",
      stage: "Reasoning",
      status: "complete",
      details: [...]
    }
  },
  // ... more thinking events
]

🧠 Attaching 3 thinking events to message from Trend Forecaster
```

### In the UI:
Below each agent message:
```
┌─────────────────────────────────────────────┐
│ 🧠 Show thinking process (3 steps)         │  ← Click to expand
└─────────────────────────────────────────────┘

When expanded:
┌─────────────────────────────────────────────┐
│ 🧠 Hide thinking process (3 steps)         │
│                                             │
│ Stage: Reasoning                            │
│ Status: ✅ complete                         │
│ Details:                                    │
│ • Read participant: John Smith             │
│ • Read participant: Jane Doe               │
│ • Analyzed 12 messages                     │
│                                             │
│ Stage: Response Generation                 │
│ Status: ✅ complete                         │
│ ...                                         │
└─────────────────────────────────────────────┘
```

---

## If Thinking Still Not Showing

### Check 1: Are Thinking Events Arriving?
Open browser console and look for `🧠 Found thinking events` messages.

**If YES (events arriving)**:
- Problem is in frontend display logic
- Check EventFeed.tsx grouping logic

**If NO (no events arriving)**:
- Problem is in backend broadcast or frontend WebSocket
- Continue to Check 2

### Check 2: Check Backend Logs
```bash
tail -100 /tmp/api_logs.txt | grep -E "thinking|Reasoning|broadcast"
```

**Look for**:
```
🧠 CONSTITUTIONAL AI PIPELINE for Agent Name
  Stage 1: Reasoning...
  Stage 2: Response Generation...
  Stage 3: Constitutional Validation...
```

**If you see these** → Backend is generating thinking
**If you don't see these** → Constitutional AI isn't running

### Check 3: Check Database
```bash
cd apps/api && source .venv/bin/activate && python3 -c "
from src.database import get_db_connection, get_cursor
conn = get_db_connection()
cursor = get_cursor(conn)
cursor.execute(\"SELECT COUNT(*) FROM events WHERE event_type = 'agent_thinking'\")
count = cursor.fetchone()
print(f'Thinking events in DB: {count[0]}')
conn.close()
"
```

**If count > 0** → Thinking is being persisted
**If count = 0** → Persistence is failing

### Check 4: Check WebSocket Connection
In browser console, look for:
```
[useDebateRoom] WebSocket error
⚠️ WebSocket disconnected
```

**If disconnected**:
1. Refresh the page
2. Check API server is running: http://localhost:8000/health
3. Check for CORS errors in Network tab

### Check 5: Verify Event Envelope Format
In browser console, inspect a thinking event:
```javascript
// Should have these fields:
event = {
  type: "agent_thinking",       // ✅ Required
  debate_id: "...",              // ✅ Required
  sender_type: "agent",          // ✅ Required
  sender_id: "Agent Name",       // ✅ Required
  payload: {                     // ✅ Required
    agent_name: "...",
    thinking_type: "...",
    stage: "...",
    status: "...",
    details: [...]
  }
}
```

**If missing fields** → Backend envelope format is wrong

---

## Debug Commands

### Force a Turn via WebSocket (bypassing UI)
Open browser console:
```javascript
// Get the debate room component
// (only works if you're on the room page)

// Manually send WebSocket command
// Note: This assumes WebSocket is connected
```

### Check API Directly
```bash
curl -X POST "http://localhost:8000/debates/011fe524-af70-4519-84b3-0ba99046479c/turn/next" \
  -H "Content-Type: application/json" \
  -H "X-OpenRouter-Key: YOUR_KEY_HERE" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Watch Live Logs
```bash
tail -f /tmp/api_logs.txt | grep --line-buffered -E "thinking|Reasoning|broadcast|🧠"
```

---

## Common Issues

### Issue: "No thinking events in console"
**Cause**: WebSocket not receiving events or backend not emitting
**Fix**: 
1. Check backend logs for `🧠 CONSTITUTIONAL AI PIPELINE`
2. Check WebSocket connection status
3. Refresh page to reconnect

### Issue: "Thinking events in console but not in UI"
**Cause**: Frontend filtering or grouping issue
**Fix**: 
1. Check `EventFeed.tsx` line 103 - `agent_thinking` should be in `shouldFilterOut`
2. Check grouping logic line 128-141
3. Check if `thinkingEvents` array is attached to agent_message

### Issue: "Button shows '0 steps'"
**Cause**: Thinking events not being matched with agent message
**Fix**:
1. Check `agent_name` field matches between thinking and message
2. Check sequence_number ordering (thinking should come before message)
3. Check the 10-event window (line 136)

### Issue: "Database error: column occurred_at does not exist"
**Cause**: Fix wasn't applied
**Status**: ✅ FIXED - Changed to `created_at` in all 4 places

### Issue: "WebSocket keeps disconnecting"
**Cause**: Heartbeat timeout or server restart
**Fix**: 
1. Frontend auto-reconnects - wait 5 seconds
2. Check API server is running
3. Check firewall/proxy settings

---

## Files Modified

1. `/apps/api/src/turn_orchestrator.py` - Added import
2. `/apps/api/src/agent_thinking_service.py` - Fixed column names + envelope format
3. `/apps/web/src/components/room/EventFeed.tsx` - Added debug logging

---

## Next Steps

1. **Refresh the page** (to load latest frontend JS)
2. **Open browser console** (to see debug logs)
3. **Click "Next Turn"**
4. **Watch console for** `🧠 Found thinking events`
5. **Look below agent message for** button

If you still don't see thinking after following all steps above, share:
1. Browser console output
2. Backend logs (last 50 lines)
3. Screenshot of the UI
