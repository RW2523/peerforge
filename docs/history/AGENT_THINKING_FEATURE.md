# Agent Thinking Visibility Feature

## Overview

Real-time visibility into agent's thinking process - similar to Claude/Cursor's thinking blocks. Users can now see what agents are doing behind the scenes while waiting for responses.

---

## What You See

### During "Next Agent" Turn

Instead of just waiting, you now see **collapsible thinking blocks** showing:

```
🤔 Stage 1: Reasoning
   Evaluating stance and analyzing recent messages...
   ▼ Expand thinking
```

Click to expand and see details:
```
🤔 Stage 1: Reasoning
   Evaluating stance and analyzing recent messages...
   
   • Reading 3 past messages from this agent
   • Analyzing 5 recent conversation turns
   • Checking for user interventions: None
   • Comparing with 4 agents who have spoken
   
   ▲ Collapse
```

---

## Thinking Stages

### Stage 1: Reasoning 🤔
**What's Happening:** Agent analyzes conversation and determines stance

**Details You'll See:**
- How many past messages they're reviewing
- How many recent conversation turns they're analyzing
- Whether user interventions were detected
- How many other agents have spoken

**Example:**
```
🤔 Stage 1: Reasoning
   Evaluating stance and analyzing recent messages...
   
   • Reading 2 past messages from this agent
   • Analyzing 3 recent conversation turns
   • Checking for user interventions: Yes
   • Comparing with 2 agents who have spoken
```

Then when complete:
```
🤔 Stage 1: Complete
   Reasoning complete
   
   • Stance: AI will DESTROY more jobs than it creates in the short...
   • Confidence: 0.85
   • Stance changed: False
   • Key points identified: 4
```

---

### Stage 2: Generating Response ✍️
**What's Happening:** Agent crafts natural language message

**Details You'll See:**
- Current stance being used
- Debate rules being applied
- Checking for direct challenges
- Ensuring authentic character voice

**Example:**
```
✍️ Stage 2: Generating Response
   Crafting message based on reasoning...
   
   • Using stance: AI will DESTROY more jobs than it creates in...
   • Incorporating debate rules and personality
   • Checking for direct challenges to respond to
   • Ensuring authentic character voice
```

Then when complete:
```
✍️ Stage 2: Complete
   Response generated
   
   • Message length: 1245 characters
   • Estimated words: ~220
   • Contains citations: Yes
```

---

### Stage 3: Validation ✅
**What's Happening:** Checking message against constitutional rules

**Details You'll See:**
- Checking for hallucinations (invalid participant mentions)
- Checking for flip-flopping (consistency)
- Checking for repetition (echoing others)
- Checking for self-contradiction
- Number of valid participants being checked

**Example (Success):**
```
✅ Stage 3: Validation
   Checking message against constitutional rules...
   
   • Checking for hallucinations (invalid participant mentions)
   • Checking for flip-flopping (consistency with past stance)
   • Checking for repetition (echoing other agents)
   • Checking for self-contradiction
   • Validating against 5 valid participants
```

Then:
```
✅ Stage 3: Complete
   ✅ All checks passed
   
   • No hallucinations detected
   • Consistent with past stance
   • Not repeating others
   • Message approved
```

**Example (Issues Found):**
```
⚠️ Stage 3: Issues Found
   Constitutional violations detected
   
   • ⚠️ no_hallucination: Agent mentioned @Economist who doesn't exist
   • ⚠️ no_repetition: Message too similar to recent message by Tech Nerd
```

Then:
```
🔧 Stage 3: Auto-Corrected
   Message automatically fixed
   
   • Applied automatic corrections
   • Message ready to send
```

Or:
```
🔄 Stage 3: Regenerating
   Creating new message with stricter constraints...
   
   • Previous message violated rules
   • Regenerating with specific fixes
```

---

## User Experience

### Collapsed by Default
Thinking blocks appear **collapsed** so they don't clutter the chat:

```
💬 Message from Agent
🧠 Thinking (Stage 2: Generating Response) ▼ Expand thinking
💬 Next message
```

### Expand to See Details
Click "Expand thinking" to see what the agent was doing:

```
💬 Message from Agent
🧠 Thinking
   ✍️ Stage 2: Generating Response
      Crafting message based on reasoning...
      
      • Using stance: optimistic outlook
      • Incorporating debate rules
      • Checking for direct challenges
      • Ensuring authentic voice
   ▲ Collapse
💬 Next message
```

