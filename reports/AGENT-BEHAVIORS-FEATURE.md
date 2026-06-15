# Agent Behaviors Feature - Making It "Spicy" 🌶️

## Overview
Transformed Boardroom AI from a basic turn-based system into a true **Agentic AI Platform** with autonomous behaviors, strategic planning, and behind-the-scenes negotiations.

---

## What Was Added

### 1. **Web Research During Preflight** 🌐
- **Technology**: DuckDuckGo Search (free, no API key)
- **When**: Automatically during agent preparation
- **Token-Efficient**: Top 3 results only, 200-char snippets
- **Visible**: Research results appear in prep pack preview
- **Status Update**: "Researching topic online" shows in UI

**Example Output:**
```
**Web Research Results:**
1. OpenAI releases GPT-5 with superior coding abilities
   Recent benchmarks show GPT-5 outperforms Claude...
   Source: techcrunch.com/2026/01/...
```

---

### 2. **Coalition Formation** 🤝
- **What**: Agents autonomously decide to form alliances
- **When**: 12.5% chance after each turn (25% trigger × 50% coalition check)
- **How**: Agent analyzes other participants' positions and decides who to ally with
- **Visible**: New "Agent Behaviors" panel shows coalitions in real-time
- **Token Cost**: ~80 tokens per coalition check (uses gpt-4o-mini)

**Example:**
```
🤝 Coalition Formed
Members: Expert Analyst, Rational Analyst
Strategy: "Align on data-driven approach"
```

---

### 3. **Private Messaging** 💬
- **What**: Agents send private messages to each other (other participants don't see)
- **When**: 7.5% chance after each turn (25% trigger × 30% message check)
- **How**: Agent generates strategic private message to negotiate or propose alliance
- **Visible**: Shows in "Private Msgs" tab - OTHER AGENTS CAN'T SEE THIS
- **Token Cost**: ~50 tokens per message (max 30 words)

**Example:**
```
Consumer Advisor → Expert Analyst
"Let's align on quality metrics. Your data supports my consumer focus. Coalition?"
```

---

### 4. **Strategic Round Awareness** 🎯
Agents now receive complete debate structure upfront:

**For 2-Round Debates:**
- Round 1: Explore, ask questions, be open-minded
- Round 2: Synthesize, decide with clear reasoning

**For 3+ Round Debates:**
- Round 1: Explore and listen
- Round 2: Engage and develop position  
- Final Round: Converge and decide

**Token Savings**: Agents strategize properly instead of jumping to conclusions

---

### 5. **Explicit Final Turn Behavior** 🔴
When it's an agent's absolute last turn, they receive:

```
🔴 YOUR FINAL TURN - NO MORE CHANCES TO SPEAK

MANDATORY FORMAT:
"Given this is my final turn (Round 3/3), I'll conclude by stating my decision: 
[CLEAR YES/NO or SPECIFIC CHOICE]"

✅ GOOD: "My final decision: Coffee is superior because..."
❌ BAD: "I conclude by saying both have merit..." (TOO VAGUE)
```

---

## New UI Components

### **Agent Behaviors Panel** (replaced Agenda Panel)
Three tabs showing real-time autonomous activity:

**🤝 Coalitions Tab:**
- Shows which agents have formed alliances
- Displays coalition strategy
- Updates in real-time via WebSocket

**💬 Private Messages Tab:**
- Shows private negotiations between agents
- Hidden from other participants
- Timestamps and message content

**📋 Sub-tasks Tab:**
- Shows agents breaking down goals into steps
- Status: Planning → Executing → Complete
- (Currently prepared, will activate when agents use it)

---

## Token Efficiency Strategy

| Feature | Trigger Rate | Token Cost | Model |
|---------|-------------|------------|-------|
| Web Research | Once per agent (preflight) | ~500 tokens | N/A (DuckDuckGo) |
| Coalition Check | 12.5% per turn | ~80 tokens | gpt-4o-mini |
| Private Message | 7.5% per turn | ~50 tokens | gpt-4o-mini |
| Sub-tasks | On-demand | ~70 tokens | gpt-4o-mini |

**Total Added Cost per Turn**: ~10-15 tokens average (mostly free turns)

---

## Architecture Changes

### Backend
- **New**: `agent_autonomy.py` - Service for autonomous behaviors
- **Modified**: `turn_orchestrator.py` - Triggers autonomy after turns
- **Modified**: `tasks/preflight.py` - Added web search integration
- **WebSocket**: New event types: `coalition_formed`, `private_message`

### Frontend
- **New**: `AgentBehaviorsPanel.tsx` - Real-time behaviors display
- **Removed**: Agenda panel from live room (moved to pre-setup)
- **Modified**: `room/page.tsx` - Uses new behaviors panel

---

## How to Test

1. **Create a debate** with 2-3 rounds
2. **Watch preflight**: You'll see "Researching topic online"
3. **View prep packs**: Check web research results
4. **During debate**: Watch the "Agent Behaviors" panel (right side)
   - See coalitions form in real-time
   - See private messages between agents
5. **Final turns**: Agents will explicitly declare decisions

---

## What Makes This "Agentic" Now

✅ **Autonomy**: Agents decide when to form coalitions (not user-triggered)  
✅ **Proactivity**: Agents initiate private messages on their own  
✅ **Tool Use**: Agents search the web during preparation  
✅ **Strategic Planning**: Agents see full debate structure and plan accordingly  
✅ **Negotiation**: Private messages allow behind-the-scenes strategy  
✅ **Goal-Directed**: All behaviors aim toward desired outcomes  

---

## Cost Impact

**Before**: ~2,000 tokens per turn (agent message only)
**After**: ~2,020 tokens per turn average (+1% increase)

The autonomous behaviors are **extremely token-efficient** due to:
- Low trigger rates (12.5% and 7.5%)
- Cheap model (gpt-4o-mini at ~$0.0001/1K tokens)
- Short outputs (30-50 words max)
- Free web search (DuckDuckGo)

---

## Status: ✅ COMPLETE

All features implemented and tested. Backend running successfully.
