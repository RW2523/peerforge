"""
Agent Thinking Service - Manages thinking events and persistence

Extracts thinking logic from turn_orchestrator to keep files modular.
Handles:
- Emitting thinking events via WebSocket
- Persisting thinking to database
- Retrieving thinking history
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
import asyncio
from .database import get_db_connection, get_cursor
import psycopg2.extras


class AgentThinkingService:
    """
    Service for managing agent thinking process visibility and persistence
    """
    
    _websocket_manager = None
    _event_loop = None
    
    @classmethod
    def set_broadcast_context(cls, manager, loop):
        """Set the WebSocket manager and event loop for broadcasting"""
        cls._websocket_manager = manager
        cls._event_loop = loop
    
    def __init__(self):
        self.current_thinking_session = None
    
    def start_thinking_session(self, debate_id: str, agent_name: str, turn_number: int) -> str:
        """
        Start a new thinking session for an agent turn
        Returns session_id for grouping all thinking steps
        """
        session_id = str(uuid.uuid4())
        self.current_thinking_session = {
            "session_id": session_id,
            "debate_id": debate_id,
            "agent_name": agent_name,
            "turn_number": turn_number,
            "started_at": datetime.now(timezone.utc),
            "steps": []
        }
        return session_id
    
    def emit_thinking_step(
        self,
        debate_id: str,
        agent_name: str,
        thinking_type: str,
        thinking_data: Dict[str, Any],
        persist: bool = True
    ):
        """
        Emit a single thinking step and optionally persist it
        
        Args:
            debate_id: The debate ID
            agent_name: Agent who is thinking
            thinking_type: Type of thinking (reasoning, generating, validating, etc.)
            thinking_data: Dict with stage, status, details
            persist: Whether to save to database
        """
        step = {
            "step_id": str(uuid.uuid4()),
            "thinking_type": thinking_type,
            "stage": thinking_data.get("stage", ""),
            "status": thinking_data.get("status", ""),
            "details": thinking_data.get("details", []),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        print(f"🧠 Emitting thinking step: {thinking_type} - {thinking_data.get('stage', '')}")
        
        # Add to current session
        if self.current_thinking_session:
            self.current_thinking_session["steps"].append(step)
        
        # Persist to database first to get sequence_number
        sequence_number = None
        if persist:
            sequence_number = self._persist_thinking_step(debate_id, agent_name, step)
        
        # Broadcast via WebSocket with actual sequence_number
        self._broadcast_thinking(debate_id, agent_name, step, sequence_number)
    
    def complete_thinking_session(self) -> Dict[str, Any]:
        """
        Complete the current thinking session and return summary
        """
        if not self.current_thinking_session:
            return {}
        
        session = self.current_thinking_session
        session["completed_at"] = datetime.now(timezone.utc)
        session["duration_seconds"] = (
            session["completed_at"] - session["started_at"]
        ).total_seconds()
        
        # Persist full session summary
        self._persist_thinking_session(session)
        
        # Clear current session
        result = session
        self.current_thinking_session = None
        return result
    
    def _broadcast_thinking(self, debate_id: str, agent_name: str, step: Dict[str, Any], sequence_number: int = None):
        """Send thinking step via WebSocket (non-blocking)"""
        try:
            from .websocket_service import websocket_manager
            
            # Create proper event envelope for WebSocket
            envelope = {
                "type": "agent_thinking",
                "debate_id": debate_id,
                "sequence_number": sequence_number,  # Use actual DB sequence number
                "event_id": step.get("step_id"),
                "occurred_at": step.get("timestamp"),
                "sender_type": "agent",
                "sender_id": agent_name,
                "payload": {
                    "agent_name": agent_name,
                    "thinking_type": step.get("thinking_type"),
                    "stage": step.get("stage"),
                    "status": step.get("status"),
                    "details": step.get("details", []),
                    "timestamp": step.get("timestamp")
                }
            }
            
            print(f"📡 Broadcasting thinking to debate {debate_id}: {step.get('stage')}")
            
            # Check active connections
            active_count = len(websocket_manager.active_connections.get(debate_id, []))
            print(f"   Active WebSocket connections for debate: {active_count}")
            
            # Broadcast via WebSocket using the event loop from the WS handler
            if self._websocket_manager and self._event_loop:
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self._websocket_manager.broadcast_to_debate(debate_id, envelope),
                        self._event_loop
                    )
                    future.result(timeout=5.0)
                    print(f"✅ Thinking broadcast via WebSocket")
                except Exception as e:
                    print(f"⚠️ Thinking broadcast failed: {e}")
            else:
                print(f"⚠️ No broadcast context set (manager={self._websocket_manager is not None}, loop={self._event_loop is not None})")
                
        except Exception as e:
            print(f"❌ Thinking broadcast error: {e}")
            import traceback
            traceback.print_exc()
    
    def _persist_thinking_step(self, debate_id: str, agent_name: str, step: Dict[str, Any]) -> int:
        """Persist individual thinking step to events table. Returns sequence_number."""
        try:
            with get_db_connection() as conn:
                cursor = get_cursor(conn)
                
                # Use step_id as event_id to prevent duplicates between WS and DB
                event_id = step.get("step_id", str(uuid.uuid4()))
                
                # Get next sequence number
                cursor.execute("""
                    SELECT COALESCE(MAX(sequence_number), 0) + 1 as next_seq
                    FROM events WHERE debate_id = %s
                """, (debate_id,))
                next_seq = cursor.fetchone()['next_seq']
                
                # Store as event with type 'agent_thinking'
                cursor.execute("""
                    INSERT INTO events (event_id, debate_id, event_type, sequence_number, sender_type, sender_id, content, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    event_id,
                    debate_id,
                    'agent_thinking',
                    next_seq,
                    'system',
                    None,
                    psycopg2.extras.Json({
                        "agent_name": agent_name,
                        "thinking_type": step["thinking_type"],
                        "stage": step["stage"],
                        "status": step["status"],
                        "details": step["details"],
                        "timestamp": step["timestamp"]
                    }),
                    datetime.now(timezone.utc)
                ))

                conn.commit()
                return next_seq  # Return sequence_number for WebSocket broadcast

        except Exception as e:
            print(f"⚠️ Thinking persistence error: {e}")
            return None
    
    def _persist_thinking_session(self, session: Dict[str, Any]):
        """Persist complete thinking session summary to agent_memories table"""
        try:
            with get_db_connection() as conn:
                cursor = get_cursor(conn)
                
                # Store in agent_memories as a 'thinking_session' type
                memory_id = str(uuid.uuid4())
                
                cursor.execute("""
                    INSERT INTO agent_memories (
                        memory_id, agent_role, debate_id, memory_type, content,
                        importance, emotional_valence, confidence, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    memory_id,
                    session["agent_name"],
                    session["debate_id"],
                    'thinking_session',
                    psycopg2.extras.Json({
                        "session_id": session["session_id"],
                        "turn_number": session["turn_number"],
                        "steps": session["steps"],
                        "duration_seconds": session.get("duration_seconds", 0),
                        "stages_completed": len(session["steps"])
                    }),
                    0.5,  # Medium importance
                    0.0,  # Neutral emotional valence
                    1.0,  # High confidence (it's raw thinking data)
                    session["completed_at"]
                ))
                
                conn.commit()
                print(f"💾 Thinking session saved: {len(session['steps'])} steps")
                
        except Exception as e:
            print(f"⚠️ Thinking session persistence error: {e}")
    
    def get_thinking_history(
        self,
        debate_id: str,
        agent_name: str = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve thinking history from database
        
        Args:
            debate_id: Debate to fetch from
            agent_name: Optional - filter by specific agent
            limit: Max number of thinking events to return
        """
        try:
            with get_db_connection() as conn:
                cursor = get_cursor(conn)
                
                if agent_name:
                    cursor.execute("""
                        SELECT event_id, sequence_number, content, created_at
                        FROM events
                        WHERE debate_id = %s 
                          AND event_type = 'agent_thinking'
                          AND content->>'agent_name' = %s
                        ORDER BY sequence_number DESC
                        LIMIT %s
                    """, (debate_id, agent_name, limit))
                else:
                    cursor.execute("""
                        SELECT event_id, sequence_number, content, created_at
                        FROM events
                        WHERE debate_id = %s 
                          AND event_type = 'agent_thinking'
                        ORDER BY sequence_number DESC
                        LIMIT %s
                    """, (debate_id, limit))
                
                rows = cursor.fetchall()
                
                return [
                    {
                        "event_id": row["event_id"],
                        "sequence": row["sequence_number"],
                        "agent_name": row["content"].get("agent_name"),
                        "thinking_type": row["content"].get("thinking_type"),
                        "stage": row["content"].get("stage"),
                        "status": row["content"].get("status"),
                        "details": row["content"].get("details", []),
                        "timestamp": row["created_at"].isoformat()
                    }
                    for row in rows
                ]
                
        except Exception as e:
            print(f"⚠️ Error fetching thinking history: {e}")
            return []
