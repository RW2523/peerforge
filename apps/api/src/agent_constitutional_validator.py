"""
Constitutional Validator - Stage 3 of Constitutional AI Pipeline

Anthropic's Constitutional AI approach: Hard-coded rules that override
LLM outputs to ensure consistency and prevent flip-flopping.

This is the "safety layer" that catches bad behavior.
"""
import re
from typing import Dict, Any, Optional, List


class ConstitutionalValidator:
    """
    Stage 3: Validates agent responses against constitutional rules
    
    These are hard-coded rules that MUST be followed, regardless of
    what the LLM generates. If violated, the response is rejected/modified.
    """
    
    # Constitutional rules (topic-agnostic)
    CONSTITUTION = {
        "no_flip_flop": {
            "rule": "If stance changed without justification, reject",
            "severity": "critical"
        },
        "no_hallucination": {
            "rule": "Don't reference agents who haven't spoken",
            "severity": "critical"
        },
        "persona_authenticity": {
            "rule": "Must maintain unique character voice - no generic phrases that any agent could say",
            "severity": "high"
        },
        "no_repetition": {
            "rule": "Don't repeat what others just said - add NEW information or disagree",
            "severity": "high"
        },
        "no_self_contradiction": {
            "rule": "Don't contradict your previous messages",
            "severity": "high"
        },
        "must_address_others": {
            "rule": "Must engage with at least one other participant",
            "severity": "medium"
        },
        "role_consistency": {
            "rule": "Professional Arguer must disagree, Visionary must be forward-looking",
            "severity": "medium"
        }
    }
    
    # Generic phrases that destroy persona authenticity
    GENERIC_PHRASES = [
        "i appreciate your perspective",
        "your insights are spot-on",
        "you raise an important point",
        "you raise a good point",
        "building on what",
        "i completely acknowledge",
        "i hear your concerns",
        "that's a fair point",
        "you make a valid point"
    ]
    
    def __init__(self):
        pass
    
    def validate(
        self,
        message: str,
        reasoning: Dict[str, Any],
        agent_name: str,
        agent_role: str,
        past_messages: List[str],
        active_participants: List[str],
        recent_other_messages: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Validate message against constitutional rules
        
        Args:
            message: Generated debate message
            reasoning: Stage 1 reasoning output
            agent_name: Agent's name
            agent_role: Agent's role (for role-specific rules)
            past_messages: Agent's previous messages
            active_participants: Names of agents who have spoken
            recent_other_messages: Last 2-3 messages from OTHER agents (for repetition check)
        
        Returns:
            {
                "valid": bool,
                "violations": [{"rule": str, "severity": str, "details": str}],
                "corrected_message": str or None,
                "needs_regeneration": bool
            }
        """
        violations = []
        
        # Rule 1: Check for flip-flopping
        flip_flop_violation = self._check_flip_flop(
            message,
            reasoning,
            past_messages
        )
        if flip_flop_violation:
            violations.append(flip_flop_violation)
        
        # Rule 2: Check for hallucination (mentioning non-existent participants)
        hallucination_violation = self._check_hallucination(
            message,
            active_participants
        )
        if hallucination_violation:
            violations.append(hallucination_violation)
        
        # Rule 2.5: Check for persona authenticity (generic phrases)
        persona_violation = self._check_persona_authenticity(
            message,
            agent_name,
            agent_role
        )
        if persona_violation:
            violations.append(persona_violation)
        
        # Rule 3: Check for self-contradiction
        contradiction_violation = self._check_self_contradiction(
            message,
            past_messages
        )
        if contradiction_violation:
            violations.append(contradiction_violation)
        
        # Rule 4: Check for repetition (NEW - Anthropic-style)
        if recent_other_messages and reasoning.get("am_i_repeating") == "repeat":
            repetition_violation = self._check_repetition(
                message,
                recent_other_messages,
                reasoning
            )
            if repetition_violation:
                violations.append(repetition_violation)
        
        # Rule 5: Check role consistency
        role_violation = self._check_role_consistency(
            message,
            agent_role,
            reasoning
        )
        if role_violation:
            violations.append(role_violation)
        
        # Rule 6: Check engagement (must address others if they exist)
        if active_participants:
            engagement_violation = self._check_engagement(
                message,
                active_participants
            )
            if engagement_violation:
                violations.append(engagement_violation)
        
        # Determine severity
        critical_violations = [v for v in violations if v["severity"] == "critical"]
        
        result = {
            "valid": len(critical_violations) == 0,
            "violations": violations,
            "corrected_message": None,
            "needs_regeneration": len(critical_violations) > 0
        }
        
        # If correctable, attempt auto-fix
        if not result["valid"] and len(critical_violations) == 1:
            corrected = self._attempt_auto_fix(
                message,
                critical_violations[0],
                reasoning,
                active_participants
            )
            if corrected:
                result["corrected_message"] = corrected
                result["needs_regeneration"] = False
        
        return result
    
    def _check_flip_flop(
        self,
        message: str,
        reasoning: Dict[str, Any],
        past_messages: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Check if agent is flip-flopping without justification"""
        
        if not past_messages:
            return None  # First message, can't flip-flop
        
        if reasoning.get("stance_changed") == True:
            # Stance changed - check if message justifies it
            justification_phrases = [
                "i'm revising",
                "i'm changing",
                "reconsidering",
                "on second thought",
                "new information",
                "after hearing",
                "that changes"
            ]
            
            message_lower = message.lower()
            has_justification = any(phrase in message_lower for phrase in justification_phrases)
            
            if not has_justification:
                return {
                    "rule": "no_flip_flop",
                    "severity": "critical",
                    "details": "Agent changed stance but message doesn't explain why"
                }
        
        return None
    
    def _check_hallucination(
        self,
        message: str,
        active_participants: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Check if agent is referencing non-existent participants"""
        
        # Extract all @mentions from message
        mentions = re.findall(r'@["\']?([^"\',\s]+)["\']?', message)
        
        # Check if any mentions are not in active participants
        invalid_mentions = []
        for mention in mentions:
            # Clean up mention (remove quotes if present)
            clean_mention = mention.strip('"\'')
            if clean_mention not in active_participants:
                # Check for common placeholders
                if any(placeholder in clean_mention.lower() for placeholder in ['name', 'agent', 'person', 'someone']):
                    invalid_mentions.append(clean_mention)
        
        if invalid_mentions:
            return {
                "rule": "no_hallucination",
                "severity": "critical",
                "details": f"Message mentions non-existent participants: {invalid_mentions}"
            }
        
        return None
    
    def _check_self_contradiction(
        self,
        message: str,
        past_messages: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Check if agent contradicts their previous statements"""
        
        # This is a simple heuristic - in production you'd use semantic similarity
        if not past_messages:
            return None
        
        # Look for explicit contradictions
        contradiction_patterns = [
            (r'\bi was wrong\b', r'\bnow i (believe|think)\b'),
            (r'\bi said .* but\b', r'\bactually\b'),
        ]
        
        message_lower = message.lower()
        
        # If message contains "I was wrong" or similar, check if they justify it
        if any(re.search(pattern[0], message_lower) for pattern in contradiction_patterns):
            # This is okay if they explain why
            explanation_phrases = ["because", "due to", "given", "after", "since"]
            has_explanation = any(phrase in message_lower for phrase in explanation_phrases)
            
            if not has_explanation:
                return {
                    "rule": "no_self_contradiction",
                    "severity": "high",
                    "details": "Agent contradicts themselves without explanation"
                }
        
        return None
    
    def _check_role_consistency(
        self,
        message: str,
        agent_role: str,
        reasoning: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Check if agent is acting according to their role"""
        
        role_lower = agent_role.lower()
        message_lower = message.lower()
        
        # Professional Arguer / Contrarian must disagree
        if "arguer" in role_lower or "contrarian" in role_lower or "devil" in role_lower:
            disagreement_phrases = [
                "disagree", "wrong", "flawed", "incorrect", "not convinced",
                "challenge", "question", "doubt", "skeptical", "but", "however"
            ]
            has_disagreement = any(phrase in message_lower for phrase in disagreement_phrases)
            
            if not has_disagreement and reasoning.get("should_disagree_with"):
                return {
                    "rule": "role_consistency",
                    "severity": "medium",
                    "details": f"{agent_role} should disagree but message is too agreeable"
                }
        
        # Visionary should be forward-looking
        if "visionary" in role_lower:
            future_phrases = ["future", "will", "trend", "emerging", "next", "tomorrow", "ahead"]
            has_future_focus = any(phrase in message_lower for phrase in future_phrases)
            
            if not has_future_focus:
                return {
                    "rule": "role_consistency",
                    "severity": "medium",
                    "details": "Visionary should focus on future implications"
                }
        
        return None
    
    def _check_engagement(
        self,
        message: str,
        active_participants: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Check if agent engages with others"""
        
        # Check for @mentions or references to others
        has_mention = any(f"@{name}" in message or f'@"{name}"' in message for name in active_participants)
        
        # Check for indirect references
        reference_phrases = [
            "you said", "you mentioned", "your point", "as you noted",
            "building on", "responding to", "agree with", "disagree with"
        ]
        has_reference = any(phrase in message.lower() for phrase in reference_phrases)
        
        if not has_mention and not has_reference:
            return {
                "rule": "must_address_others",
                "severity": "medium",
                "details": "Agent should engage with other participants"
            }
        
        return None
    
    def _check_repetition(
        self,
        message: str,
        recent_other_messages: List[str],
        reasoning: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Check if agent is repeating what others just said
        
        This is an Anthropic-style constitutional check: agents must add NEW information,
        not just rephrase what others said.
        """
        # If reasoning stage flagged this as repetition, it's a violation
        if reasoning.get("am_i_repeating") == "repeat":
            return {
                "rule": "no_repetition",
                "severity": "high",
                "details": f"Agent is repeating what others said: '{reasoning.get('what_others_said', 'N/A')[:100]}...'. Must add NEW information or disagree."
            }
        
        # Additional check: keyword overlap with recent messages
        message_words = set(w.lower() for w in message.split() if len(w) > 4)
        
        for other_msg in recent_other_messages[-2:]:  # Check last 2 messages
            other_words = set(w.lower() for w in other_msg.split() if len(w) > 4)
            overlap = len(message_words & other_words)
            total = len(message_words)
            
            if total > 0:
                overlap_ratio = overlap / total
                
                # If >60% overlap, it's likely repetition
                if overlap_ratio > 0.6:
                    return {
                        "rule": "no_repetition",
                        "severity": "high",
                        "details": f"Message has {overlap_ratio*100:.0f}% word overlap with recent message. Must add unique perspective."
                    }
        
        return None
    
    def _check_persona_authenticity(
        self,
        message: str,
        agent_name: str,
        agent_role: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check if message uses generic phrases that destroy unique character voice
        
        This enforces agents to maintain distinct personas and avoid sounding identical
        """
        message_lower = message.lower()
        
        # Check for forbidden generic phrases
        found_generic_phrases = []
        for phrase in self.GENERIC_PHRASES:
            if phrase in message_lower:
                found_generic_phrases.append(phrase)
        
        if found_generic_phrases:
            return {
                "rule": "persona_authenticity",
                "severity": "high",
                "details": f"Message uses generic phrases that any agent could say: {', '.join(found_generic_phrases)}. Must use unique character voice for {agent_name} ({agent_role})."
            }
        
        # Check for "agreement then but" pattern
        agreement_but_pattern = r"(absolutely|definitely|certainly|i agree|you\'re right)[^.!?]*(\.|,)\s*(but|however|though|although)"
        if re.search(agreement_but_pattern, message_lower, re.IGNORECASE):
            return {
                "rule": "persona_authenticity",
                "severity": "high",
                "details": f"Message starts with agreement then adds 'but/however' - this is formulaic. {agent_name} should take a clear stance, not hedge."
            }
        
        return None
    
    def _attempt_auto_fix(
        self,
        message: str,
        violation: Dict[str, Any],
        reasoning: Dict[str, Any],
        active_participants: List[str]
    ) -> Optional[str]:
        """Attempt to automatically fix a violation"""
        
        if violation["rule"] == "no_hallucination":
            # Remove placeholder mentions like @Name, @Agent1
            fixed = re.sub(r'@["\']?(Name|Agent\d*|Someone|Person)["\']?', '', message)
            return fixed.strip()
        
        if violation["rule"] == "no_flip_flop" and reasoning.get("reason_for_change"):
            # Prepend justification
            justification = f"I'm revising my position because {reasoning['reason_for_change']}. "
            return justification + message
        
        # Can't auto-fix, need regeneration
        return None
