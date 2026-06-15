# M1 Runbook: Debate-in-a-Box API

## Overview

M1 provides a single API endpoint (`POST /debates/run`) that executes a complete 5-turn round-robin debate with exactly 3 agents and returns structured outputs.

**Scope:**
- 5-turn deterministic round-robin orchestration
- OpenRouter BYOK (Bring Your Own Key) per request
- Event ledger persistence to database
- Returns: summary + minutes + action items + event history

**Out of scope (future milestones):**
- Realtime SSE/WebSocket streaming
- Pause/resume/intervention controls
- Voice mode
- Full memory fabric retrieval

---

## Prerequisites

1. **Database running:**
   ```bash
   cd /path/to/arinar-v2
   make db-up
   make db-migrate
   make db-seed
   ```

2. **Python dependencies installed:**
   ```bash
   cd apps/api
   pip install -r requirements.txt
   ```

3. **OpenRouter API key:**
   - Get your key from https://openrouter.ai/keys
   - M1 uses BYOK (provided per request, not stored)

---

## Local Startup

### Start API Server

```bash
cd apps/api
python -m src.main
```

The API will start on `http://localhost:8000`.

### Verify Health

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "arinar-api",
  "version": "1.0.0"
}
```

---

## Example Usage

### Example Request

```bash
curl -X POST http://localhost:8000/debates/run \
  -H "Content-Type: application/json" \
  -d '{
    "problem_statement": "Should we prioritize mobile-first or desktop-first design for our new product?",
    "agents": [
      {
        "name": "Product Manager",
        "role": "Strategic product leader focused on user needs",
        "model_id": "anthropic/claude-3.5-sonnet"
      },
      {
        "name": "Senior Engineer",
        "role": "Technical lead with focus on feasibility and scalability",
        "model_id": "openai/gpt-4-turbo"
      },
      {
        "name": "UX Designer",
        "role": "User experience expert focused on accessibility",
        "model_id": "anthropic/claude-3.5-sonnet"
      }
    ],
    "openrouter_api_key": "YOUR_OPENROUTER_KEY_HERE",
    "debate_title": "Design Priority Discussion"
  }'
```

### Example Response

```json
{
  "debate_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "outputs": {
    "summary": "The team discussed mobile-first vs desktop-first design priorities. Product Manager emphasized market trends, Senior Engineer highlighted technical constraints, and UX Designer focused on user accessibility.",
    "minutes_of_meeting": "Product Manager opened by noting that 65% of users access web products from mobile devices. Senior Engineer countered that complex features are easier to build desktop-first, then adapt. UX Designer emphasized that mobile-first ensures better accessibility from the start. Product Manager suggested a phased approach. Senior Engineer agreed, proposing core features desktop-first, secondary features mobile-first. UX Designer proposed responsive design patterns to serve both. Team converged on a hybrid approach prioritizing responsive design with mobile-optimized core flows.",
    "action_items": [
      "Conduct user analytics review for mobile vs desktop usage",
      "Create responsive design system with mobile-first core flows",
      "Prototype key features on both platforms for comparison",
      "Document phased rollout plan"
    ]
  },
  "event_history": [
    {
      "event_id": "e1...",
      "turn": 1,
      "agent": "Product Manager",
      "message": "Based on market research, 65% of users..."
    },
    {
      "event_id": "e2...",
      "turn": 2,
      "agent": "Senior Engineer",
      "message": "From a technical perspective, desktop-first..."
    },
    {
      "event_id": "e3...",
      "turn": 3,
      "agent": "UX Designer",
      "message": "Mobile-first design ensures accessibility..."
    },
    {
      "event_id": "e4...",
      "turn": 4,
      "agent": "Product Manager",
      "message": "I propose a phased approach..."
    },
    {
      "event_id": "e5...",
      "turn": 5,
      "agent": "Senior Engineer",
      "message": "Agreed, we can prioritize core features..."
    }
  ]
}
```

---

## Validation Commands

### 1. Run API Tests

```bash
cd apps/api
pip install -r requirements-dev.txt
pytest tests/test_debate_run.py -v
```

Expected: All tests pass (8 test cases)

### 2. Contract Validation

```bash
cd packages/contracts
npm run validate:all
npm run generate:types
```

Expected: OpenAPI spec validates, types generate without errors

### 3. Full Quality Gates

```bash
cd /path/to/arinar-v2
make verify
```

Expected: All gates pass (lint, typecheck, tests, quality checks)

---

## Troubleshooting

### Issue: 401 Unauthorized (Invalid OpenRouter Key)

**Symptom:**
```json
{
  "detail": "OpenRouter authentication failed: Invalid OpenRouter API key"
}
```

**Solution:**
- Verify your OpenRouter API key is correct
- Check key has required permissions
- Ensure key has available credits

### Issue: 500 Internal Server Error (OpenRouter Timeout)

**Symptom:**
```json
{
  "detail": "OpenRouter API error: OpenRouter request timed out after 120s"
}
```

**Solution:**
- OpenRouter is experiencing high load; retry after a few minutes
- Check OpenRouter status page: https://status.openrouter.ai
- Consider using a different model if one is consistently slow

### Issue: Database Connection Error

**Symptom:**
```
psycopg2.OperationalError: could not connect to server
```

**Solution:**
```bash
# Check if database is running
make db-up

