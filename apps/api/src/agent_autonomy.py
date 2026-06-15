"""
Agent Autonomy Service
Handles autonomous agent behaviors: coalition formation, private messaging, sub-task planning
"""

import uuid
import psycopg2.extras
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from .database import get_db_connection, get_cursor
from .openrouter_client import OpenRouterClient


class AgentAutonomyService:
    """
    Manages autonomous agent behaviors between turns:
    - Coalition formation (agents decide who to ally with)
    - Private messaging (agents negotiate strategies)
    - Sub-task planning (agents break down goals)
    """
    
    def __init__(self, openrouter_api_key: str):
        self.openrouter_client = OpenRouterClient(openrouter_api_key)
    
    def decide_strategic_action(
        self,
        debate_id: str,
        agent_name: str,
        conversation_history: List[Dict[str, Any]],
        problem_statement: str,
        current_round: int,
        max_rounds: int
    ) -> Optional[Dict[str, Any]]:
        """
        Agent decides if they want to propose a strategic action:
        - Interrupt (strong disagreement)
        - Propose vote on a specific point
        - Suggest breaking into sub-questions
        - Challenge debate format/structure
        - Call for evidence/data
        """
        
        # Get recent messages
        recent_context = "\n".join([
            f"{h.get('content', {}).get('agent_name', 'Agent')}: {h.get('content', {}).get('text', '')[:150]}"
            for h in conversation_history[-3:]
            if h.get('event_type') == 'agent_message'
        ])
        
        prompt = f"""You are {agent_name}. After hearing the recent discussion, do you want to propose a STRATEGIC ACTION?

**Recent discussion:**
{recent_context[:600]}

**Problem:** {problem_statement[:200]}
**Round:** {current_round}/{max_rounds}

**Your strategic options:**
1. **INTERRUPT** - Someone said something dangerously wrong, you need to jump in NOW
   Example: {{"action": "interrupt", "reason": "Data is completely wrong", "urgency": "high"}}

2. **PROPOSE VOTE** - The group is stuck, let's vote on a specific question
   Example: {{"action": "vote", "question": "Should we prioritize X or Y?", "options": ["X", "Y"]}}

3. **NARROW FOCUS** - This is too broad, let's break it into sub-questions
   Example: {{"action": "narrow", "sub_questions": ["First, address X", "Then, tackle Y"]}}

4. **CALL FOR EVIDENCE** - People are making claims without data
   Example: {{"action": "evidence", "what": "Need actual numbers on X"}}

5. **CHALLENGE FORMAT** - This debate structure isn't working
   Example: {{"action": "restructure", "proposal": "Let's do 1-on-1 mini-debates instead"}}

6. **NOTHING** - Discussion is flowing fine
   Example: {{"action": "none"}}

**Rules:**
- Be selective - only act if you feel STRONGLY
- Consider the round (early rounds = explore, late = decide)
- Don't interrupt unless truly urgent

**Respond in JSON:**"""
        
        try:
            response = self.openrouter_client.chat_completion(
                model='openai/gpt-4o-mini',
                messages=[
                    {"role": "system", "content": "You are a strategic thinker. Respond ONLY with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            import json
            decision = json.loads(response['content'])
            
            if decision.get('action') != 'none':
                print(f"    🎯 STRATEGIC ACTION by {agent_name}: {decision.get('action')}")
                return decision
            else:
                print(f"    ℹ️  {agent_name} chose no strategic action")
        except Exception as e:
            print(f"    ⚠️ Strategic decision failed: {e}")
        
        return None
    
    def analyze_and_form_coalitions(
        self, 
        debate_id: str, 
        current_agent_name: str,
        all_participants: List[Dict[str, Any]],
        conversation_history: List[Dict[str, Any]],
        desired_outcomes: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Agent decides if they vibe with someone - could be alliance, rivalry, or just respect.
        More strategic and purposeful - agents form coalitions with GOALS.
        
        Returns coalition details if they feel strongly about someone, None otherwise.
        """
        
        # Build context for coalition decision
        other_participants = [
            p for p in all_participants 
            if (p.get('agent_config') or {}).get('name') != current_agent_name
        ]
        
        if len(other_participants) < 1:
            return None  # Need at least one other agent
        
        participant_summaries = []
        for p in other_participants:
            name = (p.get('agent_config') or {}).get('name') or p.get('role_name', 'Agent')
            # Find their recent messages
            messages = [
                h['content'].get('text', '')[:150] 
                for h in conversation_history 
                if h.get('content', {}).get('agent_name') == name
            ]
            recent = messages[-1] if messages else "Has not spoken yet"
            participant_summaries.append(f"- {name}: {recent}")
        
        coalition_prompt = f"""You are {current_agent_name}. Form strategic coalitions with SPECIFIC GOALS.

**Other Participants:**
{chr(10).join(participant_summaries)}

**Options:**
1. **Alliance**: Team up to push a shared argument/strategy
   Example: {{"should_form_coalition": true, "members": ["Agent1"], "strategy": "Push for data-driven approach", "goal": "Win vote on X", "type": "alliance"}}

2. **Opposition**: Counter someone's weak logic together
   Example: {{"should_form_coalition": true, "members": ["Agent2"], "strategy": "Challenge Agent3's claims", "goal": "Expose flaws in Y", "type": "rivalry"}}

3. **Nothing**: No strategic need right now
   Example: {{"should_form_coalition": false}}

**Rules:**
- Coalitions need a PURPOSE and GOAL
- Be selective - only if strategically valuable
- Can include 1-2 other agents (strategic pairs work best)

**Respond in JSON:**"""
        
        try:
            response = self.openrouter_client.chat_completion(
                model='openai/gpt-4o-mini',  # Fast and reliable
                messages=[
                    {"role": "system", "content": "You are a human-like agent with opinions. Respond ONLY with valid JSON, no other text."},
                    {"role": "user", "content": coalition_prompt}
                ],
                temperature=0.7,  # Higher temp for more personality
                max_tokens=100  # Keep it brief
            )
            
            import json
            decision = json.loads(response['content'])
            
            if decision.get('should_form_coalition'):
                coalition_type = decision.get('type', 'alliance')
                coalition = {
                    'members': [current_agent_name] + decision.get('members', []),
                    'strategy': decision.get('strategy', 'Strategic coordination'),
                    'goal': decision.get('goal', 'Advance shared position'),
                    'type': coalition_type
                }
                emoji = '🤝' if coalition_type == 'alliance' else '⚔️'
                print(f"    {emoji} {coalition_type.upper()} formed by {current_agent_name}: {coalition}")
                return coalition
            else:
                print(f"    ℹ️  {current_agent_name} chose NOT to form coalition this turn")
        except Exception as e:
            print(f"    ⚠️ Coalition analysis failed: {e}")
        
        return None
    
    def generate_private_message(
        self,
        debate_id: str,
        from_agent: str,
        to_agent: str,
        conversation_context: str,
        desired_outcomes: List[str],
        previous_dm: Optional[str] = None
    ) -> Optional[str]:
        """Generate human-like private message with personality"""
        
        # Add previous DM context if this is a reply
        previous_context = ""
        if previous_dm:
            previous_context = f"\n**Previous message from {to_agent}:**\n{previous_dm}\n\n(You're REPLYING to this message)\n"
        
        message_prompt = f"""You are {from_agent}. DM {to_agent} privately.
{previous_context}
**Debate context:**
{conversation_context[:400]}

**DM like a real person:**
- React to what THEY said/did specifically
- Be casual and direct - it's private
- Strategy, criticism, support, sarcasm, challenge, venting, or coordination

**Examples:**
- "Yo, back me up on X next turn"
- "Your Y argument was weak tbh"
- "Let's tag-team them on Z"
- "Did you seriously argue for that? lol"
- "You crushed it with that data"
- "They're missing the obvious - noticed?"
- "Want to propose a vote on X?"
- "I'm interrupting next if they keep going"
- "Challenge: you vs me on X, one round"
- "Form alliance? We can push for Y together"
- "Need you to call out Z next turn"

Respond with ONLY the message (15-40 words):**"""
        
        try:
            response = self.openrouter_client.chat_completion(
                model='openai/gpt-oss-20b:free',  # Free, fast, more conversational
                messages=[
                    {"role": "system", "content": "You are a human with personality. Be genuine, witty, or critical as needed."},
                    {"role": "user", "content": message_prompt}
                ],
                temperature=0.95,  # Very high temp for personality
                max_tokens=100  # More room for expression
            )
            
            message = response['content'].strip().strip('"\'')[:280]  # Cap at 280 chars, remove quotes
            print(f"    💬 Private message: {from_agent} → {to_agent}: {message[:60]}...")
            return message
        except Exception as e:
            print(f"    ⚠️ Private message generation failed: {e}")
            return None
    
    def plan_subtasks(
        self,
        debate_id: str,
        agent_name: str,
        problem_statement: str,
        desired_outcomes: List[str]
    ) -> List[str]:
        """
        Agent breaks down the problem into sub-tasks.
        Token-efficient: max 3 sub-tasks, each under 15 words.
        """
        
        subtask_prompt = f"""You are {agent_name}. Break down this problem into 2-3 actionable sub-tasks.

**Problem**: {problem_statement[:200]}
**Desired Outcomes**: {', '.join(desired_outcomes[:2]) if desired_outcomes else 'N/A'}

**List 2-3 sub-tasks (each max 12 words). Format:**
1. [Task 1]
2. [Task 2]
3. [Task 3]

Be specific and actionable. Keep it brief."""
        
        try:
            response = self.openrouter_client.chat_completion(
                model='openai/gpt-4o-mini',
                messages=[{"role": "user", "content": subtask_prompt}],
                temperature=0.4,
                max_tokens=80
            )
            
            # Parse numbered list
            tasks = []
            for line in response['content'].split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-')):
                    task = line.lstrip('0123456789.-) ').strip()
                    if task:
                        tasks.append(task[:100])  # Cap each task
            
            return tasks[:3]  # Max 3 tasks
        except Exception as e:
            print(f"    ⚠️ Sub-task planning failed: {e}")
            return []
