# Fix: Step 1 Participant Validation Bug 🐛

**Date:** February 13, 2026  
**Status:** ✅ FIXED

---

## Problem

After enabling early debate creation (to allow file uploads in Step 2), users were seeing this error in **Step 1**:

```
❌ "At least 1 participant required"
```

**But participants aren't selected until Step 3!**

---

## Root Cause

When I changed the flow to create the debate after Step 1 (to enable file uploads in Step 2), the `handleCreateDebate()` function was being called too early.

**Old Flow:**
```
Step 1: Basic Info
Step 2: Materials
Step 3: Participants
Step 4: Click "Create" → handleCreateDebate() called ✅
```

**New Flow (buggy):**
```
Step 1: Click "Next" → handleCreateDebate() called ❌
  └─ Checks: if (participants.length === 0) alert('...')
  └─ But participants aren't selected yet!
Step 2: Materials
Step 3: Participants
Step 4: Memory
```

### The Code That Caused It

**File:** `useDebateSetupActions.ts`

```typescript
const handleCreateDebate = async () => {
  // ...
  if (participants.length === 0) {  // ❌ This ran in Step 1
    alert('At least 1 participant required');
    return null;
  }
  // ...
};
```

---

## Solution

**Removed the participant validation from `handleCreateDebate()`**

**Why it's safe:**
1. ✅ UI validation in `useSetupValidation.ts` already prevents advancing from Step 3 without participants
2. ✅ Backend will validate participants when launching the debate
3. ✅ Debate can be created as a "draft" in Step 1, participants added later
4. ✅ This matches the new flow where debate is created early for file uploads

### Fixed Code

```typescript
const handleCreateDebate = async () => {
  const {
    workspaceId,
    title,
    problemStatement,
    // ... other fields
    participants,
  } = options;

  // Allow creating debate early (Step 1) without participants
  // Participants will be added in later API calls or when launching
  // Only validate participants if we're past Step 1 (i.e., participants should be selected)
  // This check is handled by the UI validation in useSetupValidation.ts

  setIsLoading(true);
  // ... continue with debate creation
};
```

---

## Validation Flow (Corrected)

### Step-by-Step Validation:

**Step 1: Basic Info**
```typescript
canGoNext = Boolean(title.trim() && problemStatement.trim())
✅ Only checks title and problem statement
❌ Does NOT check participants
```

**Step 2: Materials**
```typescript
canGoNext = true  // Always allowed (materials are optional)
```

**Step 3: Participants**
```typescript
canGoNext = participants.length > 0
✅ NOW checks for participants
```

**Step 4: Memory**
```typescript
canGoNext = true  // Memory import is optional
```

**Step 5: Preflight**
```typescript
canGoNext = false  // No "next" button (launch instead)
```

---

## User Experience

### Before Fix:
```
User: Fills in "Meeting Title" and "Problem Statement"
User: Clicks "Next"
System: ❌ "At least 1 participant required"
User: 😕 "But I haven't gotten to participants yet..."
```

### After Fix:
```
User: Fills in "Meeting Title" and "Problem Statement"
User: Clicks "Next"
System: ✅ Creates debate, moves to Step 2 (Materials)
User: Uploads files if needed
User: Clicks "Next" → Step 3 (Participants)
User: Selects participants
User: Can't click "Next" until at least 1 participant selected ✅
```

---

## Testing Checklist

- [x] Step 1: Fill title + problem → Click "Next" → No error ✅
- [x] Step 1: Empty title → "Next" disabled ✅
- [x] Step 2: File upload button works ✅
- [x] Step 3: No participants → "Next" disabled ✅
- [x] Step 3: Add 1+ participants → "Next" enabled ✅
- [x] Step 4: Can proceed regardless of memory import ✅
- [x] Step 5: Preflight runs correctly ✅
- [x] Full flow: Complete setup end-to-end ✅

---

## Related Changes

This fix is related to the file upload feature:

**Original Issue:** File uploads were disabled until Step 4  
**Solution:** Create debate after Step 1  
**Side Effect:** Participant validation triggered too early ❌  
**This Fix:** Remove premature participant check ✅

**Related Files:**
- `apps/web/src/app/setup/page.tsx` - Early debate creation
- `apps/web/src/hooks/useDebateSetupActions.ts` - Validation removal (this fix)
- `apps/web/src/hooks/useSetupValidation.ts` - Step-level validation

---

## Why This Design is Correct

### Backend Perspective:
```python
# Debate creation endpoint accepts empty participants
POST /debates/setup
{
  "title": "My Meeting",
  "problem_statement": "...",
  "participants": []  # ✅ Empty is OK
}

# Participants can be added later
POST /debates/{id}/participants
{
  "participant_id": "..."
}
```

### Frontend Perspective:
```typescript
// Step 1: Create "draft" debate
const debate = await createDebate({
  title,
  problemStatement,
  participants: []  // Empty initially
});

// Step 3: Add participants (updates existing debate)
const debate = await createDebate({
  ...existingData,
  participants: [...]  // Now populated
});
```

### Preflight Perspective:
```python
# Preflight validation (Step 5) ensures participants exist
if len(debate.participants) == 0:
    raise ValueError("Cannot start preflight without participants")
```

**Result:** Validation happens at the right time! ✅

---

## Status: ✅ FIXED

**Symptom:** "At least 1 participant required" in Step 1  
**Root Cause:** Early debate creation + premature validation  
**Solution:** Remove participant check from `handleCreateDebate`  
**Validation:** Now handled correctly in Step 3 via `useSetupValidation`  
**Testing:** All scenarios pass  

**Users can now progress through setup without false errors!** 🎉
