"""
Agent Memory System - Retrieves agent's past positions and reasoning

Anthropic-inspired approach: Agents need memory of their own past stances
to maintain consistency across turns. This is topic-agnostic.
"""
from typing import List, Dict, Any, Optional
from .database import get_db_connection, get_cursor


class AgentMemory:
    """Manages retrieval and summarization of an agent's debate history"""
    
    def __init__(self, debate_id: str, agent_name: str):
        self.debate_id = debate_id
        self.agent_name = agent_name
    
    def get_past_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve agent's past messages in this debate
        
        Returns:
            List of {turn: int, text: str, timestamp: datetime}
        """
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute("""
                SELECT 
                    content->>'text' as text,
                    sequence_number as turn,
                    created_at
                FROM events
                WHERE debate_id = %s
                  AND event_type = 'agent_message'
                  AND content->>'agent_name' = %s
                ORDER BY sequence_number DESC
                LIMIT %s
            """, (self.debate_id, self.agent_name, limit))
            
            messages = cursor.fetchall()
            cursor.close()
            return [
                {
                    "turn": msg["turn"],
                    "text": msg["text"],
                    "timestamp": msg["created_at"]
                }
                for msg in reversed(messages)  # Chronological order
            ]
    
    def build_memory_context(self, max_chars_per_message: int = 300) -> str:
        """
        Build a concise memory context for the agent
        
        Format:
        YOUR PAST POSITIONS IN THIS DEBATE:
        Turn 1: [summary]
        Turn 3: [summary]
        ...
        
        This is injected into the system prompt to give the agent
        a sense of their own history.
        """
        past_messages = self.get_past_messages(limit=5)
        
        if not past_messages:
            return "⚠️ This is your FIRST turn in this debate. You have no previous positions yet."
        
        memory_lines = ["📚 YOUR PAST POSITIONS IN THIS DEBATE:"]
        for msg in past_messages:
            # Truncate long messages
            text = msg["text"][:max_chars_per_message]
            if len(msg["text"]) > max_chars_per_message:
                text += "..."
            memory_lines.append(f"Turn {msg['turn']}: {text}")
        
        memory_lines.append("")
        memory_lines.append("⚠️ CONSISTENCY RULE: Build on these positions. If you change your view, explicitly state why.")
        
        return "\n".join(memory_lines)
    
    def extract_initial_stance(self) -> Optional[str]:
        """
        Extract the agent's initial position (first message)
        
        Returns:
            First ~200 chars of their opening message, or None if no messages yet
        """
        past_messages = self.get_past_messages(limit=1)
        if not past_messages:
            return None
        
        first_message = past_messages[0]["text"]
        # Extract first 200 chars as "initial stance"
        return first_message[:200].strip()
    
    def count_stance_changes(self, recent_turns: int = 5) -> int:
        """
        Count how many times the agent has significantly changed their position
        
        This is a simple heuristic: check for phrases like "I'm changing my view",
        "actually", "revising my position", etc.
        
        Used to detect flip-flopping.
        """
        past_messages = self.get_past_messages(limit=recent_turns)
        
        change_indicators = [
            "i'm changing",
            "i'm revising",
            "actually",
            "on second thought",
            "i was wrong",
            "reconsidering",
            "flipping my view"
        ]
        
        change_count = 0
        for msg in past_messages:
            text_lower = msg["text"].lower()
            if any(indicator in text_lower for indicator in change_indicators):
                change_count += 1
        
        return change_count
    
    def get_user_interventions(self) -> List[Dict[str, Any]]:
        """
        Get all user/moderator interventions in this debate
        
        Returns:
            List of {turn: int, text: str, actor: str}
        """
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute("""
                SELECT 
                    content->>'text' as text,
                    content->>'actor' as actor,
                    sequence_number as turn,
                    created_at
                FROM events
                WHERE debate_id = %s
                  AND event_type = 'human_message'
                ORDER BY sequence_number DESC
                LIMIT 10
            """, (self.debate_id,))
            
            interventions = cursor.fetchall()
            cursor.close()
            return [
                {
                    "turn": inv["turn"],
                    "text": inv["text"],
                    "actor": inv["actor"] or "Moderator"
                }
                for inv in reversed(interventions)
            ]
