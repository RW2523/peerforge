"""
Agent Strategic Actions - High-Agency Behaviors
Agents can interrupt, propose votes, challenge structure, etc.
"""

from typing import Dict, List, Any, Optional
from .openrouter_client import OpenRouterClient


class AgentStrategicPlanner:
    """Handles agentic strategic decisions during debates"""
    
    def __init__(self, openrouter_api_key: str):
        self.openrouter_client = OpenRouterClient(openrouter_api_key)
    
    def should_interrupt(
        self,
        agent_name: str,
        last_speaker: str,
        last_message: str,
        agent_personality: str
    ) -> Optional[Dict[str, Any]]:
        """
        Decide if agent should INTERRUPT the current speaker
        Returns: {"should_interrupt": bool, "reason": str, "response": str}
        """
        
        prompt = f"""You are {agent_name}. {last_speaker} just said:

"{last_message[:400]}"

**Should you INTERRUPT right now?**

Only interrupt if:
- They're spreading misinformation/dangerous advice
- They're making a critical logical error
- They're ignoring a major point you raised
- The urgency is HIGH

**Respond in JSON:**
{{"should_interrupt": true/false, "reason": "why", "your_interruption": "Your 20-word response"}}

Example interrupt: "Wait—that data is from 2022, completely outdated. The 2025 study shows the opposite."

If no strong reason to interrupt: {{"should_interrupt": false}}
"""
        
        try:
            response = self.openrouter_client.chat_completion(
                model='openai/gpt-4o-mini',
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=100
            )
            
            import json
            return json.loads(response['content'])
        except Exception as e:
            print(f"    ⚠️ Interrupt decision failed: {e}")
            return None
    
    def decide_strategic_action(
        self,
        agent_name: str,
        conversation_summary: str,
        round_number: int,
        max_rounds: int
    ) -> Optional[Dict[str, Any]]:
        """
        Agent proposes a tactical move to advance the debate:
        - Vote on a specific question
        - Break into sub-topics
        - Call for evidence
        - Suggest format change
        """
        
        prompt = f"""You are {agent_name}. Round {round_number}/{max_rounds}.

**Discussion so far:**
{conversation_summary[:500]}

**Can you propose a TACTICAL MOVE to advance this debate?**

Options:
1. **Vote**: "Let's vote: Should we do X or Y?"
   JSON: {{"move": "vote", "question": "Should we X or Y?", "options": ["X", "Y"]}}

2. **Break Down**: "This is too broad, let's tackle sub-questions"
   JSON: {{"move": "breakdown", "sub_topics": ["First X", "Then Y"]}}

3. **Demand Evidence**: "We need data on X before continuing"
   JSON: {{"move": "evidence", "what_needed": "Data on X"}}

4. **Challenge Structure**: "This format isn't working, try Y instead"
   JSON: {{"move": "restructure", "proposal": "Do Y instead"}}

5. **Nothing**: Discussion is fine
   JSON: {{"move": "none"}}

Be selective. Only propose if truly helpful. Respond in JSON:"""
        
        try:
            response = self.openrouter_client.chat_completion(
                model='openai/gpt-4o-mini',
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=120
            )
            
            import json
            decision = json.loads(response['content'])
            
            if decision.get('move') != 'none':
                return decision
        except Exception as e:
            print(f"    ⚠️ Tactical move failed: {e}")
        
        return None
