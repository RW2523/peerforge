"""
Document WebSocket Hub
Handles Yjs CRDT synchronization for collaborative documents
"""
import logging
import asyncio
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
import json

logger = logging.getLogger(__name__)


class DocumentWebSocketHub:
    """Manages WebSocket connections for document collaboration"""
    
    def __init__(self):
        # document_id -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # document_id -> yjs state (for persistence)
        self.document_states: Dict[str, bytes] = {}
        
    async def connect(self, websocket: WebSocket, document_id: str):
        """Accept new websocket connection"""
        await websocket.accept()
        
        if document_id not in self.active_connections:
            self.active_connections[document_id] = set()
        
        self.active_connections[document_id].add(websocket)
        
        logger.info(f"Client connected to document {document_id}. Total: {len(self.active_connections[document_id])}")
        
    def disconnect(self, websocket: WebSocket, document_id: str):
        """Remove websocket connection"""
        if document_id in self.active_connections:
            self.active_connections[document_id].discard(websocket)
            
            # Cleanup empty document rooms
            if not self.active_connections[document_id]:
                del self.active_connections[document_id]
                
        logger.info(f"Client disconnected from document {document_id}")
        
    async def broadcast(self, document_id: str, message: bytes, sender: WebSocket = None):
        """Broadcast message to all connections except sender"""
        if document_id not in self.active_connections:
            return
            
        # Send to all clients except sender
        disconnected = []
        for connection in self.active_connections[document_id]:
            if connection != sender:
                try:
                    await connection.send_bytes(message)
                except Exception as e:
                    logger.error(f"Failed to send to client: {e}")
                    disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection, document_id)
    
    async def send_to(self, websocket: WebSocket, message: bytes):
        """Send message to specific client"""
        try:
            await websocket.send_bytes(message)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise
    
    def get_connection_count(self, document_id: str) -> int:
        """Get number of active connections for document"""
        return len(self.active_connections.get(document_id, set()))
    
    def get_document_state(self, document_id: str) -> bytes:
        """Get persisted Yjs state"""
        return self.document_states.get(document_id, b'')
    
    def set_document_state(self, document_id: str, state: bytes):
        """Persist Yjs state"""
        self.document_states[document_id] = state
        logger.debug(f"Persisted state for document {document_id}: {len(state)} bytes")


# Global hub instance
document_hub = DocumentWebSocketHub()


async def handle_document_websocket(websocket: WebSocket, document_id: str):
    """
    Handle WebSocket connection for document collaboration
    Implements Yjs sync protocol
    """
    await document_hub.connect(websocket, document_id)
    
    try:
        # Send initial state if exists
        initial_state = document_hub.get_document_state(document_id)
        if initial_state:
            await document_hub.send_to(websocket, initial_state)
        
        # Main message loop
        while True:
            # Receive message (can be text or binary)
            try:
                # Try binary first (Yjs updates are binary)
                message = await websocket.receive_bytes()
                
                # Persist state updates
                document_hub.set_document_state(document_id, message)
                
                # Broadcast to other clients
                await document_hub.broadcast(document_id, message, sender=websocket)
                
            except RuntimeError:
                # Try text message
                try:
                    text_message = await websocket.receive_text()
                    data = json.loads(text_message)
                    
                    # Handle text-based messages (awareness, control)
                    if data.get('type') == 'ping':
                        await websocket.send_text(json.dumps({'type': 'pong'}))
                    elif data.get('type') == 'awareness':
                        # Broadcast awareness to others
                        await document_hub.broadcast(
                            document_id,
                            text_message.encode(),
                            sender=websocket
                        )
                        
                except json.JSONDecodeError:
                    logger.error("Invalid JSON message")
                    
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from document {document_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        document_hub.disconnect(websocket, document_id)
