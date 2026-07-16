# YOLO Debate Mode - Technical Specification

## Overview
Fully autonomous debates that run without user intervention, with optional Telegram streaming.

## Architecture

### Phase 1: Autonomous Engine (PRIORITY)
**Goal**: Self-running debates

**Components**:
1. `autonomous_debate_service.py` - Orchestrates auto-turns
2. Policy config: `autonomous_mode: bool`, `auto_turn_delay_seconds: int`
3. Background worker: Auto-triggers turns every N seconds
4. Auto-conclusion: Triggers summary when done

**Flow**:
```
Start → Background Task → Loop:
  - Wait N seconds
  - Trigger next turn
  - Check if done (max_rounds/timebox)
  - If done: Generate summary, set status=completed
```

**API Endpoints**:
- `POST /api/debates/{id}/start-autonomous` - Start YOLO mode
- `POST /api/debates/{id}/pause-autonomous` - Pause
- `POST /api/debates/{id}/resume-autonomous` - Resume
- `GET /api/debates/{id}/status` - Get current status

**Database Changes**:
```sql
ALTER TABLE debates ADD COLUMN autonomous_mode BOOLEAN DEFAULT false;
ALTER TABLE debates ADD COLUMN autonomous_status TEXT; -- 'running', 'paused', 'completed'
ALTER TABLE debates ADD COLUMN auto_turn_delay_seconds INTEGER DEFAULT 10;
```

### Phase 2: UI (AFTER Phase 1 works)
**Components**:
1. `YoloDebateSetup.tsx` - Quick setup modal
2. Status indicator in room page
3. Auto-refresh when autonomous

**Features**:
- Toggle: "🤖 YOLO Mode"
- Auto-turn delay slider (5-60 seconds)
- Progress: "Turn 5/20 | ETA: 3 min"
- Pause/Resume buttons

### Phase 3: Telegram Integration (AFTER Phase 2 works)
**Setup**:
1. Get bot token from @BotFather
2. Add to `.env`: `TELEGRAM_BOT_TOKEN=...`
3. Install: `pip install python-telegram-bot`

**Components**:
1. `telegram_bot.py` - Bot handlers (~200 lines)
2. `telegram_streaming.py` - Event formatter (~150 lines)
3. Hook into `websocket_service.py` broadcast

**Commands**:
- `/start` - Welcome message
- `/watch <debate_id>` - Subscribe to debate
- `/pause` - Pause debate
- `/resume` - Resume debate
- `/summary` - Get summary
- `/stop` - Stop watching

**Message Format**:
```
🎤 Agent Name
Message preview (200 chars)...

🤝 Coalition: A, B, C
Strategy text

💬 A → B: Private message

✅ Debate completed!
```

**Integration Point**:
```python
# websocket_service.py
async def broadcast_to_debate(debate_id, event):
    # Existing: WebSocket broadcast
    for ws in connections: await ws.send_json(event)
    
    # NEW: Telegram broadcast (if enabled)
    if telegram_bridge:
        await telegram_bridge.stream_event(debate_id, event)
```

## Cost Optimization
- All models already optimized (gemini-flash for chat, gpt-4o-mini for debate)
- YOLO mode doesn't add LLM costs (reuses existing turn logic)
- Telegram: Free (Telegram API is free)
- Background tasks: Minimal CPU (sleeps between turns)

## Implementation Order
1. ✅ Phase 1 (Core) - 2-3 hours
2. Phase 2 (UI) - 1 hour  
3. Phase 3 (Telegram) - 2 hours

## Settings Recommendations
- `auto_turn_delay_seconds: 10` (balance speed/quality)
- Keep research enabled (quality matters)
- Keep agent autonomy enabled (makes it interesting)
- Default to `max_rounds` over timebox (predictable)
