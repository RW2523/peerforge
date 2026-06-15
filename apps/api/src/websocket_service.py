"""
WebSocket Service - Production Debate Room Transport
Handles authenticated WS connections, command processing, and event broadcast.
Refactored for file size compliance (command handlers in websocket_handlers.py).
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from .database import get_db_connection, get_cursor
from .debate_service import DebateService
from .websocket_handlers import WebSocketCommandHandlers

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per debate room with workspace isolation."""
    
    def __init__(self):
        # debate_id -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # websocket -> connection metadata
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, debate_id: str, user_id: str, workspace_id: str):
        """Register a new WebSocket connection for a debate room."""
        await websocket.accept()
        
        if debate_id not in self.active_connections:
            self.active_connections[debate_id] = set()
        
        self.active_connections[debate_id].add(websocket)
        self.connection_metadata[websocket] = {
            'debate_id': debate_id,
            'user_id': user_id,
            'workspace_id': workspace_id,
            'connected_at': datetime.now(timezone.utc)
        }
        
        logger.info(f"WS connected: debate={debate_id}, user={user_id}, total={len(self.active_connections[debate_id])}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.connection_metadata:
            metadata = self.connection_metadata[websocket]
            debate_id = metadata['debate_id']
            
            if debate_id in self.active_connections:
                self.active_connections[debate_id].discard(websocket)
                if not self.active_connections[debate_id]:
                    del self.active_connections[debate_id]
            
            del self.connection_metadata[websocket]
            logger.info(f"WS disconnected: debate={debate_id}")
    
    async def broadcast_to_debate(self, debate_id: str, message: Dict[str, Any]):
        """Broadcast a message to all connections in a debate room."""
        if debate_id not in self.active_connections:
            print(f"⚠️ No active connections for debate {debate_id}")
            return
        
        conn_count = len(self.active_connections[debate_id])
        msg_type = message.get('type', 'unknown')
        print(f"📤 Broadcasting {msg_type} to {conn_count} connection(s) for debate {debate_id}")
        
        disconnected = []
        for websocket in self.active_connections[debate_id]:
            try:
                await websocket.send_json(message)
                print(f"  ✅ Sent {msg_type} to websocket")
            except Exception as e:
                print(f"  ❌ Failed to send {msg_type}: {e}")
                logger.error(f"Failed to send to websocket: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws)
    
    async def send_to_client(self, websocket: WebSocket, message: Dict[str, Any]):
        """Send a message to a specific client."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send to client: {e}")
            self.disconnect(websocket)


class WebSocketService:
    """Core WebSocket service for debate room realtime transport."""
    
    def __init__(self):
        self.manager = ConnectionManager()
        self.debate_service = DebateService()
        self.handlers = WebSocketCommandHandlers(self.manager, self.debate_service)
    
    def _create_event_envelope(
        self,
        event_type: str,
        debate_id: str,
        payload: Dict[str, Any],
        sequence_number: Optional[int] = None,
        event_id: Optional[str] = None,
        sender_type: str = 'system',
        sender_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a strict event envelope for WebSocket messages."""
        return {
            'type': event_type,
            'debate_id': debate_id,
            'sequence_number': sequence_number,
            'event_id': event_id,
            'occurred_at': datetime.now(timezone.utc).isoformat(),
            'sender_type': sender_type,
            'sender_id': sender_id,
            'payload': payload,
            'request_id': request_id
        }
    
    def _create_ack(self, request_id: str, command: str) -> Dict[str, Any]:
        """Create ACK message for successful command."""
        return {
            'type': 'ack',
            'request_id': request_id,
            'command': command,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def _create_error(self, request_id: str, command: str, error: str) -> Dict[str, Any]:
        """Create ERROR message for failed command."""
        return {
            'type': 'error',
            'request_id': request_id,
            'command': command,
            'error': error,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    async def _persist_event(self, debate_id: str, event_type: str, payload: Dict[str, Any], sender_id: Optional[str] = None, sender_type: str = 'human') -> Optional[Dict[str, Any]]:
        """Persist event to database and return with sequence_number."""
        try:
            with get_db_connection() as conn:
                cursor = get_cursor(conn)
                
                # Get next sequence number for this debate
                cursor.execute("""
                    SELECT COALESCE(MAX(sequence_number), 0) + 1 as next_seq
                    FROM events
                    WHERE debate_id = %s
                """, (debate_id,))
                
                result = cursor.fetchone()
                next_seq = result['next_seq'] if result else 1
                
                # Insert event
                cursor.execute("""
                    INSERT INTO events (
                        event_id, debate_id, event_type, sequence_number,
                        created_at, content, sender_id, sender_type
                    ) VALUES (
                        gen_random_uuid(), %s, %s, %s,
                        NOW(), %s, %s, %s
                    )
                    RETURNING event_id, sequence_number, created_at
                """, (debate_id, event_type, next_seq, json.dumps(payload), sender_id, sender_type))
                
                event = cursor.fetchone()
                conn.commit()
                
                return {
                    'event_id': event['event_id'],
                    'sequence_number': event['sequence_number'],
                    'created_at': event['created_at'].isoformat()
                }
        except Exception as e:
            logger.error(f"Failed to persist event: {e}")
            return None
    
    async def handle_command(self, websocket: WebSocket, message: Dict[str, Any]):
        """Process command messages from client."""
        command = message.get('command')
        request_id = message.get('request_id', 'unknown')
        
        if not command:
            await self.manager.send_to_client(
                websocket,
                self._create_error(request_id, 'unknown', 'Missing command')
            )
            return
        
        # SECURITY: Get debate_id from connection metadata ONLY (never trust client)
        metadata = self.manager.connection_metadata.get(websocket, {})
        debate_id = metadata.get('debate_id')
        user_id = metadata.get('user_id')
        
        if not debate_id:
            await self.manager.send_to_client(
                websocket,
                self._create_error(request_id, command, 'Connection not associated with debate')
            )
            return
        
        # Validate client debate_id if provided (prevent mistakes, not for auth)
        client_debate_id = message.get('debate_id')
        if client_debate_id and client_debate_id != debate_id:
            await self.manager.send_to_client(
                websocket,
                self._create_error(request_id, command, f'Debate ID mismatch: connected to {debate_id}, requested {client_debate_id}')
            )
            return
        
        try:
            if command == 'join_presence':
                await self.handlers.handle_join_presence(websocket, debate_id, user_id, request_id, self._persist_event, self._create_event_envelope, self._create_ack)
            elif command == 'leave_presence':
                await self.handlers.handle_leave_presence(websocket, debate_id, user_id, request_id, self._persist_event, self._create_event_envelope, self._create_ack)
            elif command == 'typing':
                await self.handlers.handle_typing(websocket, debate_id, user_id, request_id, message.get('payload', {}), self._create_event_envelope, self._create_ack)
            elif command == 'control.next_turn':
                await self.handlers.handle_next_turn(websocket, debate_id, user_id, request_id, message.get('payload', {}), self._create_event_envelope, self._create_ack, self._create_error)
            elif command == 'control.pause':
                await self.handlers.handle_pause(websocket, debate_id, user_id, request_id, self._create_event_envelope, self._create_ack, self._create_error)
            elif command == 'control.resume':
                await self.handlers.handle_resume(websocket, debate_id, user_id, request_id, self._create_event_envelope, self._create_ack, self._create_error)
            elif command == 'control.end':
                await self.handlers.handle_end(websocket, debate_id, user_id, request_id, self._create_event_envelope, self._create_ack, self._create_error)
            elif command == 'intervene':
                await self.handlers.handle_intervene(websocket, debate_id, user_id, request_id, message.get('payload', {}), self._persist_event, self._create_event_envelope, self._create_ack, self._create_error)
            else:
                await self.manager.send_to_client(
                    websocket,
                    self._create_error(request_id, command, f'Unknown command: {command}')
                )
        except Exception as e:
            logger.error(f"Command handler error: {e}")
            await self.manager.send_to_client(
                websocket,
                self._create_error(request_id, command, str(e))
            )
    
    
    async def send_historical_events(self, websocket: WebSocket, debate_id: str, since_sequence: int = 0):
        """Send historical events to a newly connected client."""
        try:
            with get_db_connection() as conn:
                cursor = get_cursor(conn)
                cursor.execute("""
                    SELECT event_id, event_type, sequence_number, created_at, content, sender_id
                    FROM events
                    WHERE debate_id = %s AND sequence_number > %s
                    ORDER BY sequence_number ASC
                    LIMIT 100
                """, (debate_id, since_sequence))
                
                events = cursor.fetchall()
                
                for event in events:
                    try:
                        payload = json.loads(event['content']) if isinstance(event['content'], str) else event['content']
                    except:
                        payload = {}
                    
                    envelope = self._create_event_envelope(
                        event['event_type'],
                        debate_id,
                        payload,
                        sequence_number=event['sequence_number'],
                        event_id=event['event_id'],
                        sender_type='system' if not event.get('sender_id') else 'user',
                        sender_id=event.get('sender_id')
                    )
                    await self.manager.send_to_client(websocket, envelope)
        except Exception as e:
            logger.error(f"Failed to send historical events: {e}")


# Global manager instance
ws_service = WebSocketService()

# Export websocket manager for use in other modules (like preflight tasks)
websocket_manager = ws_service.manager
