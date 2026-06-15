"""Events and SSE streaming endpoints"""
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional, List
import psycopg2.extras
from ..auth import get_current_user, check_workspace_access
from ..debate_service import DebateService
from ..stream_service import StreamService
from ..database import get_db_connection, get_cursor

router = APIRouter()


@router.get("/debates/{debate_id}/events")
async def get_debate_events(
    debate_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    limit: Optional[int] = None,
    event_type: Optional[str] = None,
    since: Optional[int] = None
):
    """
    Get all events for a debate (for history/transcript viewing)
    
    Protected: Requires valid JWT and workspace access
    
    Args:
        debate_id: Debate ID
        limit: Optional limit on number of events (default: all)
        event_type: Optional filter by event type (e.g., 'agent_thinking')
        since: Optional - only return events with sequence_number > since
    
    Returns:
        List of events in sequence order (WSEventEnvelope format)
    """
    # Verify debate exists and user has access
    service = DebateService()
    debate = service.get_debate(debate_id)
    
    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debate {debate_id} not found"
        )
    
    check_workspace_access(current_user, debate['workspace_id'])
    
    # Fetch events
    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        
        query = """
            SELECT event_id, debate_id, event_type, sender_type, sender_id,
                   sequence_number, content, created_at
            FROM events
            WHERE debate_id = %s
        """
        params = [debate_id]
        
        if event_type:
            query += " AND event_type = %s"
            params.append(event_type)
        
        if since is not None:
            query += " AND sequence_number > %s"
            params.append(since)
        
        query += " ORDER BY sequence_number DESC"  # Get newest first for polling
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, tuple(params))
        events = cursor.fetchall()
        
        # Transform events to match WSEventEnvelope format
        return [{
            'event_id': event['event_id'],
            'debate_id': event['debate_id'],
            'type': event['event_type'],  # Map event_type to type
            'sender_type': event['sender_type'],
            'sender_id': event['sender_id'],
            'sequence_number': event['sequence_number'],
            'payload': event['content'],  # Map content to payload
            'occurred_at': event['created_at'].isoformat() if event.get('created_at') else None
        } for event in events]


@router.get("/debates/{debate_id}/events/stream")
async def stream_debate_events(
    debate_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    since: Optional[int] = None
):
    """
    Stream debate events via Server-Sent Events (SSE)
    
    Protected: Requires valid JWT and workspace access
    
    Args:
        debate_id: Debate ID to stream
        since: Optional sequence number to resume from
    
    Returns:
        StreamingResponse with SSE events
    
    Event types:
        - debate_event: Individual event from debate
        - state_update: Debate state changed
        - stream_end: Stream terminated (debate ended)
        - error: Error occurred
    
    Raises:
        401: Unauthorized
        403: Forbidden (workspace access denied)
        404: Debate not found
    """
    # Verify debate exists and user has access
    service = DebateService()
    debate = service.get_debate(debate_id)
    
    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debate {debate_id} not found"
        )
    
    check_workspace_access(current_user, debate['workspace_id'])
    
    # Stream events
    stream_service = StreamService()
    
    return StreamingResponse(
        stream_service.stream_debate_events(debate_id, since_sequence=since),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
