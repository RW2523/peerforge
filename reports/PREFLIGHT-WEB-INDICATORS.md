# Preflight Web Search Indicators 🌐

**Date:** February 5, 2026  
**Status:** ✅ COMPLETE

---

## What Was Added

Visual indicators showing what each agent researched and analyzed during preflight preparation.

---

## UI Changes

### Before:
```
┌─────────────────────────────┐
│ 👤 Expert Analyst           │
│ ✅ Ready                     │
│ [View Prep Pack]            │
└─────────────────────────────┘
```

### After:
```
┌──────────────────────────────────┐
│ 👤 Expert Analyst  🌐 📄 3  🧠 5  │
│ ✅ Ready                          │
│ [📊 View Prep Pack]              │
└──────────────────────────────────┘
```

**Badges:**
- **🌐** - Web research performed (pulsing animation!)
- **📄 3** - 3 materials analyzed (green badge)
- **🧠 5** - 5 memory chunks used (purple badge)

---

## Badge Details

### 🌐 Web Research Badge
- **Color:** Blue gradient with purple accent
- **Animation:** Pulsing glow effect
- **Tooltip:** "Web research performed"
- **Shown when:** `metadata.web_research_performed === true`

### 📄 Materials Badge
- **Color:** Green
- **Shows count:** Number of materials analyzed
- **Tooltip:** "X materials analyzed"
- **Shown when:** Material count > 0

### 🧠 Memory Badge
- **Color:** Purple
- **Shows count:** Number of memory chunks retrieved
- **Tooltip:** "X memory chunks"
- **Shown when:** Memory count > 0

---

## CSS Styling

**File:** `SetupSteps.module.css`

```css
.webBadge {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(147, 51, 234, 0.15));
  border: 1px solid rgba(59, 130, 246, 0.3);
  color: #3b82f6;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4);
  }
  50% {
    opacity: 0.9;
    box-shadow: 0 0 0 4px rgba(59, 130, 246, 0);
  }
}
```

**Hover Effect:**
```css
.webBadge:hover {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.25), rgba(147, 51, 234, 0.25));
  transform: scale(1.05);
}
```

---

## Data Source

**Badges read from participant run metadata:**

```typescript
const webResearchPerformed = participantRun.metadata?.web_research_performed || false;
const materialsCount = participantRun.metadata?.material_chunks_count || 0;
const memoryCount = participantRun.metadata?.imported_chunks_count || 0;
```

**This metadata is set by backend during preflight:**
```python
# In tasks/preflight.py
Json({
    'web_research_performed': web_research_performed,
    'web_research_query': problem_statement[:100] if web_research_performed else None,
    'material_chunks_count': len(material_chunks),
    'imported_chunks_count': len(imported_chunks),
    'generated_at': datetime.utcnow().isoformat()
})
```

---

## Visual Hierarchy

**Badge priority (left to right):**
1. 🌐 Web research (most prominent - pulsing)
2. 📄 Materials count
3. 🧠 Memory count

**Why this order:**
- Web research is the most expensive operation (external API)
- Materials are user-uploaded (important to show they were used)
- Memory is background knowledge (least prominent)

---

## Examples

### Agent with Everything:
```
Expert Analyst  🌐 📄 5  🧠 12
```
- Did web research
- Analyzed 5 materials
- Retrieved 12 memory chunks

### Agent with No Web Search:
```
Consumer Advisor  📄 2  🧠 8
```
- No web research performed
- Analyzed 2 materials
- Retrieved 8 memory chunks

### Agent with Only Web Search:
```
Sustainability Advocate  🌐
```
- Did web research
- No materials uploaded
- No memory chunks available

---

## Accessibility

**Tooltip Hints:**
- Hover over 🌐 → "Web research performed"
- Hover over 📄 3 → "3 materials analyzed"
- Hover over 🧠 5 → "5 memory chunks"

**Visual Indicators:**
- Pulsing animation draws attention to web research
- Color coding: Blue (web), Green (materials), Purple (memory)
- Count badges show exact numbers

---

## Performance

**CSS Animations:**
- Hardware accelerated (transform, opacity)
- No layout thrashing
- 60fps smooth animation

**Render Cost:**
- Minimal - just conditional rendering
- No API calls
- Data already in participant run status

---

## Testing

### How to Verify:

1. **Create a debate** with a current topic (e.g., "AI Ethics 2026")
2. **Add OpenRouter API key** in Settings
3. **Click "Start Preparation"**
4. **Watch preflight progress**
5. **After completion:**
   - Look for **🌐 icons** on agent cards
   - Hover over badges to see tooltips
   - Click "📊 View Prep Pack" → Go to "🌐 Research" tab to see actual results

### Expected:
- All agents should have **🌐 badge** (if problem_statement exists)
- Badge should **pulse** with blue glow
- Hover should show "Web research performed"

---

## Future Enhancements

### Short Term:
- [ ] Click 🌐 badge to jump directly to Research tab in prep pack
- [ ] Show web research query on hover
- [ ] Add loading animation during web search

### Long Term:
- [ ] Show research quality score
- [ ] Indicate which sources were most useful
- [ ] Track research time vs token cost

---

## Status: ✅ DEPLOYED

**Backend:** Running, metadata includes web research flag
**Frontend:** Styled, badges display correctly
**Animation:** Pulsing web icon working
**Accessibility:** Tooltips added

**Now you can see at a glance which agents did web research!** 🌐✨
