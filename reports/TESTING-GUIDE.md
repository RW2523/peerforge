# Testing Guide - Agent Behaviors & UI 🧪

## Quick Test Protocol

### 1. UI Visual Check ✅
**What to verify:**
- Right panel is **420px wide** (not cramped)
- Cards have **18px padding** (spacious)
- **Hover effects** work (border glow + shadow)
- Tabs have rounded tops
- Lock icon 🔒 appears on private messages
- Empty states are prominent with large icons

**How to test:**
1. Open the meeting room
2. Resize browser to verify responsive layout
3. Hover over cards - should see glow effect
4. Switch between tabs - should be smooth

---

### 2. Autonomous Behaviors Pipeline ✅

**Expected Console Output:**

```bash
# After each turn (after turn 2), you might see:

🎭 Triggering autonomous behaviors for Consumer Advisor...
    ✅ Coalition decision: {'members': ['Consumer Advisor', 'Expert Analyst'], 'strategy': 'Focus on data quality'}
🤝 Coalition formed: ['Consumer Advisor', 'Expert Analyst']

# OR

🎭 Triggering autonomous behaviors for Rational Analyst...
    ℹ️  Rational Analyst chose not to form coalition
    ✅ Private message: Rational Analyst → Expert Analyst: "Let's coordinate on methodology..."
💬 Private message: Rational Analyst → Expert Analyst
```

**What to verify:**
- 🎭 Trigger message appears ~25% of turns (after turn 2)
- Coalitions form occasionally (12.5% of turns)
- Private messages appear occasionally (7.5% of turns)
- UI updates in real-time

---

### 3. WebSocket Connection ✅

**Chrome DevTools → Network Tab:**
1. Filter by `WS` (WebSocket)
2. Look for `/ws/debate/{debate_id}`
3. Status should be `101 Switching Protocols`
4. Click connection → Messages tab
5. Watch for event types:
   - `agent_message`
   - `coalition_formed` ⭐ NEW
   - `private_message` ⭐ NEW
   - `typing_indicator`
   - `presence_update`

---

### 4. Full End-to-End Test

**Setup (2 minutes):**
```
1. Go to Settings → Add OpenRouter API key
2. Go to Setup → Create new debate
   - Title: "Should we use React or Vue?"
   - 3 participants (any personas)
   - 3 rounds
3. Complete preflight (watch for web research)
4. Launch debate
```

**Testing (5 minutes):**
```
Turn 1: Click "Next Turn"
  → Agent 1 speaks
  → Agent Behaviors panel is empty (expected - need 2+ turns)

Turn 2: Click "Next Turn"
  → Agent 2 speaks
  → Watch console for "🎭 Triggering autonomous behaviors..."
  → Might see coalition or private message appear!

Turn 3-9: Keep clicking "Next Turn"
  → ~25% chance to see autonomous behaviors
  → Coalitions tab: Check for alliance cards
  → Private Msgs tab: Check for secret messages
  → Sub-tasks tab: Will be empty for now
```

**Success Criteria:**
- ✅ UI is spacious and responsive
- ✅ WebSocket events arrive in real-time
- ✅ Console shows "🎭 Triggering..." after some turns
- ✅ At least 1 coalition OR private message appears by turn 9

---

### 5. Error Scenarios (Should Not Crash)

**Test graceful failures:**

```
Scenario 1: Disconnect OpenRouter API key mid-debate
  → Autonomous behaviors fail silently
  → Main debate continues normally
  → Console: "⚠️ Coalition analysis failed: ..."

Scenario 2: Close WebSocket connection
  → UI shows "Reconnecting..."
  → Events resume after reconnect
  → No duplicate events

Scenario 3: Refresh page mid-debate
  → Rejoins debate successfully
  → Previous events load from API
  → New events stream via WebSocket
```

---

### 6. Performance Check

**Metrics to monitor:**

| Metric | Expected | How to Check |
|--------|----------|--------------|
| Turn response time | < 5s | Click "Next Turn" → Message appears |
| WebSocket latency | < 100ms | DevTools Network → WS → Timing |
| UI re-render | < 16ms | React DevTools Profiler |
| Autonomous trigger | ~1-2s extra | Console timestamps |

**Should NOT see:**
- ❌ UI freezing
- ❌ Multiple duplicate events
- ❌ Turn failures due to autonomy
- ❌ WebSocket disconnections

---

### 7. Visual Regression Check

**Before/After Comparison:**

```
BEFORE UI:
┌─────────────────────────┐ 320px
│ Cramped header          │
│ ┌─────────┐ 12px pad    │
│ │Coalition│             │
│ └─────────┘             │
│ ↓ 12px gap              │
└─────────────────────────┘

AFTER UI:
┌───────────────────────────────┐ 420px
│  Spacious header              │
│  Better subtitle              │
│  ┌───────────────┐ 18px pad   │
│  │  Coalition    │            │
│  │  [Hover glow] │            │
│  └───────────────┘            │
│  ↓ 16px gap                   │
└───────────────────────────────┘
```

**Checklist:**
- [ ] Right panel wider
- [ ] Cards more spacious
- [ ] Hover effects present
- [ ] Tabs have rounded corners
- [ ] Lock icons on private messages
- [ ] Empty states prominent
- [ ] Color-coded borders

---

### 8. Debug Commands

**Backend health:**
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy",...}
```

**Check WebSocket endpoint:**
```bash
# In browser console:
ws = new WebSocket('ws://localhost:8000/ws/debate/YOUR_DEBATE_ID?token=YOUR_TOKEN');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

**Force autonomous behavior (for debugging):**
```python
# In turn_orchestrator.py, temporarily change:
should_trigger_autonomy = random.random() < 1.0  # Always trigger
```

---

### 9. Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| No autonomous behaviors | Probability too low | Wait for more turns (25% chance) |
| UI cramped | Old CSS cached | Hard refresh (Cmd+Shift+R) |
| WebSocket not connecting | Backend down | Check `curl localhost:8000/health` |
| Events not appearing | Wrong event type | Check console for event.type |
| Coalition JSON error | LLM response invalid | Autonomy fails silently - OK |

---

### 10. Expected Behavior Summary

**Turn Flow:**
```
User clicks "Next Turn"
  → Backend: TurnOrchestrator.trigger_next_turn()
  → Agent generates response (2-5s)
  → Message persisted to database
  → Message broadcast via WebSocket
  → Frontend: Message appears in feed
  → (25% chance) Backend: Autonomous behaviors triggered
  → (If triggered) Coalition/message broadcast
  → (If broadcast) UI updates in Agent Behaviors panel
```

**Timing:**
- Turn response: 2-5 seconds
- Autonomous behaviors: +1-2 seconds (async, non-blocking)
- UI update: < 100ms after WebSocket event

---

## Status: ✅ READY TO TEST

All systems verified and documented. Backend running, frontend deployed.

**Next Steps:**
1. Create a test debate
2. Progress through 9 turns
3. Verify UI improvements
4. Watch for autonomous behaviors
5. Report any issues
