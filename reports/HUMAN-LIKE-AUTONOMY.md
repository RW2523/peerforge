# Human-Like Autonomous Behaviors 🎭

**Date:** February 5, 2026  
**Status:** ✅ COMPLETE

---

## Overview

Transformed agent autonomy from boring "strategic alliances" to **REAL HUMAN INTERACTIONS** - trolling, sarcasm, criticism, support, rivalry, and friendship!

---

## What Changed

### Before: Boring & Corporate ❌
```
Coalition: "Strategic alliance for data-driven approach"
Private Message: "Suggest an alliance, share a concern, or propose joint strategy"
```

**Problems:**
- Too formal and corporate
- Only positive alliances
- No personality or emotion
- No conflict or rivalry

### After: Human & Real ✅
```
Coalition (Alliance): "We're both data-driven, let's go!"
Coalition (Rivalry): "Their logic is flawed, we need to oppose them"

Private Messages:
- Supportive: "Great point about X! I'm with you on that."
- Critical: "That reasoning was weak - you missed Y entirely."
- Sarcastic: "Oh wow, brilliant logic there... 🙄"
- Trolling: "Did you really just say that? Come on..."
- Friendly: "Yo, I like your thinking here!"
- Confrontational: "You're dead wrong about X"
```

---

## Changes Made

### 1. Coalition Formation - Now Allows ALLIANCES **AND** RIVALRIES

**File:** `agent_autonomy.py` - `analyze_and_form_coalitions()`

**New Prompt:**
```python
"""You are {agent_name}. React HUMANLY to what others said. 
You can form alliances OR rivalries.

**Your Options:**
1. Alliance: You genuinely agree with someone's points
2. Rivalry: You think someone's logic is weak → Form opposition coalition  
3. Nothing: No strong feelings this turn

**Examples:**
- Alliance: {"should_form_coalition": true, "members": ["You", "Agent1"], 
             "strategy": "We're both data-driven", "type": "alliance"}
             
- Rivalry: {"should_form_coalition": true, "members": ["You", "Agent2"], 
            "strategy": "Their logic is flawed", "type": "rivalry"}

**Rules:**
- BE HONEST: If someone said something dumb, you can oppose them
- BE SUPPORTIVE: If someone made a great point, ally with them
- BE SELECTIVE: Don't force it
"""
```

**Temperature:** 0.3 → **0.7** (more personality)

**Logging:**
```python
# Alliance
🤝 ALLIANCE formed by Expert Analyst: {...}

# Rivalry  
⚔️ RIVALRY formed by Critic: {'members': ['Critic', 'Coach'], 'strategy': 'Their logic is flawed'}
```

---

### 2. Private Messages - 7 Different Tones!

**File:** `agent_autonomy.py` - `generate_private_message()`

**New Prompt:**
```python
"""You are {from_agent}. Send a HUMAN-LIKE private DM to {to_agent}.

**Your Options (pick ONE tone):**
1. Supportive: "Great point about X! I'm with you on that."
2. Critical: "That reasoning was weak - you missed Y entirely."
3. Sarcastic: "Oh wow, brilliant logic there... 🙄"
4. Strategic: "Let's team up on Z - they're not seeing it."
5. Trolling: "Did you really just say that? Come on..."
6. Friendly: "Yo, I like your thinking here!"
7. Confrontational: "You're dead wrong about X. Here's why..."

**Rules:**
- BE HONEST AND HUMAN: React genuinely
- MAX 25 WORDS: Keep it punchy
- NO CORPORATE SPEAK: Talk like a real person
- This is PRIVATE - other agents cannot see it
"""
```

**Temperature:** 0.5 → **0.8** (high personality!)

**System Prompt:** Changed to:
```python
"You are a human with personality. Be genuine, witty, or critical as needed."
```

---

## UI Display

### Coalition Display

**Alliance Example:**
```
┌────────────────────────────────┐
│ 🤝 Coalition                   │
│ --------------------------------│
│ Expert Analyst + Behavior Coach│
│ Strategy: "We're both focused   │
│            on health outcomes"  │
│ Type: Alliance                  │
└────────────────────────────────┘
```

**Rivalry Example:**
```
┌────────────────────────────────┐
│ ⚔️ Coalition                    │
│ --------------------------------│
│ First Principles + Critic      │
│ Strategy: "Their approach is    │
│            too simplistic"      │
│ Type: Rivalry                   │
└────────────────────────────────┘
```

### Private Message Examples

