# Conflict & Tension Fix - Opposing Camps Implementation

## Problem
Debates were too polite and lacked real conflict:
- Everyone agreed: "AI augments, doesn't replace"
- Too many "I appreciate your insights, however..." phrases
- Agents sounded like LinkedIn influencers, not real debaters
- No opposing camps - everyone was on the same side

## Solution: Dynamic Stance Assignment

### What Changed

#### 1. **Automatic Opposing Camp Assignment** 
**File:** `apps/api/src/turn_orchestrator.py` (lines 851-1014)

**New Method:** `_assign_debate_stance()`

**How It Works:**
- Splits participants into **two opposing camps** using a simple algorithm:
  - **Even indices (0, 2, 4...)** = Camp A (Pro/Optimistic/For)
  - **Odd indices (1, 3, 5...)** = Camp B (Con/Pessimistic/Against)

**Example for "When will the job market get better":**
- **Camp A (Optimistic):** Visionary, Market Indicator Analyst
  - Stance: "Things WILL improve soon (6-12 months)"
  - Arguments: Early positive signals, historical patterns
  
- **Camp B (Pessimistic):** Tech Nerd, Trend Forecaster, Strong Critic
  - Stance: "Things WON'T improve for 2+ years"
  - Arguments: Structural problems, current data, systemic barriers

#### 2. **Topic-Based Stance Templates**

The system automatically detects debate type and assigns appropriate stances:

