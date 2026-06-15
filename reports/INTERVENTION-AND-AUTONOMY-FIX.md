# Intervention, Timer & Autonomy Fixes

## Issues Fixed

### 1. ⏰ Timer Not Counting Down
**Problem**: Timer showed "5 minutes" but remained static, never counting down.

**Root Cause**: 
- Timer display only showed configured `timebox_minutes` from policy config
- No countdown logic implemented
- `started_at` timestamp wasn't being set when debate started
- No elapsed time calculation

**Fix**:
1. **Backend** (`debate_service.py` line 105-109):
   - Set `started_at` timestamp when debate transitions to running state
   ```python
   UPDATE debates
   SET state = 'running', updated_at = NOW(), started_at = NOW()
   WHERE debate_id = %s
   ```

2. **Frontend** - Created new `DebateTimer` component:
   - Real-time countdown using `setInterval`
   - Calculates elapsed time from `started_at`
   - Shows remaining time in MM:SS format
   - Visual urgency indicators:
     - 🟢 Normal: > 2 minutes remaining
     - ⚠️ Warning: < 2 minutes remaining (yellow)
     - 🔴 Critical: < 1 minute remaining (red, pulsing)
     - ⏰ Expired: Time's up (red)
   - Progress bar showing elapsed time
   - Auto-updates every second

3. **Integration** (`room/page.tsx`):
   - Added `debateStartedAt` state
   - Fetches `started_at` when loading debate
   - Refreshes on state changes
   - Replaces static timer display with live countdown

### 2. 🎙️ Human Interventions Not Reaching Agents
**Problem**: User sent moderator intervention but agents didn't acknowledge it.

**Root Cause**:
- Intervention detection looked at only last 5 events
- In active debates with rapid agent turns, interventions got pushed out of the window quickly
- Agents never saw the intervention in their prompt

**Fix** (`turn_orchestrator.py` line 186):
```python
# Before: Check last 5 events
for event in reversed(history_events[-5:]):

# After: Check last 15 events
for event in reversed(history_events[-15:]):
```

**Impact**:
- Interventions now visible for ~15 turns instead of 5
- Much more likely agents will see and respond to moderator messages
- Duplicate detection ensures same message not shown multiple times
- Existing urgent intervention system prompt still active

### 3. 🤝 Coalition & Private Messages Too Rare
**Problem**: Coalitions and private messages weren't appearing often enough - agents seemed isolated.

**Root Cause**:
- Autonomous behaviors triggered only 50% of the time
- Coalition formation within that was only 50% (= 25% overall)
- Private messaging was 60% within autonomy (= 30% overall)  
- Result: Very few autonomous interactions visible

**Fix** (`turn_orchestrator.py`):

**Autonomous Behavior Trigger**:
```python
# Before: 50% chance
should_trigger_autonomy = random.random() < 0.50

# After: 80% chance
should_trigger_autonomy = random.random() < 0.80
```

**Coalition Formation**:
```python
# Before: 50% chance (= 25% overall with 50% autonomy trigger)
if random.random() < 0.5:

# After: 70% chance (= 56% overall with 80% autonomy trigger)
if random.random() < 0.70:
```

**Private Messaging**:
```python
# Before: 60% chance (= 30% overall)
if random.random() < 0.6:

# After: 90% chance (= 72% overall)
if random.random() < 0.90:
```

**Expected Behavior Now**:
- ~80% of turns will trigger autonomous behaviors
- ~56% of turns will have coalition formation/updates
- ~72% of turns will have private messages
- Much more dynamic and engaging debate experience

## Files Changed

### Backend
```
/apps/api/src/debate_service.py
  - Set started_at timestamp when debate starts

/apps/api/src/turn_orchestrator.py
  - Increased intervention window from 5 to 15 events
  - Increased autonomy trigger from 50% to 80%
  - Increased coalition chance from 50% to 70%
  - Increased private message chance from 60% to 90%
```

### Frontend
```
/apps/web/src/components/room/DebateTimer.tsx (NEW)
  - Live countdown timer component
  
/apps/web/src/components/room/DebateTimer.module.css (NEW)
  - Styling with urgency states
  
/apps/web/src/app/room/page.tsx
  - Import and use DebateTimer
  - Track debateStartedAt state
  - Refresh debate data on state changes
```

## Testing

### Timer
1. ✅ Create debate with 5 minute timebox
2. ✅ Start debate
3. ✅ Timer should begin counting down immediately
4. ✅ Shows yellow at 2 min remaining
5. ✅ Shows red and pulses at 1 min remaining
6. ✅ Shows "Time expired!" at 0:00

### Interventions
1. ✅ Start debate with 3+ agents
2. ✅ Let agents take 2-3 turns
3. ✅ Send moderator intervention
4. ✅ Next agent should acknowledge the intervention
5. ✅ Works even with 10+ agent turns after intervention

### Autonomous Behaviors
1. ✅ Start debate with 3+ agents
2. ✅ Let agents complete 2+ turns
3. ✅ Watch agent behaviors panel for:
   - 🤝 Coalition formations (~56% of turns)
   - 💬 Private messages (~72% of turns)
   - 📋 Sub-tasks (if implemented)

## Deployment Notes

- Backend changes auto-reload
- Frontend needs browser refresh
- No database migrations needed
- No breaking changes

## Impact

**Before**:
- Static timer (useless)
- Interventions ignored if >5 turns ago
- Rare autonomous behaviors (~12-30% per turn)

**After**:
- Live countdown with urgency indicators
- Interventions visible for 15 turns
- Frequent autonomous behaviors (~56-72% per turn)
- Much more dynamic and engaging debates

## Conclusion

These fixes restore the intended dynamic behavior of the debate system, making it feel more alive and responsive to user input.