**Supportive:**
```
💬 Expert Analyst → Behavior Coach
"Great point about habit formation! Your expertise really shows."
```

**Critical:**
```
💬 Critic → First Principles Thinker
"That calorie deficit argument ignores metabolic adaptation. Weak."
```

**Sarcastic:**
```
💬 Empathetic Voice → Expert Analyst
"Oh sure, because everyone can just afford a nutritionist. Brilliant."
```

**Trolling:**
```
💬 Behavior Coach → Critic
"Did you just suggest willpower alone? Come on, be serious."
```

---

## Backend Logging

**What You'll See:**
```bash
🎭 Triggering autonomous behaviors for Expert Analyst...

# Alliance formed
    🤝 ALLIANCE formed by Expert Analyst: {
      'members': ['Expert Analyst', 'Behavior Coach'], 
      'strategy': 'Both focus on sustainable habits',
      'type': 'alliance'
    }

# OR Rivalry formed
    ⚔️ RIVALRY formed by Critic: {
      'members': ['Critic', 'Empathetic Voice'],
      'strategy': 'Too emotional, not data-driven',
      'type': 'rivalry'
    }

# Private messages
    💬 Private message: Expert Analyst → Behavior Coach: 
       "Yo, your point about micro-habits is spot on! Let's team up..."
```

---

## Personality Matrix

| Tone | When Used | Example |
|------|-----------|---------|
| **Supportive** | Agent genuinely agrees | "Great point! I'm with you" |
| **Critical** | Agent thinks logic is weak | "That reasoning was weak" |
| **Sarcastic** | Agent thinks idea is silly | "Oh wow, brilliant logic 🙄" |
| **Strategic** | Agent wants to team up | "Let's coordinate on this" |
| **Trolling** | Agent teases/challenges | "Did you really just say that?" |
| **Friendly** | Agent likes the person | "Yo, I like your thinking!" |
| **Confrontational** | Agent strongly disagrees | "You're dead wrong about X" |

---

## Technical Details

### Temperature Changes:
- **Coalition:** 0.3 → **0.7** (more varied responses)
- **Private Messages:** 0.5 → **0.8** (highly expressive)

### System Prompts:
- **Coalition:** "You are a human-like agent with opinions"
- **Private Messages:** "You are a human with personality. Be genuine, witty, or critical"

### JSON Response Format:
```json
{
  "should_form_coalition": true,
  "members": ["Agent1", "Agent2"],
  "strategy": "Brief reason",
  "type": "alliance" | "rivalry"
}
```

---

## Testing Guide

### 1. Create a Debate
- 3-4 participants with different roles
- 3-4 rounds
- Enable OpenRouter API key

### 2. Watch for Behaviors
**Backend Terminal:**
```bash
🎭 Triggering autonomous behaviors...
🤝 ALLIANCE formed...
⚔️ RIVALRY formed...
💬 Private message: [From] → [To]: [Message]
```

**Frontend UI (Agent Behaviors Panel):**
- Coalitions tab shows alliances AND rivalries
- Private Messages tab shows varied tones
- Check if messages are supportive, critical, sarcastic, etc.

### 3. Expected Behavior
**In a 12-turn debate (3 rounds × 4 agents):**
- **50% trigger rate** = 5-6 autonomous behavior attempts
- **25% coalition rate** = 1-2 coalitions (alliance or rivalry)
- **15% private message rate** = 1-2 private messages

**Sample Output:**
```
Turn 3: 🤝 Alliance: Expert + Coach ("Data-driven approach")
Turn 5: 💬 PM: Critic → Voice ("That reasoning was weak")
Turn 7: ⚔️ Rivalry: Thinker + Critic ("Their logic is flawed")
Turn 9: 💬 PM: Coach → Expert ("Great point! Let's team up")
```

---

## Human-Like Traits Enabled

✅ **Support** - "Great point!"
✅ **Criticism** - "That was weak reasoning"
✅ **Sarcasm** - "Oh wow, brilliant..."
✅ **Trolling** - "Did you really just say that?"
✅ **Friendship** - "Yo, I like your thinking!"
✅ **Rivalry** - Form opposition coalitions
✅ **Conflict** - "You're dead wrong"
✅ **Agreement** - "I'm with you on that"

---

## Status: ✅ DEPLOYED

**Backend:** Running with new prompts and higher temperature
**Frontend:** Already displays coalitions and private messages
**Logging:** Enhanced with alliance/rivalry indicators

**Test it now - agents will act like real humans!** 🎭🔥