### Visual Design
- **Purple/Lavender theme** (similar to Claude's thinking blocks)
- **Compact and clean** - doesn't dominate the screen
- **Quick scan** - can see "Stage X" at a glance
- **Progressive disclosure** - collapse/expand as needed

---

## Technical Details

### Backend (Python)

**New Method:** `_emit_thinking_event()` in `turn_orchestrator.py`

Sends WebSocket events at each stage:
```python
self._emit_thinking_event(debate_id, agent_name, "reasoning", {
    "stage": "Stage 1: Reasoning",
    "status": "Evaluating stance...",
    "details": [
        "Reading 3 past messages",
        "Analyzing 5 recent turns",
        "Checking for interventions"
    ]
})
```

**Event Types:**
- `reasoning` - Stage 1 started
- `reasoning_complete` - Stage 1 finished
- `generating` - Stage 2 started
- `generating_complete` - Stage 2 finished
- `validating` - Stage 3 started
- `validation_issues` - Problems detected
- `auto_corrected` - Auto-fixed
- `regenerating` - Creating new message
- `validation_complete` - All checks passed

---

### Frontend (React/TypeScript)

**New Component:** `renderThinkingBlock()` in `EventFeed.tsx`

Renders collapsible thinking blocks with icons:
- 🤔 Reasoning
- ✍️ Generating
- ✅ Validating
- ⚠️ Issues
- 🔧 Auto-corrected
- 🔄 Regenerating

**WebSocket Event Type:** `agent_thinking`

Added to `WSEventType` in `wsClient.ts`

**CSS Styling:** `EventFeed.module.css`

Purple gradient theme, collapsible design, smooth transitions.

---

## Benefits

### For Users
1. **No more blind waiting** - see what's happening
2. **Understand agent quality** - see the thinking process
3. **Transparency** - know when issues are detected and fixed
4. **Educational** - learn how Constitutional AI works

### For Debugging
1. **See where time is spent** - which stage is slow?
2. **Identify validation issues** - what rules are being violated?
3. **Track reasoning quality** - are agents analyzing correctly?
4. **Monitor auto-corrections** - what's being fixed automatically?

### For Trust
1. **See the work** - agents aren't just guessing
2. **Quality checks visible** - validation is happening
3. **Error handling transparent** - see when things are corrected
4. **Process clarity** - understand the 3-stage pipeline

---

## Examples

### Happy Path (No Issues)
```
1. 🤔 Stage 1: Reasoning
   Evaluating stance...
   → Details: Reading messages, analyzing

2. 🤔 Stage 1: Complete
   Reasoning complete
   → Details: Stance, confidence, key points

3. ✍️ Stage 2: Generating
   Crafting message...
   → Details: Using stance, applying rules

4. ✍️ Stage 2: Complete
   Response generated
   → Details: Length, word count, citations

5. ✅ Stage 3: Validation
   Checking rules...
   → Details: Hallucination check, repetition check

6. ✅ Stage 3: Complete
   ✅ All checks passed
   → Details: No issues found

7. 💬 Agent Message
   [Actual message appears here]
```

---

### With Auto-Correction
```
1-5. [Same as above]

6. ⚠️ Stage 3: Issues Found
   Constitutional violations detected
   → Details: "⚠️ no_hallucination: Mentioned @Economist"

7. 🔧 Stage 3: Auto-Corrected
   Message automatically fixed
   → Details: Applied corrections, ready to send

8. 💬 Agent Message
   [Corrected message appears here]
```

---

### With Regeneration
```
1-5. [Same as above]

6. ⚠️ Stage 3: Issues Found
   Constitutional violations detected
   → Details: Multiple rule violations

7. 🔄 Stage 3: Regenerating
   Creating new message with stricter constraints...
   → Details: Previous violated rules, regenerating

8. ✅ Stage 3: Complete
   ✅ All checks passed
   → Details: New message approved

9. 💬 Agent Message
   [Regenerated message appears here]
```

---

## Configuration

**Enabled by Default:** No configuration needed

**To Disable Thinking Events (if needed):**
Comment out `_emit_thinking_event()` calls in `turn_orchestrator.py`

**Performance Impact:** Minimal
- Events are sent asynchronously
- Don't block agent turn execution
- If WebSocket fails, thinking events are skipped silently

---

## Future Enhancements

### Potential Additions:
1. **Time tracking** - show how long each stage took
2. **Confidence visualization** - show confidence as progress bar
3. **Stance history** - show how stance evolved over debate
4. **Token usage** - show tokens consumed per stage
5. **Model info** - show which model was used
6. **Retry count** - show if message was regenerated multiple times
7. **Collapse all thinking** - toggle to hide all thinking blocks
8. **Thinking summary** - aggregate view of all thinking stages

---

## Testing

### How to Test:
1. Create a new debate
2. Hit "Next Turn"
3. Watch for thinking blocks to appear in real-time
4. Click "Expand thinking" to see details
5. Verify all 3 stages appear
6. Check that blocks are collapsible

### What to Look For:
- ✅ Thinking blocks appear during agent turn
- ✅ Collapsed by default (compact view)
- ✅ Expandable to see details
- ✅ Stage 1, 2, 3 all show up
- ✅ Icons match the stage (🤔 ✍️ ✅)
- ✅ Purple/lavender styling
- ✅ Details are readable and useful
- ✅ Blocks don't break the layout

### Edge Cases:
- What if Constitutional AI is disabled? (Thinking won't show)
- What if WebSocket disconnects? (Events won't appear, but turn completes)
- What if validation fails multiple times? (See regeneration events)

---

## Summary

**Added:** Real-time agent thinking visibility

**Features:**
- 3-stage Constitutional AI pipeline visible
- Collapsible blocks (expanded on demand)
- Detailed progress at each stage
- Auto-correction and regeneration tracking
- Clean purple/lavender design
- Non-blocking, async delivery

**Result:** Users see what agents are doing, building trust and transparency in the AI debate process.

---

## Status
✅ Backend implemented  
✅ Frontend implemented  
✅ Styling complete  
✅ WebSocket events configured  
✅ Servers restarted  
✅ Ready to test  

Create a new debate and hit "Next Turn" to see thinking blocks in action!
