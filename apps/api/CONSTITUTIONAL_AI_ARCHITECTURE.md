# Constitutional AI Architecture

## Problem Solved

Agents were flip-flopping opinions based on moderator input without maintaining intellectual consistency. Example: Agents initially said "DMK will win", then user asks "what about Vijay?" and ALL agents immediately switch to "TVK will win" without justifying why.

## Solution: Anthropic-Style 3-Stage Pipeline

Inspired by Anthropic's Constitutional AI, we separate reasoning from response generation and validate against hard-coded rules.

```
User Input
    ↓
┌─────────────────────────────────────────┐
│  STAGE 1: REASONING ENGINE              │
│  - What's my current stance?            │
│  - Has new info changed my view?        │
│  - What are my key points?              │
│  Output: Structured reasoning (JSON)    │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  STAGE 2: RESPONSE GENERATOR            │
│  - Generate natural debate message      │
│  - Based on Stage 1 reasoning           │
│  - Follow role/persona constraints      │
│  Output: Draft message (text)           │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  STAGE 3: CONSTITUTIONAL VALIDATOR      │
│  - Check for flip-flopping              │
│  - Check for hallucination              │
│  - Check role consistency               │
│  Output: Validated message or reject    │
└─────────────────────────────────────────┘
    ↓
Final Message
```

## Architecture

### Modular Design (Each file < 500 lines)

```
agent_memory.py (150 lines)
├── Retrieves agent's past messages
├── Builds memory context
└── Detects stance changes

agent_reasoning.py (200 lines)
├── Stage 1: Evaluates current stance
├── Determines if stance changed
└── Outputs structured reasoning (JSON)

agent_response_generator.py (300 lines)
├── Stage 2: Generates debate message
├── Uses reasoning from Stage 1
└── Follows universal debate rules

agent_constitutional_validator.py (250 lines)
├── Stage 3: Validates responses
├── Enforces consistency rules
├── Auto-corrects minor violations
└── Rejects critical violations

turn_orchestrator.py (integration)
├── Coordinates 3-stage pipeline
├── Fallback to legacy single LLM call
└── Feature flag: USE_CONSTITUTIONAL_AI
```

## Constitutional Rules (Hard-Coded, Topic-Agnostic)

1. **No Flip-Flopping**: If stance changed, must explicitly justify
2. **No Hallucination**: Don't reference agents who haven't spoken
3. **No Self-Contradiction**: Don't contradict previous messages
4. **Role Consistency**: Professional Arguer must disagree, Visionary must be forward-looking
5. **Must Engage**: Reference at least one other participant (if any exist)

## Topic Versatility

All rules and examples are **domain-agnostic**:
- Works for politics ("Which candidate?")
- Works for tech ("Which framework?")
- Works for ethics ("Which is right?")
- Works for products ("Which features?")

The system doesn't know about DMK/TVK/Stalin/Vijay - it just enforces:
- Intellectual consistency
- Justified stance changes
- Role-appropriate behavior

## Usage

### Enable Constitutional AI (default: ON)

```bash
# .env
USE_CONSTITUTIONAL_AI=true
```

### Disable (fallback to legacy single LLM call)

```bash
USE_CONSTITUTIONAL_AI=false
```

### Logs

When Constitutional AI is enabled, you'll see:

```
🧠 CONSTITUTIONAL AI PIPELINE for Visionary
  Stage 1: Reasoning...
    Stance: Stalin will win due to...
    Confidence: 0.85
    Changed: False
  Stage 2: Generating response...
    Generated 1247 chars
  Stage 3: Validating...
    ✅ Validation passed
```

If violations occur:

```
  Stage 3: Validating...
    ⚠️ Constitutional violations:
      - no_flip_flop: Agent changed stance but message doesn't explain why
    🔄 Needs regeneration - using constrained retry
```

## Testing

Test with different topics to verify versatility:

```bash
# Politics
"Who will win the 2026 Tamil Nadu election?"

# Tech
"Should we use React or Vue for our next project?"

# Ethics
"Is AI regulation necessary?"

# Product
"Should we prioritize mobile app or web platform?"
```

In all cases, agents should:
1. Form initial positions
2. Maintain consistency unless new evidence emerges
3. Explicitly justify stance changes
4. Not blindly agree with moderator

## Performance

- **Stage 1** (Reasoning): ~2-3s, 400 tokens
- **Stage 2** (Response): ~5-8s, 900 tokens
- **Stage 3** (Validation): <100ms, no LLM call
- **Total**: ~7-11s per agent turn (vs 5-8s legacy)

Trade-off: +40% latency for dramatically better consistency.

## Future Improvements

1. **Semantic similarity** for better contradiction detection (currently keyword-based)
2. **Debate-wide stance tracking** in database for analysis/debugging
3. **User-configurable rules** ("My agents must always cite sources")
4. **Multi-agent consistency** (detect if all agents are agreeing too much)
5. **Reasoning trace UI** (show users WHY agent said X)

## Maintenance

Each module is independent and testable:

```python
# Test reasoning engine
reasoning = AgentReasoningEngine(api_key).evaluate_stance(...)
assert reasoning['stance_changed'] == False

# Test validator
validation = ConstitutionalValidator().validate(...)
assert validation['valid'] == True
```

No file exceeds 500 lines. Easy to extend or replace individual stages.
