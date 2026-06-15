# Quick Start Checklist - Arinar Meeting Launch

Use this checklist to ensure smooth meeting launch without errors.

---

## ✅ Pre-Launch Checklist

### 1. OpenRouter API Key
- [ ] Have valid OpenRouter API key (from https://openrouter.ai/keys)
- [ ] Key format: `sk-or-v1-...` (new) or `sk-...` (legacy)
- [ ] Key has credits/balance (check https://openrouter.ai/activity)
- [ ] Key saved in Arinar Settings page
- [ ] Test button shows ✅ "Connected"

**If Test Fails:**
- Get new key from openrouter.ai
- Check format (must start with `sk-`)
- Add credits to account

---

### 2. Meeting Setup (Steps 1-6)

#### Step 1: Meeting Details ✅
- [ ] Title entered
- [ ] Purpose/problem statement entered
- [ ] Agenda items added (optional but recommended)
- [ ] Desired outcomes defined (optional but recommended)
- [ ] Duration set (default: 30 min)

#### Step 2: Materials ✅
- [ ] Add text snippets OR
- [ ] Add website links OR
- [ ] Upload files (available after creating debate)
- [ ] At least 1 material recommended (optional)

#### Step 3: Participants ✅
- [ ] 2-3 agents selected (minimum 2)
- [ ] Turn order defined with ↑/↓ arrows
- [ ] Agent #1 should speak first
- [ ] No duplicate agents

**Recommended Agents:**
- Senior PM (Pragmatic) - strategic thinking
- Senior Engineer (Pragmatic) - technical perspective  
- First Principles Thinker - analytical approach

#### Step 4: Memory (Optional) ✅
- [ ] Skip or import relevant past debates
- [ ] Memory helps agents with context

#### Step 5: Preflight ✅
- [ ] Click "Start Preparation"
- [ ] Wait for all agents: 0/X → X/X ready
- [ ] All statuses: ✅ "success"
- [ ] View prep pack to verify agent understanding
- [ ] Can retry failed agents if needed

**If Preflight Fails:**
- Check OpenRouter key
- Retry individual agent
- Skip agent as last resort

#### Step 6: Review & Launch ✅
- [ ] Review all settings
- [ ] Click "Launch Meeting"
- [ ] Wait 3-5 seconds for first agent

---

## ✅ Post-Launch Checklist

### Room Page Loads
- [ ] Debate title visible
- [ ] Participants list shows agents
- [ ] "Live Feed" section loaded
- [ ] "Next Turn" button visible
- [ ] Controls show "Running" state

### First Agent Speaks (Auto-Triggered)
- [ ] Wait 3-5 seconds after launch
- [ ] First agent message appears in feed
- [ ] Message format: **Agent Name** + content
- [ ] No error messages

**If No Message:**
- Check browser console (F12) for errors
- Verify OpenRouter key is valid
- Click "▶ Next Turn" button manually

### Continue Debate
- [ ] Click "▶ Next Turn" for next agent
- [ ] Each agent speaks in defined turn order
- [ ] Messages stream to feed
- [ ] Can intervene with human messages
- [ ] Can pause/resume debate

---

## 🚨 Common Errors & Fixes

### Error: "Failed to trigger next turn: OpenRouter API authentication failed"
**Cause:** Invalid/expired API key  
**Fix:** Get fresh key from openrouter.ai → Update in Settings

### Error: "Failed to trigger next turn: Internal Server Error"
**Cause:** OpenRouter service issue (502)  
**Fix:** Wait 5-10 min, try again OR manually click "Next Turn"

### Error: "Insufficient credits"
**Cause:** OpenRouter account balance = $0  
**Fix:** Add credits at https://openrouter.ai/credits

### No Errors But No Messages
**Cause:** SSE connection not established  
**Fix:** Refresh page, check network tab for `/events/stream`

### Agents Stuck in "QUEUED" (Step 5)
**Cause:** Preflight backend error  
**Fix:** Check API logs, retry preparation

---

## ✅ Success Indicators

When everything works correctly:

1. **Setup Complete:** All 6 steps green ✅
2. **Preflight:** All agents "success" status
3. **Launch:** Smooth transition to room
4. **First Agent:** Speaks within 5 seconds
5. **Debate Flows:** Each turn generates response
6. **No 500 Errors:** Clean console log

---

## 🎯 Expected Timeline

- **Setup (Steps 1-4):** 2-3 minutes
- **Preflight (Step 5):** 5-10 seconds
- **Review (Step 6):** 10 seconds
- **Launch → First Message:** 3-5 seconds
- **Each Turn:** 3-5 seconds

**Total Time to First Agent Message:** ~3-5 minutes

---

## 💡 Pro Tips

1. **Test API Key First** - Don't skip Settings test
2. **Use 2-3 Agents** - More agents = longer debate
3. **Define Turn Order** - Ensures logical flow
4. **Add Materials** - Richer context = better responses
5. **Check Prep Packs** - Verify agents understand task
6. **Monitor Credits** - Watch OpenRouter usage

---

## 📞 Need Help?

If following this checklist and still having issues:

1. Check `/tmp/arinar-api.log` for backend errors
2. Check browser console (F12) for frontend errors
3. Verify OpenRouter status: https://status.openrouter.ai/
4. Check database connection (Supabase)
5. Restart API server if needed

---

**Last Updated:** Feb 11, 2026  
**Version:** 1.0 (Post auto-trigger fix)
