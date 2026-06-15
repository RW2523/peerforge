"""
Debate Message Validation System
Topic-agnostic validation for preventing echo chambers and circular debates.
"""

import re
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


class DebateValidator:
    """Validates agent messages to ensure productive debate progression"""
    
    # Banned phrases that indicate echo chamber behavior
    BANNED_AGREEABLE_PHRASES = [
        "i appreciate",
        "great point",
        "i agree with",
        "building on that",
        "you raised a valid point",
        "that's a good observation",
        "i completely agree",
        "excellent insight"
    ]
    
    # Vague phrases that should be minimized
    VAGUE_PHRASES = [
        "we should consider",
        "it's important to",
        "we need to think about",
        "we should evaluate",
        "it might be good to",
        "perhaps we could",
        "we should explore"
    ]
    
    # Words that indicate disagreement/challenge
    DISAGREEMENT_INDICATORS = [
        "however", "but", "disagree", "challenge", "contrary",
        "instead", "alternatively", "oppose", "question",
        "doubt", "skeptical", "problematic", "flawed"
    ]
    
    def __init__(self):
        self.message_history: List[str] = []
    
    def validate_message(
        self,
        message: str,
        agent_name: str,
        round_number: int,
        debate_history: List[Dict],
        agent_previous_messages: List[str]
    ) -> Dict[str, Any]:
        """
        Comprehensive validation of agent message.
        Returns: {
            "approved": bool,
            "rejections": List[str],
            "retry_instruction": str
        }
        """
        
        rejections = []
        message_lower = message.lower()
        
        # Check 1: Banned agreeable phrases
        for phrase in self.BANNED_AGREEABLE_PHRASES:
            if phrase in message_lower:
                # Allow if they're adding substantial new content (message is long enough)
                if len(message) < 300:  # Short message with agreement = echo chamber
                    rejections.append(f"❌ Contains agreeable phrase '{phrase}' without substantial new content")
        
        # Check 2: Excessive vagueness
        vague_count = sum(1 for phrase in self.VAGUE_PHRASES if phrase in message_lower)
        if vague_count > 2:
            rejections.append(f"❌ Too vague - contains {vague_count} non-specific phrases")
        
        # Check 3: Questions in later rounds
        question_count = message.count('?')
        if round_number >= 3 and question_count > 2:
            rejections.append(f"❌ Round {round_number} should focus on statements/conclusions, not questions ({question_count} found)")
        
        # Check 4: Disagreement requirement (Round 2+)
        if round_number >= 2:
            has_disagreement = any(indicator in message_lower for indicator in self.DISAGREEMENT_INDICATORS)
            if not has_disagreement:
                rejections.append(f"❌ Round {round_number} requires challenging/disagreeing with previous points")
        
        # Check 5: Specificity requirement
        has_numbers = any(char.isdigit() for char in message)
        has_specific_examples = bool(re.search(r'(example|e\.g\.|for instance|specifically|such as)', message_lower))
        has_citations = '(' in message and ')' in message
        
        specificity_score = sum([has_numbers, has_specific_examples, has_citations])
        if specificity_score == 0 and round_number >= 2:
            rejections.append(f"❌ Lacks specificity - needs numbers, examples, or specific references")
        
        # Check 6: Repetition detection (semantic similarity)
        if debate_history:
            is_repetitive = self._check_repetition(message, debate_history, agent_previous_messages)
            if is_repetitive:
                rejections.append(f"❌ Message repeats previous points - add NEW perspectives or evidence")
        
        # Check 7: Word limit (keep messages concise)
        word_count = len(message.split())
        if word_count > 400:
            rejections.append(f"❌ Message too long ({word_count} words) - keep under 400 words")
        if word_count < 50 and round_number >= 2:
            rejections.append(f"❌ Message too short ({word_count} words) - provide substantial argument")
        
        # Generate result
        if rejections:
            return {
                "approved": False,
                "rejections": rejections,
                "retry_instruction": self._generate_retry_instruction(rejections, round_number)
            }
        
        # Store in history
        self.message_history.append(message)
        
        return {
            "approved": True,
            "rejections": [],
            "retry_instruction": ""
        }
    
    def _check_repetition(
        self,
        new_message: str,
        debate_history: List[Dict],
        agent_previous_messages: List[str]
    ) -> bool:
        """
        Check if message is too similar to recent messages.
        Uses keyword overlap as a simple similarity measure.
        """
        
        # Extract key phrases from new message (3+ word phrases)
        new_keywords = self._extract_keywords(new_message)
        
        # Check against last 5 messages from ALL agents
        recent_messages = [
            msg.get('message', msg.get('content', {}).get('message', ''))
            for msg in debate_history[-5:]
            if msg.get('message') or msg.get('content', {}).get('message')
        ]
        
        for recent_msg in recent_messages:
            recent_keywords = self._extract_keywords(recent_msg)
            
            # Calculate overlap
            if new_keywords and recent_keywords:
                overlap = len(new_keywords & recent_keywords)
                overlap_ratio = overlap / max(len(new_keywords), len(recent_keywords))
                
                if overlap_ratio > 0.6:  # 60% keyword overlap
                    return True
        
        # Also check against agent's own previous messages
        for prev_msg in agent_previous_messages[-3:]:
            prev_keywords = self._extract_keywords(prev_msg)
            if new_keywords and prev_keywords:
                overlap = len(new_keywords & prev_keywords)
                overlap_ratio = overlap / max(len(new_keywords), len(prev_keywords))
                
                if overlap_ratio > 0.7:  # 70% overlap with own messages
                    return True
        
        return False
    
    def _extract_keywords(self, text: str) -> set:
        """Extract meaningful keywords from text"""
        # Remove common words and extract key phrases
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'be', 'been',
                    'i', 'you', 'we', 'they', 'this', 'that', 'these', 'those', 'what',
                    'which', 'who', 'when', 'where', 'why', 'how', 'can', 'could', 'would',
                    'should', 'may', 'might', 'must', 'will', 'shall'}
        
        # Lowercase and split
        words = text.lower().split()
        
        # Filter stopwords and short words
        keywords = {word.strip('.,!?;:()[]{}') for word in words 
                   if len(word) > 3 and word not in stopwords}
        
        return keywords
    
    def _generate_retry_instruction(self, rejections: List[str], round_number: int) -> str:
        """Generate specific instructions for improving the message"""
        
        instruction = f"""
🚫 Message Rejected - Round {round_number}

Reasons:
{chr(10).join(rejections)}

✅ To Fix:
"""
        
        if round_number == 1:
            instruction += """
- State YOUR unique position clearly (don't just ask questions)
- Provide specific evidence: numbers, studies, examples
- Focus on establishing your perspective
- Questions are OK, but back them with substance
"""
        elif round_number == 2:
            instruction += """
- CHALLENGE a specific claim from another agent
- Use words like "however", "but", "disagree", "contrary"
- Provide counter-evidence or alternative viewpoint
- Be specific and critical, not polite and vague
- Minimize questions - make assertions
"""
        elif round_number == 3:
            instruction += """
- Address criticisms of YOUR position directly
- Defend your stance with additional evidence
- Acknowledge valid points but explain why your approach prevails
- Refine your position based on new info
- No more questions - rebuttals and defenses only
"""
        else:  # Round 4+
            instruction += """
- Provide FINAL, ACTIONABLE recommendation
- Include specific steps, protocols, or concrete decisions
- Must be implementable (not vague suggestions)
- Synthesize the debate or stand firm on your position
- Conclude decisively - no more questions
"""
        
        return instruction