| Debate Type | Trigger Words | Camp A | Camp B |
|-------------|---------------|--------|--------|
| **Timeline/Prediction** | "when", "will", "future", "improve" | Optimistic (soon) | Pessimistic (long time) |
| **Policy** | "should", "must", "ban", "allow" | Pro (implement) | Against (don't implement) |
| **Tech Impact** | "ai", "technology", "automation" | Tech Optimist (creates jobs) | Tech Pessimist (destroys jobs) |
| **Comparative** | "what", "how", "which", "best" | Traditional approach | Innovative approach |
| **Generic** | Other | Positive stance | Critical stance |

#### 3. **Aggressive Conflict Instructions**

Each agent now receives explicit instructions:

```
🎯 YOUR DEBATE STANCE: TECH PESSIMIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

YOU BELIEVE: AI/technology will DESTROY more than it creates

YOUR JOB:
✅ DEFEND your position aggressively - don't back down
✅ ATTACK opposing views with specific counter-arguments
✅ CITE displacement evidence, inequality, and automation risks
✅ DON'T be polite if someone challenges you - push back hard
✅ CALL OUT weaknesses in the other camp's arguments

⚔️ YOUR OPPONENTS (they take the opposite stance):
@"Visionary", @"Market Indicator Analyst"

→ CHALLENGE them directly when they speak
→ DON'T let their arguments go unchallenged
→ DEMAND evidence when they make claims

🤝 YOUR ALLIES (they share your stance):
@"Trend Forecaster", @"Strong Critic"

→ BUILD ON their arguments
→ COORDINATE attacks on the opposing camp
→ DEFEND them when opponents attack

CONFLICT RULES:
❌ DON'T say 'both sides have merit' - pick YOUR side and defend it
❌ DON'T be overly polite - this is a real debate, not a seminar
❌ DON'T concede points easily - make opponents work for it
✅ DO interrupt if someone on the other side is dominating
✅ DO use phrases like 'That's wrong because...', 'The data doesn't support that'
✅ DO show emotion - frustration, conviction, urgency

Remember: You have a CLEAR POSITION. Defend it like your job depends on it.
```

#### 4. **Banned Polite Phrases**

**Updated:** Lines 651-672

Added explicit bans on:
- "I appreciate your insights, however..."
- "You raise valid points, but..."
- "I see where you're coming from..."
- "That's an interesting perspective..."
- "Building on what you said..."

**Replaced with:**
- "That's wrong because..."
- "@PersonName, your analysis ignores X."
- "The real issue is Y, not X."
- "Here's what everyone is missing..."

#### 5. **Enhanced "BE AGENTIC" Rules**

**Updated:** Lines 649-659

Changed from:
```
- React to proposals: "I support that vote idea" or "That won't work because..."
- Challenge host: "@Host, the topic is too vague"
```

To:
```
- Challenge opponents: "@OpponentName, you keep saying X but the data shows Y. Explain that."
- Interrupt if needed: "Wait - before we move on, @PersonName is completely wrong about X."
- Call out weak arguments: "That's circular reasoning. You're assuming X to prove X."
- Demand evidence: "@PersonName, show me the data on X or stop claiming it."
- Form coalitions: "@Ally, you and I both see Y - let's push this together."
- Attack strategy: "This approach won't work. Here's why: [specific reasons]"
- Defend allies: "@Opponent, you're attacking @Ally but missing their actual point."
- Show frustration: "This is going in circles. Here's what we actually need to decide..."
```

---

## Expected Impact

### Before (Old Debate):
```
Visionary: "I appreciate your points about AI. However, I believe we should 
also consider the opportunities..."

Tech Nerd: "You raise valid points about opportunities. Building on what you 
said, I think we need to balance..."

Market Analyst: "I see where you're both coming from. Both approaches have merit..."
```

### After (New Debate):
```
Visionary: "Wrong. The job market will recover in 6 months, not 2 years. 
Here's why @TechNerd is missing the signals..."

Tech Nerd: "@Visionary, your timeline is way too optimistic. You're ignoring 
the structural unemployment data from Q3. This isn't bouncing back fast."

Market Analyst: "@Visionary, I'm with Tech Nerd on this. Your 6-month prediction 
assumes companies will rehire, but they're automating instead. Show me the data."
```

---

## How to Test

### 1. Create a New Debate
Use a topic that naturally has two sides:
- "When will the job market get better?" (timeline)
- "Should we ban AI in hiring?" (policy)
- "Is remote work better than office work?" (comparative)

### 2. Watch for Opposing Camps
Check the server logs for stance assignments:
```
🎯 YOUR DEBATE STANCE: TECH PESSIMIST
⚔️ YOUR OPPONENTS: @"Visionary", @"Market Indicator Analyst"
🤝 YOUR ALLIES: @"Trend Forecaster", @"Strong Critic"
```

### 3. Look for Conflict Markers
- Direct challenges: "@PersonName, that's wrong because..."
- No polite phrases: Should NOT see "I appreciate..." or "You raise valid points..."
- Emotion: "This is frustrating", "You're missing the obvious", "That's clearly wrong"
- Defending allies: "@Opponent, stop attacking @Ally on X when you're ignoring Y"

### 4. Check Camp Behavior
- **Allies should coordinate:** "@Ally and I both see this problem..."
- **Opponents should clash:** "@Opponent, you keep claiming X but the data says Y"

---

## Configuration

All features are enabled by default. No environment variables needed.

The stance assignment happens automatically based on:
1. Participant order (index % 2)
2. Debate topic keywords
3. Agent role/description

---

## Limitations & Future Improvements

### Current Limitations:
1. **Simple Camp Assignment:** Uses participant index (even/odd) - could be smarter
2. **Binary Camps:** Only 2 camps - complex debates might need 3+ perspectives
3. **Static Stances:** Agents don't change camps mid-debate (by design for now)

### Future Enhancements:
1. **Semantic Camp Assignment:** Use LLM to analyze agent role + topic → assign stance
2. **Multi-Camp Support:** Allow 3-4 different positions on complex topics
3. **Dynamic Coalition Formation:** Let agents switch sides if persuaded
4. **Stance Tracking:** Store agent's stance in database for memory across debates
5. **Power Dynamics:** Some agents could be "swing votes" that both camps compete for

---

## Summary

**What This Fixes:**
✅ Agents now have **opposing positions** they must defend  
✅ Agents know who their **opponents** and **allies** are  
✅ Agents are **explicitly instructed to be confrontational**  
✅ **Polite agreement phrases are banned**  
✅ Agents must **challenge, attack, and defend** aggressively  

**Result:**
Debates should feel like **actual debates** with tension, conflict, and opposing camps fighting for their position - not a polite corporate roundtable where everyone agrees.

---

## Testing Status
- ✅ Code changes complete
- ✅ Syntax validated
- ✅ Server running
- ⏳ Ready for user testing with new debate
