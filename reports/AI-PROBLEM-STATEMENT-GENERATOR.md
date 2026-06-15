# AI Problem Statement Generator

## Overview

An AI-powered feature that helps users improve their problem statements for debates. Uses a cost-effective AI model (Claude Haiku) to rewrite user input into clear, debate-worthy problem statements with key discussion points.

## Features

### ✨ Improve with AI Button
- Located next to the "Problem Statement" field in Step 1 (Basic Info)
- Beautiful gradient button with sparkle icon
- Shows loading state during generation
- Disabled when no input is provided

### 📌 Key Discussion Points
- Extracts 3-5 key points from the improved statement
- Displays in a highlighted card below the textarea
- Dismissible by user
- Helps guide the debate focus

## Cost Effectiveness

**Model Used**: `anthropic/claude-3-haiku`
- **Cost**: ~$0.25 per 1M input tokens
- **Cost**: ~$1.25 per 1M output tokens
- **Average Cost per Request**: ~$0.001 (less than 1 cent)
- **Speed**: Very fast (<2 seconds typical)

This is ~10x cheaper than Claude Sonnet and ~20x cheaper than GPT-4.

## Implementation

### Backend

**File**: `/apps/api/src/routes/ai_assist.py`

New endpoint:
```
POST /ai/improve-problem-statement
Headers: X-OpenRouter-Key: <api_key>
Body: { "input_text": "rough problem statement" }

Response: {
  "improved_text": "Clear, debate-worthy problem statement",
  "key_points": [
    "Key point 1",
    "Key point 2",
    ...
  ]
}
```

**Features**:
- Input validation (min 10 characters)
- OpenRouter API key required
- Structured prompt engineering
- Error handling with specific HTTP status codes
- Timeout protection (30 seconds)

**Prompt Engineering**:
The system prompt instructs the AI to:
1. Make statements clear, concise, and specific
2. Frame as questions or problems to solve
3. Ensure multiple valid perspectives exist
4. Keep under 200 words
5. Extract 3-5 key discussion points

### Frontend

**File**: `/apps/web/src/components/setup/BasicInfoStep.tsx`

**Changes**:
1. Added "✨ Improve with AI" button next to label
2. Integrated OpenRouter key check
3. Loading state management
4. Key points display component
5. Error handling with user feedback

**File**: `/apps/web/src/components/setup/SetupSteps.module.css`

**New Styles**:
- `.generateButton` - Gradient purple button with hover effects
- `.keyPoints` - Highlighted card with slide-in animation
- `.keyPointsHeader` - Header with close button
- `.closeButton` - Dismiss button
- Updated `.section label` to flexbox layout

**File**: `/apps/web/src/lib/api.ts`

New function:
```typescript
export async function improveProblemStatement(
  inputText: string,
  openrouterKey: string
): Promise<ImproveProblemStatementResponse>
```

## User Experience

### Before AI Improvement
User types: "we need to figure out what to do about sales"

### After AI Improvement
```
How should our organization restructure its sales strategy to achieve 
30% growth in Q2 while maintaining customer satisfaction and team morale?

📌 Key Discussion Points:
→ Revenue growth targets and timeline
→ Customer experience and retention
→ Sales team capacity and motivation
→ Resource allocation and budgeting
→ Market conditions and competition
```

## Usage Flow

1. **User enters rough problem statement**
   - Any informal text describing the issue

2. **User clicks "✨ Improve with AI"**
   - Button disabled if no text or less than 10 characters
   - Checks for OpenRouter API key (redirects to settings if missing)

3. **AI generates improvement**
   - Loading indicator shows "⏳ Generating..."
   - Typically takes 1-3 seconds

4. **Results displayed**
   - Problem statement automatically replaced with improved version
   - Key points shown in highlighted card below
   - User can dismiss key points or edit the statement further

5. **User continues setup**
   - Improved statement is used for debate
   - Key points help inform agenda and outcomes

## Error Handling

### Missing API Key
- Redirects user to `/settings` page
- Prompts to add OpenRouter API key

### Short Input
- Alert: "Please enter at least 10 characters"
- Button remains disabled

### API Errors
- 400: Invalid request (input too short)
- 502: OpenRouter API error
- 504: Timeout (>30 seconds)
- 500: Unexpected server error

All errors shown as user-friendly alerts.

## Technical Details

### API Integration
- Uses OpenRouter's API endpoint
- Requires user's OpenRouter API key
- No server-side key storage
- Direct pass-through from frontend

### Model Parameters
```json
{
  "model": "anthropic/claude-3-haiku",
  "max_tokens": 500,
  "temperature": 0.7,
  "messages": [
    {"role": "system", "content": "<detailed prompt>"},
    {"role": "user", "content": "user input"}
  ]
}
```

### Response Parsing
1. Split on "KEY POINTS:" marker
2. Extract bullet points (lines starting with `-`, `•`, or `*`)
3. Clean and format
4. Fallback to full text if format not followed

## Benefits

### For Users
1. **Saves Time**: No need to craft perfect statements
2. **Better Debates**: Clear, focused problem statements
3. **Guided Discussion**: Key points provide structure
4. **Low Friction**: Single click to improve
5. **Learn by Example**: See how AI structures debates

### For System
1. **Higher Quality Inputs**: Better problem statements = better debates
2. **Cost Effective**: <$0.001 per request
3. **Fast**: No waiting, instant improvement
4. **Scalable**: Can handle high volume
5. **Optional**: Not required, just helpful

## Future Enhancements

1. **Template Library**
   - Pre-built problem statement templates
   - Industry-specific formats
   - Common debate structures

2. **Multi-Language Support**
   - Detect input language
   - Generate in same language

3. **Tone Selection**
   - Formal vs casual
   - Technical vs general
   - Collaborative vs adversarial

4. **Agenda Auto-Generation**
   - Use key points to populate agenda
   - One-click workflow

5. **History & Favorites**
   - Save improved statements
   - Reuse common patterns

## Testing

### Manual Test Cases
- [ ] Empty input → Button disabled
- [ ] Short input (<10 chars) → Alert shown
- [ ] Valid input → Improved statement generated
- [ ] No API key → Redirect to settings
- [ ] API error → User-friendly error message
- [ ] Key points generated → Displayed correctly
- [ ] Close key points → Card dismissed
- [ ] Edit improved text → Works normally
- [ ] Generate again → Updates content

### Example Inputs
1. "sales problem"
2. "how to increase revenue"
3. "team collaboration issues"
4. "should we pivot our product strategy?"
5. "remote work policy changes"

## Deployment

### Backend
- New route registered in `main.py`
- No database changes needed
- No environment variables needed
- Uses existing OpenRouter integration

### Frontend
- Component updates in setup wizard
- New CSS styles added
- API client function added
- No breaking changes

### Dependencies
- `httpx` (already installed)
- `anthropic` models via OpenRouter (no new SDK)

## Monitoring

### Metrics to Track
- Requests per day
- Average response time
- Error rate by type
- Cost per request
- User adoption rate

### Logs
```
INFO: AI assist request for problem statement improvement
INFO: Using model: anthropic/claude-3-haiku
INFO: Generated 245 tokens
ERROR: OpenRouter API error: 429 Rate Limited
```

## Conclusion

This feature significantly improves the user experience by helping craft better problem statements with minimal effort. The cost-effective approach using Claude Haiku ensures this remains scalable while providing high-quality results.

Users can now:
- Turn rough ideas into debate-worthy statements
- Get structured key points for discussion
- Save time on formulation
- Learn better problem framing

All with a single click and less than a penny in cost.