class DebatePositionAssigner:
    """Dynamically assigns diverse positions to agents based on debate topic"""
    
    def __init__(self, openrouter_client):
        self.openrouter_client = openrouter_client
    
    def extract_debate_dimensions(
        self,
        debate_title: str,
        debate_description: str,
        desired_outcomes: List[str]
    ) -> Dict[str, List[str]]:
        """
        Use LLM to extract key dimensions/trade-offs from the debate topic.
        Returns dimensions and possible stances for each.
        """
        
        prompt = f"""Analyze this debate and identify 3-4 key dimensions where experts might take different positions.

Debate Topic: {debate_title}
Description: {debate_description}
Goals: {', '.join(desired_outcomes[:3])}

For each dimension, identify 2-3 contrasting stances that experts could reasonably take.

Respond in JSON format:
{{
    "dimension_1_name": {{
        "description": "Brief description of this dimension",
        "stances": ["stance_a", "stance_b", "stance_c"]
    }},
    "dimension_2_name": {{ ... }},
    ...
}}

Example for "Best workout for asthma patient":
{{
    "risk_tolerance": {{
        "description": "How cautious vs aggressive to be",
        "stances": ["safety_first", "balanced_risk", "performance_focused"]
    }},
    "environment": {{
        "description": "Where exercise should occur",
        "stances": ["indoor_controlled", "flexible_mixed", "outdoor_preferred"]
    }},
    "intensity_level": {{
        "description": "How intense the exercise should be",
        "stances": ["low_intensity", "moderate_progressive", "high_intensity"]
    }}
}}

Now analyze the given debate topic:"""

        try:
            response = self.openrouter_client.chat_completion(
                model='openai/gpt-4o-mini',
                messages=[
                    {"role": "system", "content": "You analyze debate topics and extract key dimensions for structured disagreement."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )
            
            content = response.get('content', '{}')
            # Extract JSON from response (handle markdown code blocks)
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            dimensions = json.loads(content)
            print(f"✅ Extracted {len(dimensions)} debate dimensions")
            return dimensions
            
        except Exception as e:
            print(f"⚠️ Failed to extract dimensions: {e}")
            # Fallback to generic dimensions
            return {
                "approach": {
                    "description": "Overall approach or strategy",
                    "stances": ["conservative", "balanced", "aggressive"]
                },
                "priority": {
                    "description": "What to prioritize",
                    "stances": ["safety", "efficiency", "innovation"]
                }
            }
    
    def assign_positions_to_agents(
        self,
        agents: List[Dict],
        dimensions: Dict[str, Dict]
    ) -> List[Dict]:
        """
        Assign each agent a unique combination of stances across dimensions.
        Ensures maximum diversity in perspectives.
        """
        
        # Extract all possible stances for each dimension
        dimension_names = list(dimensions.keys())
        
        # For each agent, assign different stances
        for i, agent in enumerate(agents):
            assigned_stances = {}
            
            for dim_idx, dim_name in enumerate(dimension_names):
                stances = dimensions[dim_name]['stances']
                # Rotate through stances based on agent index
                stance_idx = (i + dim_idx) % len(stances)
                assigned_stances[dim_name] = stances[stance_idx]
            
            # Generate natural language description
            position_desc = self._format_position_description(
                agent['participant_name'],
                assigned_stances,
                dimensions
            )
            
            agent['assigned_position'] = position_desc
            agent['assigned_stances'] = assigned_stances
            
            print(f"  ✅ {agent['participant_name']}: {list(assigned_stances.values())}")
        
        return agents
    
    def _format_position_description(
        self,
        agent_name: str,
        stances: Dict[str, str],
        dimensions: Dict[str, Dict]
    ) -> str:
        """Convert stances into natural language guidance"""
        
        descriptions = []
        for dim_name, stance in stances.items():
            dim_info = dimensions.get(dim_name, {})
            desc = dim_info.get('description', dim_name)
            descriptions.append(f"- {desc.capitalize()}: advocate for a '{stance.replace('_', ' ')}' approach")
        
        return f"""
🎯 YOUR ASSIGNED PERSPECTIVE:

{chr(10).join(descriptions)}

This perspective ensures diverse viewpoints in the debate. Advocate for this angle, but adjust if strong evidence contradicts it.
Your role is to champion THIS perspective, challenge opposing views, and provide evidence for your stance.
"""
