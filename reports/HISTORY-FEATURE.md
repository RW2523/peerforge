# History Feature

## Overview

The History feature provides a comprehensive archive and viewing system for past debates, enabling users to:
- Browse all completed and ongoing debates
- View full conversation transcripts
- Access generated summaries and action items
- Navigate between debates easily

## Features

### 1. Debate Archive
- **List View**: Grid display of all debates with metadata
  - Title and state (pending, running, paused, ended)
  - Creation date
  - Participant and message counts
  - Quick action buttons

### 2. Full Transcript Viewer
- **Complete Conversation History**: View all messages in sequence order
- **Speaker Attribution**: Clear identification of each participant
- **Human Interventions**: Special highlighting for moderator messages
- **Sequence Numbers**: Track message order
- **Searchable**: Full text display for easy searching

### 3. Summary Viewer
- **Executive Summary**: High-level overview of the debate
- **Minutes of Meeting**: Detailed record of discussion
- **Action Items**: 
  - Prioritized tasks (high, medium, low)
  - Owner assignment
  - Clear descriptions
- **Metadata**: Generation timestamp and model used

## Implementation

### Backend APIs

#### 1. List Debates
```
GET /debates?workspace_id={id}&limit={n}&cursor={cursor}
```
Returns paginated list of debates with metadata.

#### 2. Get Events (New)
```
GET /debates/{debate_id}/events?limit={n}
```
Returns all events for a debate in sequence order for transcript viewing.

**Implementation**: `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/api/src/routes/events.py`

#### 3. Get Summary
```
GET /debates/{debate_id}/summary
```
Returns generated summary, minutes, and action items.

### Frontend Components

#### 1. History Page
**Location**: `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/web/src/app/history/page.tsx`

**Features**:
- Three view modes: List, Transcript, Summary
- Responsive grid layout
- State-based styling
- Empty states for no data
- Loading indicators

**Styling**: `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/web/src/app/history/history.module.css`

#### 2. Navigation Integration
**Location**: `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/web/src/components/layout/AppNav.tsx`

Added "📜 History" link to main navigation for easy access from anywhere.

#### 3. Summary Report Integration
**Location**: `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/web/src/components/room/SummaryReport.tsx`

Added "📜 View in History" button to allow quick navigation to history page from active debates.

### API Client Updates
**Location**: `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/web/src/lib/api.ts`

Added new functions:
```typescript
// Get all events for transcript viewing
export async function getDebateEvents(debateId: string): Promise<any[]>

// Get debate summary
export async function getDebateSummary(debateId: string): Promise<any>
```

## User Journey

### Viewing Past Debates

1. **Navigate to History**
   - Click "📜 History" in navigation bar
   - Or click "📜 View in History" from Summary Report

2. **Browse Debates**
   - See all debates in grid view
   - Filter by state (pending, running, paused, ended)
   - View metadata (date, participants, messages)

3. **View Transcript**
   - Click "📄 Transcript" on any debate card
   - See full conversation in chronological order
   - Human interventions are highlighted
   - Navigate back to list or open in room

4. **View Summary** (for ended debates)
   - Click "📊 Summary" on debate card
   - See executive summary and detailed minutes
   - Review action items with priorities
   - Option to view transcript or open in room

5. **Return to Debate**
   - Click "🏠 Open" to load debate in room
   - Resume or review active debates

## Data Structure

### Event Structure
```json
{
  "event_id": "uuid",
  "debate_id": "uuid",
  "event_type": "agent_turn | human_message | debate_summary",
  "sender_type": "agent | human | system",
  "sender_id": "agent_name",
  "sequence_number": 1,
  "content": {
    "agent_name": "AgentName",
    "text": "Message content",
    "actor": "Human name" // for human messages
  },
  "created_at": "2026-02-05T..."
}
```

### Summary Structure
```json
{
  "output_id": "uuid",
  "debate_id": "uuid",
  "summary": "Executive summary text",
  "minutes": "Detailed minutes of meeting",
  "action_items": [
    {
      "description": "Task description",
      "owner": "Responsible party",
      "priority": "high | medium | low"
    }
  ],
  "generated_at": "2026-02-05T...",
  "model_used": "anthropic/claude-3.5-sonnet"
}
```

## UI Design

### Color Coding
- **Pending**: Yellow/amber tones
- **Running**: Green tones (active)
- **Paused**: Red/warning tones
- **Ended**: Gray/muted tones
- **Human Messages**: Bright orange (#ff6b35)

### Layout
- Responsive grid for debate cards (min 380px per card)
- Full-width transcript and summary views
- Sticky headers for navigation
- Smooth transitions and hover effects

### Empty States
- Friendly messages when no debates exist
- Clear call-to-action to create first debate
- Helpful icons and guidance

## Technical Considerations

### Performance
- Pagination support for large debate lists (50 per page default)
- Lazy loading of transcripts and summaries
- Efficient event ordering using sequence numbers

### Security
- JWT authentication required for all endpoints
- Workspace access verification
- User can only view debates in their workspace

### Error Handling
- Graceful fallbacks for missing data
- Clear error messages
- 404 handling for non-existent debates
- Network error recovery

## Future Enhancements

1. **Search & Filter**
   - Full-text search across debates
   - Filter by date range, state, participants
   - Tag-based organization

2. **Export Options**
   - Download transcript as PDF/TXT
   - Export summary to various formats
   - Bulk export of debates

3. **Analytics Dashboard**
   - Debate statistics
   - Participation metrics
   - Topic analysis

4. **Favorites & Bookmarks**
   - Star important debates
   - Create collections
   - Quick access panel

5. **Annotations**
   - Add notes to specific messages
   - Highlight key moments
   - Personal annotations

## Testing

### Manual Testing Checklist
- [ ] Can view list of all debates
- [ ] Can view full transcript of debate
- [ ] Can view generated summary
- [ ] Can navigate back to list
- [ ] Can open debate in room
- [ ] Human interventions are highlighted
- [ ] Empty states display correctly
- [ ] Loading states work properly
- [ ] Error states show helpful messages
- [ ] Navigation links work correctly
- [ ] Responsive layout on mobile

### Edge Cases
- [ ] Debate with no events
- [ ] Debate without summary
- [ ] Very long transcripts
- [ ] Special characters in messages
- [ ] Multiple concurrent debates

## Deployment Notes

1. Backend changes in `routes/events.py` require deployment
2. Frontend is Next.js - standard build process
3. No database migrations needed (uses existing schema)
4. No environment variable changes required

## Conclusion

The History feature provides essential archival and review capabilities for the debate system. It enables users to:
- Maintain a complete record of all debates
- Review past discussions for insights
- Track action items and outcomes
- Share transcripts and summaries with stakeholders

This feature completes the debate lifecycle by preserving and making accessible all debate content.
