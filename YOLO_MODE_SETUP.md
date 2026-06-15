# 🚀 YOLO Mode Setup Guide

## What is YOLO Mode?

YOLO (You Only Launch Once) Mode is a fully autonomous debate feature that allows debates to run automatically without manual intervention. Perfect for simulations you can start and check back on later.

## Features

✅ **Modern UI Toggle** - Sleek toggle in setup with auto-turn delay slider  
✅ **Card-based Meeting Limits** - Beautiful redesigned duration selector  
✅ **Autonomous Execution** - Backend service runs debates automatically  
✅ **Pause/Resume Controls** - Control panel in debate room  
✅ **Status Indicators** - Visual badge shows when YOLO is active  
✅ **Cost-Optimized** - Uses efficient models for autonomous operations

## Setup Instructions

### 1. Database Migration

Apply the database migration to add YOLO mode columns:

```bash
cd arinar-v2/apps/api
psql $DATABASE_URL -f migrations/007_autonomous_debates.sql
```

Or run via Python migration tool (if you have one set up).

### 2. Backend Services

The following services are already implemented in Phase 1:
- `AutonomousDebateService` - Core autonomous execution loop
- `autonomous.py` routes - API endpoints for control
- Integrated with `TurnOrchestrator` and `SummaryService`

No additional backend setup needed!

### 3. Frontend Integration

All frontend components are wired up:
- ✅ Setup page toggle
- ✅ Room page status badge
- ✅ Pause/Resume controls
- ✅ Review step summary

## How to Use

### Creating a YOLO Debate

1. **Start Setup** - Navigate to `/setup`
2. **Enable YOLO** - Toggle "🚀 YOLO Mode" in Basic Info
3. **Adjust Delay** - Set auto-turn delay (5-60 seconds)
4. **Choose Duration** - Select Rounds or Time-based
5. **Add Agents** - Configure participants as usual
6. **Launch** - Start the debate and walk away!

### Monitoring

- **In UI**: Visit `/room?debate_id=<id>` to see live updates
- **Status Badge**: "🚀 YOLO" badge shows autonomous mode is active
- **Agent Behaviors**: Floating panel shows autonomous actions

### Controls

- **⏸️ Pause YOLO** - Temporarily stop autonomous turns
- **▶️ Resume YOLO** - Continue autonomous execution
- **End Meeting** - Stops debate and generates summary

## API Endpoints

```
POST   /api/debates/{debate_id}/start-autonomous
POST   /api/debates/{debate_id}/pause-autonomous
POST   /api/debates/{debate_id}/resume-autonomous
GET    /api/debates/{debate_id}/autonomous-status
```

## Cost Optimization

YOLO mode uses cost-effective models:
- Agent chat/questions: `google/gemini-flash-1.5`
- Coalition formation: `google/gemini-flash-1.5`
- Research/prep: `openai/gpt-4o-mini`
- Summary: `openai/gpt-4o-mini`

## What's Next (Phase 3)?

🔮 Telegram Integration:
- Stream debates to Telegram
- Control from mobile
- Get notifications
- Phase-based progress updates

## Troubleshooting

### YOLO not starting?
- Check migration was applied: `\d debates` in psql should show `autonomous_mode` column
- Verify API routes are registered in `main.py`

### Controls not showing?
- Ensure debate was created with `yoloMode: true`
- Check browser console for errors

### Autonomous loop not running?
- Check backend logs for errors
- Verify OpenRouter API key is set
- Ensure debate is in "running" state

## Architecture

```
┌─────────────────┐
│  Setup UI       │  User toggles YOLO mode
│  BasicInfoStep  │  Sets autoTurnDelay
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ useDebateSetup  │  Passes yoloMode to API
│    Actions      │  Calls start-autonomous
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Autonomous      │  Background asyncio loop
│ DebateService   │  Auto-triggers turns
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Turn            │  Orchestrates each turn
│ Orchestrator    │  Runs agent autonomy
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ WebSocket       │  Streams events to UI
│ /debates/stream │  Real-time updates
└─────────────────┘
```

## Files Modified

### Frontend
- `apps/web/src/components/setup/BasicInfoStep.tsx` - YOLO toggle + modern cards
- `apps/web/src/components/setup/SetupSteps.module.css` - Modern styling
- `apps/web/src/app/setup/page.tsx` - YOLO state management
- `apps/web/src/hooks/useDebateSetupActions.ts` - Launch logic
- `apps/web/src/lib/api.ts` - Autonomous API functions
- `apps/web/src/components/room/DebateControls.tsx` - Pause/Resume buttons
- `apps/web/src/app/room/page.tsx` - YOLO status tracking
- `apps/web/src/app/room/room.module.css` - YOLO badge styling
- `apps/web/src/components/setup/ReviewStep.tsx` - YOLO summary

### Backend (Phase 1)
- `apps/api/src/autonomous_debate_service.py` - Core service
- `apps/api/src/routes/autonomous.py` - API routes
- `apps/api/src/main.py` - Router registration
- `apps/api/migrations/007_autonomous_debates.sql` - DB schema

---

**Made with 🧡 for autonomous debates**