# Verify connection
psql postgresql://postgres:postgres@localhost:5432/arinar_local -c "SELECT 1"
```

### Issue: Wrong Number of Agents

**Symptom:**
```json
{
  "detail": "Exactly 3 agents required for M1"
}
```

**Solution:**
M1 scope requires exactly 3 agents. Provide 3 agents in the `agents` array.

---

## Database Inspection

### View Created Debates

```bash
psql postgresql://postgres:postgres@localhost:5432/arinar_local -c "
  SELECT debate_id, title, state, created_at 
  FROM debates 
  ORDER BY created_at DESC 
  LIMIT 10;
"
```

### View Events for a Debate

```bash
psql postgresql://postgres:postgres@localhost:5432/arinar_local -c "
  SELECT event_id, event_type, sequence_number, content->>'agent_name' as agent, content->>'text' as message
  FROM events 
  WHERE debate_id = 'YOUR_DEBATE_ID_HERE'
  ORDER BY sequence_number;
"
```

---

## Supported Models (OpenRouter)

M1 works with any OpenRouter model. Common choices:

- `anthropic/claude-3.5-sonnet` (recommended for quality)
- `openai/gpt-4-turbo` (good balance)
- `openai/gpt-3.5-turbo` (faster, lower cost)
- `anthropic/claude-3-opus` (highest quality)

**Note:** Different models have different costs and latency. See https://openrouter.ai/docs for pricing.

---

## Performance Characteristics

**Typical Execution Time (5 turns):**
- Fast models (gpt-3.5-turbo): 15-30 seconds
- Medium models (gpt-4-turbo): 30-60 seconds
- Slow models (claude-3-opus): 60-120 seconds

**Database Operations:**
- 1 debate insert
- 3 participant inserts
- 1 system event insert
- 5 agent message events inserts
- 1 debate update (mark completed)
- Total: 11 DB operations per run

---

## M1 Gate Checklist

Reference: `/2026-goals-codex/16-milestone-gates-and-evidence.md`

- ✅ `POST /debates/run` accepts problem statement + 3 agents + OpenRouter key
- ✅ Executes exactly 5 turns in deterministic round-robin order
- ✅ Returns summary + minutes + action items + full event history
- ✅ Persists debate + events to database ledger
- ✅ Invalid/missing OpenRouter key rejected with 401 error

---

## Next Steps (M2 Preview)

M2 will add:
- Realtime SSE/WebSocket streaming
- Pause/resume controls
- User intervention and agent tagging
- Manual meeting end

M1 provides the foundational debate loop that M2 will extend with realtime controls.
