"""Event streaming service for SSE"""
import json
import asyncio
from typing import AsyncGenerator, Optional, Dict, Any
from datetime import datetime, timezone
from .database import get_db_connection, get_cursor
from .state_machine import DebateState


class StreamService:
    """Service for streaming debate events via SSE"""
    
    def __init__(self):
        pass
    
    async def stream_debate_events(
        self,
        debate_id: str,
        since_sequence: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream debate events as Server-Sent Events
        
        Args:
            debate_id: Debate ID to stream
            since_sequence: Optional sequence number to start from (for resume)
        
        Yields:
            SSE formatted event strings
        
        Note:
            - Streams all events when debate is in any state
            - Respects state machine: ended debates close stream after final events
            - Client should handle reconnection for paused debates
        """
        try:
            # Get debate state
            debate = self._get_debate(debate_id)
            if not debate:
                yield f"event: error\ndata: {json.dumps({'error': 'Debate not found'})}\n\n"
                return
            
            state = debate['state']
            
            # Stream historical events first (filter out noisy types)
            events = self._get_events(debate_id, since_sequence or 0)
            
            for event in events:
                # Skip noisy event types that clutter the UI
                evt_type = event.get('event_type')
                if not evt_type or evt_type in ['system_message', 'presence_update', 'typing', 'heartbeat', 'keepalive']:
                    continue
                
                event_data = {
                    'event_id': event['event_id'],
                    'debate_id': event['debate_id'],
                    'event_type': event['event_type'],
                    'sequence_number': event['sequence_number'],
                    'occurred_at': event['occurred_at'].isoformat(),
                    'payload': event['payload']
                }
                yield f"event: debate_event\ndata: {json.dumps(event_data)}\n\n"
            
            # Send initial state update
            state_data = {
                'debate_id': debate_id,
                'state': state,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            yield f"event: state_update\ndata: {json.dumps(state_data)}\n\n"
            
            # If debate is ended, close stream
            if state == DebateState.ENDED.value:
                yield f"event: stream_end\ndata: {json.dumps({'reason': 'debate_ended'})}\n\n"
                return
            
            # Poll for new events (keep connection alive)
            last_sequence = since_sequence or (events[-1]['sequence_number'] if events else 0)
            poll_count = 0
            max_polls = 300  # 5 minutes (300 * 1 second)
            
            while poll_count < max_polls:
                await asyncio.sleep(1)  # Poll every 1 second
                poll_count += 1
                
                # Check for new events
                new_events = self._get_events(debate_id, last_sequence)
                
                for event in new_events:
                    # Skip noisy event types that clutter the UI (including NULL event_types)
                    evt_type = event.get('event_type')
                    if not evt_type or evt_type in ['system_message', 'presence_update', 'typing', 'heartbeat', 'keepalive']:
                        last_sequence = event['sequence_number']
                        continue
                    
                    event_data = {
                        'event_id': event['event_id'],
                        'debate_id': event['debate_id'],
                        'event_type': event['event_type'],
                        'sequence_number': event['sequence_number'],
                        'occurred_at': event['occurred_at'].isoformat(),
                        'payload': event['payload']
                    }
                    yield f"event: debate_event\ndata: {json.dumps(event_data)}\n\n"
                    last_sequence = event['sequence_number']
                
                # Check if debate state changed
                debate = self._get_debate(debate_id)
                if debate and debate['state'] != state:
                    state = debate['state']
                    state_data = {
                        'debate_id': debate_id,
                        'state': state,
                        'updated_at': datetime.now(timezone.utc).isoformat()
                    }
                    yield f"event: state_update\ndata: {json.dumps(state_data)}\n\n"
                    
                    # If ended, close stream
                    if state == DebateState.ENDED.value:
                        yield f"event: stream_end\ndata: {json.dumps({'reason': 'debate_ended'})}\n\n"
                        return
                
                # Send keepalive every 30 seconds
                if poll_count % 30 == 0:
                    yield f": keepalive\n\n"
            
            # Max duration reached
            yield f"event: stream_end\ndata: {json.dumps({'reason': 'max_duration_reached'})}\n\n"
            
        except Exception as e:
            error_data = {'error': f'Stream error: {str(e)}'}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
    
    def _get_debate(self, debate_id: str) -> Optional[Dict[str, Any]]:
        """Fetch debate from database"""
        with get_db_connection() as conn:
            with get_cursor(conn) as cur:
                cur.execute("""
                    SELECT debate_id, workspace_id, title, state, 
                           policy_config, created_at, updated_at
                    FROM debates
                    WHERE debate_id = %s
                """, (debate_id,))
                
                row = cur.fetchone()
                if not row:
                    return None
                
                return {
                    'debate_id': row['debate_id'],
                    'workspace_id': row['workspace_id'],
                    'title': row['title'],
                    'state': row['state'],
                    'policy_config': row['policy_config'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
    
    def _get_events(
        self,
        debate_id: str,
        since_sequence: int = 0
    ) -> list:
        """Fetch events for debate since given sequence"""
        with get_db_connection() as conn:
            with get_cursor(conn) as cur:
                cur.execute("""
                    SELECT event_id, debate_id, event_type, sequence_number,
                           created_at, content, sender_id
                    FROM events
                    WHERE debate_id = %s
                      AND sequence_number > %s
                    ORDER BY sequence_number ASC
                """, (debate_id, since_sequence))
                
                events = []
                for row in cur.fetchall():
                    events.append({
                        'event_id': row['event_id'],
                        'debate_id': row['debate_id'],
                        'event_type': row['event_type'],
                        'sequence_number': row['sequence_number'],
                        'occurred_at': row['created_at'],
                        'payload': row['content'],
                        'sender_id': row['sender_id']
                    })
                
                return events
