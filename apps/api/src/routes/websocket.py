"""
WebSocket Routes - Authenticated Debate Room Transport
"""
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from typing import Dict, Any
from ..auth import get_current_user_ws, check_workspace_access
from ..debate_service import DebateService
from ..websocket_service import ws_service
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/debates/{debate_id}")
async def websocket_debate_room(
    websocket: WebSocket,
    debate_id: str
):
    """
    WebSocket endpoint for debate room realtime transport.
    
    Auth: Validates Supabase JWT via query param `token`
    
    Features:
    - Historical event replay
    - Realtime event broadcast
    - Command processing (presence, typing, controls)
    - ACK/ERROR responses
    - Workspace isolation
    
    Message format (client → server):
    {
        "command": "join_presence" | "leave_presence" | "typing" | "control.*",
        "debate_id": "uuid",
        "request_id": "client-generated-id",
        "payload": {}
    }
    
    Message format (server → client):
    {
        "type": "event_type",
        "debate_id": "uuid",
        "sequence_number": 1,
        "event_id": "uuid",
        "occurred_at": "ISO8601",
        "sender_type": "system" | "user" | "agent",
        "sender_id": "uuid",
        "payload": {},
        "request_id": "optional"
    }
    
    ACK format:
    {
        "type": "ack",
        "request_id": "...",
        "command": "...",
        "timestamp": "ISO8601"
    }
    
    ERROR format:
    {
        "type": "error",
        "request_id": "...",
        "command": "...",
        "error": "error message",
        "timestamp": "ISO8601"
    }
    """
    print(f"\n🔌 WebSocket endpoint ENTERED: debate_id={debate_id}")
    logger.info(f"🔌 WebSocket endpoint ENTERED: debate_id={debate_id}")
    
    try:
        # Extract query params
        query_params = dict(websocket.query_params)
        print(f"📝 Query params: {list(query_params.keys())}")
        
        # Auth: mirrors HTTP behavior — open in dev (require_auth=false),
        # JWT required via ?token= query param otherwise.
        from ..config import settings as _settings
        if _settings.require_auth:
            token = query_params.get('token')
            if not token:
                logger.warning(f"WS rejected (no token): debate={debate_id}")
                await websocket.close(code=1008, reason="Missing auth token")
                return
            try:
                user = await get_current_user_ws(token)
            except Exception as auth_exc:
                logger.warning(f"WS rejected (invalid token): debate={debate_id} — {auth_exc}")
                await websocket.close(code=1008, reason="Invalid auth token")
                return
            user_id = user.get('sub') or user.get('user_id') or 'unknown'
            workspace_id = user.get('workspace_id')
            if not workspace_id:
                await websocket.close(code=1008, reason="User not associated with a workspace")
                return
        else:
            # Local dev identity (same defaults as HTTP auth bypass)
            user_id = 'test-user'
            workspace_id = '00000000-0000-0000-0000-000000000101'

        print(f"✅ Attempting to connect WebSocket...")
        logger.info(f"✅ Attempting to connect WebSocket...")
        
        # Accept connection FIRST
        await ws_service.manager.connect(websocket, debate_id, user_id, workspace_id)
        
        print(f"✅ WebSocket connected successfully!")
        logger.info(f"✅ WebSocket connected successfully!")
        
        try:
            # Send historical events
            since_sequence = int(query_params.get('since', 0))
            await ws_service.send_historical_events(websocket, debate_id, since_sequence)

            # Event loop — process each incoming message as a background task so
            # the receive loop is never blocked by long-running commands (e.g. LLM turns).
            # handle_command catches all exceptions internally and sends error responses.
            while True:
                data = await websocket.receive_json()
                asyncio.create_task(ws_service.handle_command(websocket, data))
        
        except WebSocketDisconnect:
            ws_service.manager.disconnect(websocket)
            logger.info(f"WebSocket disconnected: debate={debate_id}, user={user_id}")
        except Exception as e:
            logger.error(f"WebSocket error in event loop: {e}")
            import traceback
            traceback.print_exc()
            ws_service.manager.disconnect(websocket)
    
    except Exception as e:
        print(f"❌ WEBSOCKET ENDPOINT ERROR: {e}")
        logger.error(f"❌ WEBSOCKET ENDPOINT ERROR: {e}")
        import traceback
        traceback.print_exc()
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass
