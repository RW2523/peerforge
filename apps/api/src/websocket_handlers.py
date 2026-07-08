"""
WebSocket Command Handlers
Extracted from websocket_service.py to maintain file size compliance.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Set
from fastapi import WebSocket
from .database import get_db_connection, get_cursor
from .debate_service import DebateService

logger = logging.getLogger(__name__)


class WebSocketCommandHandlers:
    """Command handlers for WebSocket debate room operations."""

    def __init__(self, manager, debate_service: DebateService):
        self.manager = manager
        self.debate_service = debate_service
        # Track debates that currently have a turn in progress (prevents duplicates)
        self._turns_in_progress: Set[str] = set()
    
    async def handle_join_presence(self, websocket: WebSocket, debate_id: str, user_id: str, request_id: str, persist_event_fn, create_envelope_fn, create_ack_fn):
        """Handle join_presence command."""
        event_data = await persist_event_fn(debate_id, 'presence_update', {
            'action': 'join',
            'participant_id': user_id
        }, sender_id=user_id)
        
        if event_data:
            envelope = create_envelope_fn(
                'presence_update',
                debate_id,
                {'action': 'join', 'participant_id': user_id},
                sequence_number=event_data['sequence_number'],
                event_id=event_data['event_id'],
                sender_type='user',
                sender_id=user_id
            )
            await self.manager.broadcast_to_debate(debate_id, envelope)
        
        await self.manager.send_to_client(websocket, create_ack_fn(request_id, 'join_presence'))
    
    async def handle_leave_presence(self, websocket: WebSocket, debate_id: str, user_id: str, request_id: str, persist_event_fn, create_envelope_fn, create_ack_fn):
        """Handle leave_presence command."""
        event_data = await persist_event_fn(debate_id, 'presence_update', {
            'action': 'leave',
            'participant_id': user_id
        }, sender_id=user_id)
        
        if event_data:
            envelope = create_envelope_fn(
                'presence_update',
                debate_id,
                {'action': 'leave', 'participant_id': user_id},
                sequence_number=event_data['sequence_number'],
                event_id=event_data['event_id'],
                sender_type='user',
                sender_id=user_id
            )
            await self.manager.broadcast_to_debate(debate_id, envelope)
        
        await self.manager.send_to_client(websocket, create_ack_fn(request_id, 'leave_presence'))
    
    async def handle_typing(self, websocket: WebSocket, debate_id: str, user_id: str, request_id: str, payload: Dict, create_envelope_fn, create_ack_fn):
        """Handle typing command (ephemeral, not persisted)."""
        # Don't persist typing events (they're ephemeral)
        envelope = create_envelope_fn(
            'typing',
            debate_id,
            {'participant_id': user_id, 'ping': payload.get('ping', False)},
            sender_type='user',
            sender_id=user_id
        )
        await self.manager.broadcast_to_debate(debate_id, envelope)
        await self.manager.send_to_client(websocket, create_ack_fn(request_id, 'typing'))
    
    async def handle_next_turn(self, websocket: WebSocket, debate_id: str, user_id: str, request_id: str, payload: Dict, create_envelope_fn, create_ack_fn, create_error_fn):
        """Handle control.next_turn — ACK immediately, execute turn as background task."""
        print(f"\n🎮 WEBSOCKET COMMAND: control.next_turn received")
        print(f"   Debate ID: {debate_id}")
        print(f"   User ID: {user_id}")
        print(f"   Request ID: {request_id}")

        openrouter_key = payload.get('openrouter_key')
        if not openrouter_key:
            print("❌ ERROR: No OpenRouter key in payload!")
            await self.manager.send_to_client(
                websocket, create_error_fn(request_id, 'control.next_turn', 'OpenRouter API key required')
            )
            return

        # Prevent concurrent turns for the same debate
        if debate_id in self._turns_in_progress:
            print(f"⚠️  Turn already in progress for debate {debate_id}")
            await self.manager.send_to_client(
                websocket,
                create_error_fn(request_id, 'control.next_turn', 'Turn already in progress — wait for the current agent to finish')
            )
            return

        self._turns_in_progress.add(debate_id)

        # ACK immediately so the WebSocket receive loop is unblocked for heartbeats/other commands
        await self.manager.send_to_client(websocket, create_ack_fn(request_id, 'control.next_turn'))
        print(f"✅ ACK sent; scheduling background turn for debate {debate_id}\n")

        # Run the actual LLM turn as a background task
        asyncio.create_task(
            self._execute_turn_background(debate_id, openrouter_key, create_envelope_fn)
        )

    async def _execute_turn_background(self, debate_id: str, openrouter_key: str, create_envelope_fn):
        """Background coroutine: run LLM turn and broadcast result to room."""
        try:
            from .turn_orchestrator import TurnOrchestrator
            from .agent_thinking_service import AgentThinkingService

            loop = asyncio.get_running_loop()
            AgentThinkingService.set_broadcast_context(self.manager, loop)

            def run_turn():
                orchestrator = TurnOrchestrator(openrouter_key)
                return orchestrator.trigger_next_turn(debate_id)

            result = await asyncio.to_thread(run_turn)
            print(f"✅ Background turn completed for debate {debate_id}")

            # Broadcast with field names matching the DB schema so historical + real-time are consistent:
            #   text       — message body (matches events.content->>'text')
            #   turn       — round number  (matches events.content->>'turn')
            envelope = create_envelope_fn(
                'agent_message',
                debate_id,
                {
                    'agent_name': result['participant_name'],
                    'text': result['message'],              # canonical field name
                    'turn': result['round_number'],         # round number (1, 2, 3…)
                    'model': result.get('model', ''),
                    'turn_number': result['turn_number'],   # sequential turn index (back-compat)
                    'citations': result.get('citations', []),  # Glass-Box grounding chips
                },
                sequence_number=result['sequence_number'],
                event_id=result['event_id'],
                sender_type='agent',
                sender_id=result['participant_id']
            )
            await self.manager.broadcast_to_debate(debate_id, envelope)
            print(f"✅ agent_message broadcast complete for debate {debate_id}\n")

        except Exception as e:
            print(f"❌ Background turn error for debate {debate_id}: {e}")
            import traceback
            traceback.print_exc()
            # Broadcast an error event so the room UI can react
            error_evt = {
                'type': 'error',
                'debate_id': debate_id,
                'sequence_number': None,
                'event_id': None,
                'occurred_at': datetime.now(timezone.utc).isoformat(),
                'sender_type': 'system',
                'sender_id': None,
                'payload': {'error': str(e), 'command': 'control.next_turn'},
                'request_id': None,
            }
            await self.manager.broadcast_to_debate(debate_id, error_evt)
        finally:
            self._turns_in_progress.discard(debate_id)
    
    async def handle_pause(self, websocket: WebSocket, debate_id: str, user_id: str, request_id: str, create_envelope_fn, create_ack_fn, create_error_fn):
        """Handle control.pause command."""
        debate = self.debate_service.pause_debate(debate_id)
        if debate:
            await self.manager.send_to_client(websocket, create_ack_fn(request_id, 'control.pause'))
            envelope = create_envelope_fn(
                'state_update',
                debate_id,
                {'state': 'paused'},
                sender_type='system'
            )
            await self.manager.broadcast_to_debate(debate_id, envelope)
        else:
            await self.manager.send_to_client(websocket, create_error_fn(request_id, 'control.pause', 'Failed to pause'))
    
    async def handle_resume(self, websocket: WebSocket, debate_id: str, user_id: str, request_id: str, create_envelope_fn, create_ack_fn, create_error_fn):
        """Handle control.resume command."""
        debate = self.debate_service.resume_debate(debate_id)
        if debate:
            await self.manager.send_to_client(websocket, create_ack_fn(request_id, 'control.resume'))
            envelope = create_envelope_fn(
                'state_update',
                debate_id,
                {'state': 'running'},
                sender_type='system'
            )
            await self.manager.broadcast_to_debate(debate_id, envelope)
        else:
            await self.manager.send_to_client(websocket, create_error_fn(request_id, 'control.resume', 'Failed to resume'))
    
    async def handle_end(self, websocket: WebSocket, debate_id: str, user_id: str, request_id: str, create_envelope_fn, create_ack_fn, create_error_fn):
        """Handle control.end command."""
        debate = self.debate_service.end_debate(debate_id)
        if debate:
            await self.manager.send_to_client(websocket, create_ack_fn(request_id, 'control.end'))
            envelope = create_envelope_fn(
                'state_update',
                debate_id,
                {'state': 'ended'},
                sender_type='system'
            )
            await self.manager.broadcast_to_debate(debate_id, envelope)
        else:
            await self.manager.send_to_client(websocket, create_error_fn(request_id, 'control.end', 'Failed to end'))
    
    async def handle_intervene(self, websocket: WebSocket, debate_id: str, user_id: str, request_id: str, payload: Dict, persist_event_fn, create_envelope_fn, create_ack_fn, create_error_fn):
        """Handle intervene command."""
        print(f"\n🎙️ INTERVENTION RECEIVED:")
        print(f"   Debate ID: {debate_id}")
        print(f"   User ID: {user_id}")
        print(f"   Message: {payload.get('message', '')[:100]}")
        print(f"   Tagged agents: {payload.get('tagged_agents', [])}\n")
        
        try:
            message_text = payload.get('message')
            if not message_text:
                raise ValueError("Intervention message required")
            
            # Persist intervention as 'human_message' event type (to match turn_orchestrator expectations)
            event_data = await persist_event_fn(debate_id, 'human_message', {
                'actor': payload.get('actor', 'Moderator'),
                'text': message_text,  # Changed from 'message' to 'text' to match turn_orchestrator
                'tagged_agents': payload.get('tagged_agents', []),
                'action': 'intervene'
            }, sender_id=user_id)
            
            print(f"✅ Intervention persisted as human_message with event_id: {event_data.get('event_id') if event_data else 'FAILED'}\n")
            
            if event_data:
                # Broadcast as 'human_message' type for consistency
                envelope = create_envelope_fn(
                    'human_message',
                    debate_id,
                    {
                        'actor': payload.get('actor', 'Moderator'),
                        'text': message_text,
                        'tagged_agents': payload.get('tagged_agents', [])
                    },
                    sequence_number=event_data['sequence_number'],
                    event_id=event_data['event_id'],
                    sender_type='user',
                    sender_id=user_id
                )
                await self.manager.broadcast_to_debate(debate_id, envelope)
                print(f"✅ Intervention broadcasted to all debate participants\n")
            
            await self.manager.send_to_client(websocket, create_ack_fn(request_id, 'intervene'))
        except Exception as e:
            print(f"❌ ERROR handling intervention: {e}")
            import traceback
            traceback.print_exc()
            await self.manager.send_to_client(websocket, create_error_fn(request_id, 'intervene', str(e)))
