"""Debate orchestration engine (M1: 5-turn round-robin)"""
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any
import psycopg2.extras
from .openrouter_client import OpenRouterClient
from .database import get_db_connection, get_cursor


class DebateEngine:
    """
    Core debate orchestration logic
    
    M1 scope: 5-turn deterministic round-robin across exactly 3 agents
    """
    
    def __init__(self, openrouter_api_key: str):
        """
        Initialize debate engine
        
        Args:
            openrouter_api_key: OpenRouter API key (BYOK)
        """
        self.openrouter_client = OpenRouterClient(openrouter_api_key)
    
    def run_debate(
        self,
        problem_statement: str,
        agents: List[Dict[str, str]],
        debate_title: str = "Untitled Debate"
    ) -> Dict[str, Any]:
        """
        Run complete 5-turn debate and persist to database
        
        Args:
            problem_statement: Problem to discuss
            agents: List of exactly 3 agent dicts with name, role, model_id
            debate_title: Optional debate title
        
        Returns:
            Dict with debate_id, status, outputs, event_history
        """
        if len(agents) != 3:
            raise ValueError("Exactly 3 agents required for M1")
        
        # Generate IDs
        debate_id = str(uuid.uuid4())
        workspace_id = "00000000-0000-0000-0000-000000000101"  # Demo workspace (local)
        
        # Store debate + participants
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            
            # Insert debate
            cursor.execute("""
                INSERT INTO debates (
                    debate_id, workspace_id, title, state, policy_config, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                debate_id,
                workspace_id,
                debate_title,
                'running',
                psycopg2.extras.Json({'problem_statement': problem_statement, 'turns': 5}),
                datetime.now(timezone.utc),
                datetime.now(timezone.utc)
            ))
            
            # Insert participants
            participant_ids = []
            for idx, agent in enumerate(agents):
                participant_id = str(uuid.uuid4())
                participant_ids.append(participant_id)
                
                cursor.execute("""
                    INSERT INTO participants (
                        participant_id, debate_id, participant_type, role_name,
                        agent_config, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    participant_id,
                    debate_id,
                    'agent',
                    agent['name'],
                    psycopg2.extras.Json({
                        'role': agent['role'],
                        'model_id': agent['model_id']
                    }),
                    datetime.now(timezone.utc)
                ))
            
            # System message event
            system_event_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO events (
                    event_id, debate_id, event_type, sender_type, sequence_number,
                    content, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                system_event_id,
                debate_id,
                'system_message',
                'system',
                0,
                psycopg2.extras.Json({'text': f'Debate started: {debate_title}', 'problem_statement': problem_statement}),
                datetime.now(timezone.utc)
            ))
        
        # Run 5-turn round-robin
        conversation_history = [
            {"role": "system", "content": f"Problem to discuss: {problem_statement}"}
        ]
        
        events = []
        sequence_num = 1
        
        for turn in range(5):
            agent_idx = turn % 3
            agent = agents[agent_idx]
            participant_id = participant_ids[agent_idx]
            
            # Build prompt for current agent
            messages = conversation_history.copy()
            messages.append({
                "role": "user",
                "content": f"You are {agent['name']}, a {agent['role']}. Continue the discussion with your perspective."
            })
            
            # Get response from OpenRouter
            response = self.openrouter_client.chat_completion(
                model=agent['model_id'],
                messages=messages,
                temperature=0.7
            )
            
            agent_message = response['content']
            
            # Add to conversation history
            conversation_history.append({
                "role": "assistant",
                "content": f"{agent['name']}: {agent_message}"
            })
            
            # Persist event
            event_id = str(uuid.uuid4())
            with get_db_connection() as conn:
                cursor = get_cursor(conn)
                cursor.execute("""
                    INSERT INTO events (
                        event_id, debate_id, event_type, sender_type, sender_id,
                        sequence_number, content, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    event_id,
                    debate_id,
                    'agent_message',
                    'agent',
                    participant_id,
                    sequence_num,
                    psycopg2.extras.Json({
                        'agent_name': agent['name'],
                        'text': agent_message,
                        'model': response['model'],
                        'turn': turn + 1
                    }),
                    datetime.now(timezone.utc)
                ))
            
            events.append({
                'event_id': event_id,
                'turn': turn + 1,
                'agent': agent['name'],
                'message': agent_message
            })
            
            sequence_num += 1
        
        # Generate final outputs using last agent to summarize
        outputs = self._generate_outputs(problem_statement, events, agents[-1]['model_id'])
        
        # Mark debate as completed
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute("""
                UPDATE debates SET state = %s, updated_at = %s WHERE debate_id = %s
            """, ('ended', datetime.now(timezone.utc), debate_id))
        
        return {
            'debate_id': debate_id,
            'status': 'ended',
            'outputs': outputs,
            'event_history': events
        }
    
    def _generate_outputs(
        self,
        problem_statement: str,
        events: List[Dict],
        model_id: str
    ) -> Dict[str, Any]:
        """
        Generate summary, minutes, and action items from debate
        
        Args:
            problem_statement: Original problem
            events: List of debate events
            model_id: Model to use for generation
        
        Returns:
            Dict with summary, minutes_of_meeting, action_items
        """
        # Build conversation summary
        discussion = "\n\n".join([
            f"Turn {e['turn']} - {e['agent']}:\n{e['message']}"
            for e in events
        ])
        
        prompt = f"""You are analyzing a debate discussion. Provide structured outputs.

Problem Statement:
{problem_statement}

Discussion:
{discussion}

Provide a JSON response with:
1. "summary": A 2-3 sentence high-level summary
2. "minutes_of_meeting": Detailed minutes (200-300 words)
3. "action_items": Array of 3-5 concrete action items

Format: {{"summary": "...", "minutes_of_meeting": "...", "action_items": ["item1", "item2", ...]}}"""
        
        response = self.openrouter_client.chat_completion(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        
        # Parse JSON from response (best effort)
        import json
        try:
            outputs = json.loads(response['content'])
        except json.JSONDecodeError:
            # Fallback if model doesn't return valid JSON
            outputs = {
                'summary': response['content'][:500],
                'minutes_of_meeting': response['content'],
                'action_items': ['Review discussion transcript', 'Schedule follow-up', 'Document decisions']
            }
        
        return outputs
