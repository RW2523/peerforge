# TICKET-16: Meeting Setup Flow Enhancement & Fixes

**Created:** 2026-02-11  
**Status:** In Progress  
**Priority:** High  
**Affects:** Setup flow (Steps 1-5), Room page, Preflight UI

---

## Problem Statement

The meeting setup flow works but has critical issues and missing features:

### Current Issues
1. ❌ **Preflight prep UI is basic** - can't see detailed agent preparation
2. ❌ **Debates don't start after launch** - no agent messages appear in room
3. ⚠️ **Missing context fields** - no agenda, desired outcomes capture
4. ⚠️ **No turn order control** - agents speak in random/creation order
5. ⚠️ **No website link support** - only file uploads

### User Requirements
> "User enters title, purpose, **agenda, desired outcomes** → provides materials (**website links + documents**) and duration → selects agents and **defines turn order** → memory → **preflight shows detailed prep for each participant** → launch meeting and **see debates happen**"

---

## Solution Design

### Phase 1: Fix Critical Issues (30 min)

#### Issue 1: Debates Not Starting After Launch
**Root Cause:** Need to verify:
- [ ] `handleLaunchDebate` calls `api.startDebate()` ✅ (already done)
- [ ] Room page auto-triggers first turn
- [ ] `TurnOrchestrator` is working
- [ ] "Next Turn" button functionality

**Files to check:**
- `apps/web/src/app/room/page.tsx`
- `apps/web/src/components/room/DebateControls.tsx`
- `apps/api/src/routes/turns.py`
- `apps/api/src/turn_orchestrator.py`

#### Issue 2: Preflight Prep UI Enhancement
**Current:** Basic "View prep pack" button shows raw text
**Target:** Rich dialog showing:
- Meeting context understanding (title, purpose, agenda, outcomes)
- Materials analyzed (list + summaries)
- Memory chunks used (count + sources)
- Agent's preparation notes
- Ready status indicator

**Files to modify:**
- `apps/web/src/components/setup/PreflightDialogs.tsx` (enhance PrepPackDialog)
- `apps/web/src/components/setup/PreflightStep.tsx` (better status display)

---

### Phase 2: Add Missing Fields (20 min)

#### Step 1 Enhancement: Add Agenda & Desired Outcomes
**Schema changes:**
```sql
-- debates.policy_config already supports JSONB, add fields:
{
  "problem_statement": "...",
  "agenda": ["item 1", "item 2", "item 3"],  // NEW
  "desired_outcomes": ["outcome 1", "outcome 2"],  // NEW
  "timebox_minutes": 30
}
```

**UI changes:**
- Add textarea for Agenda (comma-separated or bulleted)
- Add textarea for Desired Outcomes
- Update `setup/page.tsx` state
- Update `api.setupDebate()` payload

#### Step 2 Enhancement: Add Website Links
**Schema:** Use existing `materials` table
- `source_type` can be 'upload' or 'url'
- Add URL input field
- Backend: Fetch & process URL content

**UI changes:**
- Add URL input field with "Add Link" button
- Display URLs in materials list
- Handle URL processing/preview

---

### Phase 3: Turn Order Control (15 min)

#### Step 3 Enhancement: Define Turn Order
**Options:**
1. **Simple:** Add "Order" number input per participant
2. **Rich:** Drag-and-drop reordering UI

**Implementation:**
- Store order in `participants.participant_order` (new column) OR
- Use array position in setup payload
- `TurnOrchestrator` respects order
- Visual indicator in UI

**Files:**
- `apps/web/src/components/setup/ParticipantsList.tsx`
- `apps/api/src/routes/setup.py`
- `apps/api/src/turn_orchestrator.py`

---

### Phase 4: Preflight Context Enhancement (15 min)

**Backend:** Include new fields in prep pack generation
- Read agenda, outcomes from policy_config
- Include in prompt to OpenRouter
- Store in prep pack metadata

**Files:**
- `apps/api/src/tasks/preflight.py` (prepare_participant_preflight)

---

## Implementation Plan

### Priority 1 (Do First): Fix Debates Not Starting
1. Verify room page loads debate correctly
2. Check if "Next Turn" button triggers agent
3. Test TurnOrchestrator with real debate
4. Add auto-trigger for first turn (optional)

### Priority 2: Enhance Preflight UI
1. Redesign PrepPackDialog with sections
2. Add material preview
3. Add memory context display
4. Style improvements

### Priority 3: Add Fields
1. Agenda field (Step 1)
2. Desired outcomes field (Step 1)
3. Website links input (Step 2)
4. Backend URL processing

### Priority 4: Turn Order
1. Add order field to participants
2. UI for setting order
3. Update TurnOrchestrator to respect order

---

## Testing Checklist

- [ ] Complete flow: Create meeting → Add materials → Select agents → Memory → Preflight
- [ ] Preflight shows detailed prep for each agent
- [ ] Launch meeting successfully
- [ ] Agents take turns speaking in defined order
- [ ] Debate messages appear in room
- [ ] All new fields persist correctly

---

## Files Affected

### Frontend
- `apps/web/src/app/setup/page.tsx` - Add new fields, state management
- `apps/web/src/app/room/page.tsx` - Fix debate loading/auto-start
- `apps/web/src/components/setup/PreflightDialogs.tsx` - Enhanced prep pack dialog
- `apps/web/src/components/setup/PreflightStep.tsx` - Better status display
- `apps/web/src/components/setup/ParticipantsList.tsx` - Turn order UI
- `apps/web/src/components/room/DebateControls.tsx` - Verify "Next Turn"
- `apps/web/src/lib/api.ts` - Add fields to payload

### Backend
- `apps/api/src/tasks/preflight.py` - Include agenda/outcomes in prep
- `apps/api/src/turn_orchestrator.py` - Respect turn order
- `apps/api/src/routes/setup.py` - Accept new fields
- `apps/api/src/routes/turns.py` - Verify working
- `apps/api/src/routes/materials.py` - URL processing (optional)

### Database
- Migration: Add `participant_order` column (if needed)
- No schema changes needed for agenda/outcomes (use policy_config JSONB)

---

## Estimated Time
- Priority 1 (Fix debates): 30 min
- Priority 2 (Preflight UI): 30 min
- Priority 3 (Add fields): 20 min
- Priority 4 (Turn order): 15 min

**Total: ~90 min** (1.5 hours)

---

## Next Steps

1. Start with **Priority 1** - Fix debates not starting
2. Then **Priority 2** - Enhance preflight UI
3. Add fields incrementally (Priority 3 & 4)
4. Test full flow end-to-end
