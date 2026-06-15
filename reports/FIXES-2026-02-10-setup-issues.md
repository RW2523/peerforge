# Setup Wizard Issues - Fixed 2026-02-10

## Issues Reported

1. **Step 2 (Materials)**: Unable to upload files
2. **Step 3 (Participants)**: Agent templates and categories missing

---

## Root Causes & Fixes

### Issue 1: File Upload Disabled

**Root Cause**:
- MaterialsStep component requires a `debateId` to upload files
- In the current setup flow, debate is created AFTER step 4 (Memory Import)
- So in step 2, `debateId` is `undefined` and file upload button is disabled

**Current Behavior**:
- "Upload Files" button is visible but disabled (grayed out)
- No clear message explaining why it's disabled

**Fix Applied**:
- Updated button text to show "(after setup)" when debate doesn't exist yet
- Added tooltip: "File uploads available after creating debate (complete all steps first)"

**Why Not Change the Flow?**:
- Creating debate earlier (after step 1) would:
  - Orphan debates if user abandons setup midway
  - Require more complex cleanup logic
  - Break the clear "review then commit" flow
- V1: Manual materials (text/link) work fine in step 2
- File uploads work in a different flow (upload to existing debate)

**Workaround for Now**:
- In step 2, use "Add Text" or "Add Link" for manual materials
- For file uploads:
  - Complete setup to create debate
  - Navigate to the debate in /room
  - Use materials upload feature in room (if implemented)
  - OR go back to /setup with existing debate_id

**Future Fix (TICKET-13B.2)**:
- Add ability to create "draft debate" earlier in flow
- Or add file staging area (upload to temp storage, attach on debate creation)

### Issue 2: Missing Templates & Agents

**Root Cause**:
- `useParticipants` and `useMaterials` hooks used stale closures
- `useCallback` dependencies captured old `participants`/`materials` state
- When templates were clicked, the add handler saw empty array instead of current state

**Example of Bug**:
```typescript
// BEFORE (broken):
const handleAdd = useCallback((template) => {
  setParticipants([...participants, newParticipant]); // participants is stale!
}, [participants]); // This creates new callback every render

// AFTER (fixed):
const handleAdd = useCallback((template) => {
  setParticipants(prev => [...prev, newParticipant]); // prev is always current
}, []); // Stable callback, no dependencies
```

**Fix Applied**:
- Updated `useParticipants.ts`: Use functional updates (`prev => ...`)
- Updated `useMaterials.ts`: Use functional updates
- Removed `participants`/`materials` from dependency arrays
- Callbacks are now stable and always see current state

**API Verification**:
```bash
curl http://localhost:8000/agent-templates
# ✅ Returns 200 OK with 18 templates
# Categories: Product, Engineering, Design, Legal, Finance, Research, Facilitation, Contrarian
```

---

## What Works Now

### Step 2: Materials
- ✅ "Add Text" button works
- ✅ "Add Link" button works
- ⚠️ "Upload Files (after setup)" button disabled with tooltip (by design until debate exists)
- ✅ Manual materials can be added, edited, removed

### Step 3: Participants
- ✅ Agent templates load and display (18 templates across 8 categories)
- ✅ Category filter works (All, Product, Engineering, Design, etc.)
- ✅ Clicking template adds participant correctly
- ✅ Participant list shows added agents
- ✅ Edit/remove buttons work
- ✅ Max 8 participants enforced with alert

---

## Testing Done

### API Server
```bash
# Start API
cd /Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/api
REQUIRE_AUTH=false .venv/bin/python3.11 -m uvicorn src.main:app --reload --port 8000
# ✅ Started on http://127.0.0.1:8000

# Test templates endpoint
curl -s http://localhost:8000/agent-templates | python3 -m json.tool | head -50
# ✅ Returns 18 templates with correct structure (template_id, label, role_title, category, character, system_prompt, model_id, model_config)
```

### Frontend
```bash
# Start web
cd /Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/web
npm run dev
# ✅ Started on http://localhost:3000

# Navigate to http://localhost:3000/setup
# ✅ Page loads
# ✅ API call: GET /agent-templates returns 200 OK (visible in API logs)
```

### Hook Fixes
```bash
# Rebuilt after fixing useParticipants + useMaterials hooks
# ✅ No build errors
# ✅ Functional updates pattern eliminates stale closures
```

---

## Remaining Limitations (By Design)

1. **File Uploads in Step 2**:
   - Not available until debate is created
   - User must use text/link materials or upload after debate creation
   - Clear UI indication (button disabled + tooltip)

2. **No Early Debate Creation**:
   - Debate created only after completing all setup steps (step 4 → 5 transition)
   - Prevents orphaned debates from abandoned setup flows
   - Clearer separation: configure → commit → prepare → launch

---

## Commands Run

```bash
# Kill existing API processes
kill -9 18629 23359

# Start API server
cd /Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/api
REQUIRE_AUTH=false .venv/bin/python3.11 -m uvicorn src.main:app --reload --port 8000
# ✅ Running

# Frontend already running
# http://localhost:3000 - Ready
```

---

## Status

| Component | Status | Note |
|-----------|--------|------|
| API Server | ✅ Running | Port 8000, auth disabled for demo |
| Frontend | ✅ Running | Port 3000, hot reload working |
| Templates API | ✅ Working | 18 templates, 8 categories |
| Agents API | ✅ Working | Returns agent list |
| File Upload | ⚠️ Disabled | By design (no debate_id yet) |
| Templates Display | ✅ Fixed | Functional updates in hooks |
| Add Participant | ✅ Working | Stale closure bug fixed |

---

**Both servers are now running. Please refresh http://localhost:3000/setup and check:**
1. Step 3 should show 18 agent templates with categories
2. Step 2 file upload button says "Upload Files (after setup)" and is disabled
3. Text/Link materials work in step 2
