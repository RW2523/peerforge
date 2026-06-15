"""
Debate Enhancement System
Integrates validation and position assignment to improve debate quality.
"""

from typing import Dict, List, Any, Optional
from .debate_validator import DebateValidator, DebatePositionAssigner
from .database import get_db_connection, get_cursor
import json


class DebateEnhancer:
    """
    Coordinates debate improvements:
    - Position assignment at debate start
    - Message validation during turns
    - Retry logic for rejected messages
    """
    
    def __init__(self, openrouter_client):
        self.validator = DebateValidator()
        self.position_assigner = DebatePositionAssigner(openrouter_client)
        self.debate_positions: Dict[str, Dict] = {}  # debate_id -> dimensions
        self.agent_positions: Dict[str, Dict] = {}  # debate_id -> {agent_name -> position}
    
    def initialize_debate_positions(
        self,
        debate_id: str,
        debate_title: str,
        debate_description: str,
        desired_outcomes: List[str],
        participants: List[Dict]
    ) -> List[Dict]:
        """
        Called when debate starts.
        Extracts dimensions and assigns diverse positions to agents.
        """
        
        print(f"\n🎯 INITIALIZING DEBATE POSITIONS")
        print(f"   Debate: {debate_title}")
        print(f"   Participants: {len(participants)}")
        
        # Extract debate dimensions
        dimensions = self.position_assigner.extract_debate_dimensions(
            debate_title,
            debate_description,
            desired_outcomes
        )
        
        # Assign positions to agents
        participants_with_positions = self.position_assigner.assign_positions_to_agents(
            participants,
            dimensions
        )
        
        # Store for later validation
        self.debate_positions[debate_id] = dimensions
        self.agent_positions[debate_id] = {
            p['participant_name']: p.get('assigned_position', '')
            for p in participants_with_positions
        }
        
        # Persist to database
        self._persist_positions(debate_id, dimensions, self.agent_positions[debate_id])
        
        print(f"✅ Positions initialized for {len(participants)} agents\n")
        
        return participants_with_positions
    
    def validate_and_improve_message(
        self,
        message: str,
        agent_name: str,
        debate_id: str,
        round_number: int,
        retry_count: int = 0,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Validate agent message. If rejected, return retry instruction.
        
        Returns:
        {
            "approved": bool,
            "message": str (original or improved),
            "rejections": List[str],
            "retry_instruction": str,
            "should_retry": bool
        }
        """
        
        # Get debate history
        debate_history = self._get_debate_history(debate_id)
        agent_previous_messages = self._get_agent_messages(debate_id, agent_name)
        
        # Validate
        validation_result = self.validator.validate_message(
            message,
            agent_name,
            round_number,
            debate_history,
            agent_previous_messages
        )
        
        if validation_result['approved']:
            return {
                "approved": True,
                "message": message,
                "rejections": [],
                "retry_instruction": "",
                "should_retry": False
            }
        
        # Message rejected
        print(f"\n⚠️ MESSAGE REJECTED - {agent_name} (Round {round_number})")
        for rejection in validation_result['rejections']:
            print(f"   {rejection}")
        
        # Check if we should retry
        should_retry = retry_count < max_retries
        
        return {
            "approved": False,
            "message": message,
            "rejections": validation_result['rejections'],
            "retry_instruction": validation_result['retry_instruction'],
            "should_retry": should_retry
        }
    
    def get_agent_position(self, debate_id: str, agent_name: str) -> str:
        """Get the assigned position for an agent"""
        positions = self.agent_positions.get(debate_id, {})
        return positions.get(agent_name, "")
    
    def get_debate_dimensions(self, debate_id: str) -> Dict:
        """Get the extracted dimensions for a debate"""
        return self.debate_positions.get(debate_id, {})
    
    def _get_debate_history(self, debate_id: str, limit: int = 10) -> List[Dict]:
        """Get recent debate messages for context"""
        try:
            with get_db_connection() as conn:
                cursor = get_cursor(conn)
                cursor.execute("""
                    SELECT content, event_type, created_at
                    FROM events
                    WHERE debate_id = %s
                    AND event_type = 'agent_message'
                    ORDER BY sequence_number DESC
                    LIMIT %s
                """, (debate_id, limit))
                
                results = cursor.fetchall()
                return [
                    {
                        'message': r['content'].get('text', ''),
                        'agent': r['content'].get('agent_name', ''),
                        'created_at': r['created_at']
                    }
                    for r in results
                ]
        except Exception as e:
            print(f"⚠️ Failed to get debate history: {e}")
            return []
    
    def _get_agent_messages(self, debate_id: str, agent_name: str, limit: int = 5) -> List[str]:
        """Get agent's previous messages for repetition detection"""
        try:
            with get_db_connection() as conn:
                cursor = get_cursor(conn)
                cursor.execute("""
                    SELECT content
                    FROM events
                    WHERE debate_id = %s
                    AND event_type = 'agent_message'
                    AND content->>'agent_name' = %s
                    ORDER BY sequence_number DESC
                    LIMIT %s
                """, (debate_id, agent_name, limit))
                
                results = cursor.fetchall()
                return [r['content'].get('text', '') for r in results]
        except Exception as e:
            print(f"⚠️ Failed to get agent messages: {e}")
            return []
    
    def _persist_positions(
        self,
        debate_id: str,
        dimensions: Dict,
        agent_positions: Dict[str, str]
    ):
        """Store debate positions in database for reference"""
        try:
            with get_db_connection() as conn:
                cursor = get_cursor(conn)
                
                # Store in debate_outputs or a dedicated table
                cursor.execute("""
                    INSERT INTO debate_outputs (debate_id, output_type, content, created_at)
                    VALUES (%s, 'debate_positions', %s, NOW())
                    ON CONFLICT (debate_id, output_type) 
                    DO UPDATE SET content = EXCLUDED.content, created_at = NOW()
                """, (
                    debate_id,
                    json.dumps({
                        'dimensions': dimensions,
                        'agent_positions': agent_positions
                    })
                ))
                
                conn.commit()
                print(f"✅ Positions persisted to database")
                
        except Exception as e:
            print(f"⚠️ Failed to persist positions: {e}")
    
    def generate_enhanced_prompt(
        self,
        base_prompt: str,
        agent_name: str,
        debate_id: str,
        round_number: int
    ) -> str:
        """
        Enhance the agent's system prompt with:
        - Their assigned position
        - Round-specific instructions
        - Debate rules
        """
        
        # Get assigned position
        position = self.get_agent_position(debate_id, agent_name)
        
        # Get round-specific guidance
        round_guidance = self._get_round_guidance(round_number)
        
        # Combine
        enhanced_prompt = f"""{base_prompt}

{position}

📋 DISCUSSION GUIDANCE:

{round_guidance}

💡 BE CONSCIOUS:
- Read what others have said - don't repeat the same points
- If someone asks a question, consider answering it
- Add NEW information or perspectives
- Be specific when possible (examples, numbers, experiences)
- It's okay to disagree - but explain your reasoning
- It's okay to agree - but ADD something new to the point

Remember: Behave like a thoughtful human expert in a real discussion.
"""
        
        return enhanced_prompt
    
    def _get_round_guidance(self, round_number: int) -> str:
        """Get natural guidance based on debate progression"""
        
        # Natural progression - not forced
        if round_number == 1:
            return """
🎯 EARLY DISCUSSION:
- Share your perspective and expertise
- Ask clarifying questions if needed
- Provide evidence for your viewpoint
- Be authentic and thoughtful
"""
        else:
            return """
🎯 ONGOING DISCUSSION:
- Build on or challenge previous points thoughtfully
- Provide specific examples and evidence
- Be conscious of what's already been said - add new value
- Think critically but respectfully
- If you disagree, explain why clearly
"""
