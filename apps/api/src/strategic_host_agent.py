"""
Strategic Host Agent - Meta-moderator intelligence

Anthropic-inspired: Hierarchical multi-agent system.
Host guides debate toward productive outcomes, intervenes strategically.
"""
from typing import Dict, Any, List, Optional
from .debate_progress_tracker import DebateProgressTracker


class StrategicHostAgent:
    """
    Intelligent host that monitors debate and intervenes strategically
    
    Like a skilled facilitator in real debates:
    - Redirects when off-topic
    - Proposes conclusions when consensus reached
    - Seeks common ground when polarized
    - Calls for evidence when claims are unsubstantiated
    """
    
    def __init__(self, debate_id: str):
        self.debate_id = debate_id
        self.progress_tracker = DebateProgressTracker(debate_id)
    
    def should_intervene(self) -> Dict[str, Any]:
        """
        Decide if host should intervene and how
        
        Returns:
            {
                "should_intervene": bool,
                "action": str,  # "redirect", "conclude", "seek_common_ground", "call_for_evidence", "none"
                "message": str,
                "urgency": "low/medium/high"
            }
        """
        # Analyze current state
        progress = self.progress_tracker.analyze()
        
        # Decision tree for interventions
        
        # High priority: Repetition problem
        if progress['new_info_rate'] < 0.3 and progress['message_count'] > 5:
            return {
                "should_intervene": True,
                "action": "redirect",
                "message": self._generate_redirect_message(progress),
                "urgency": "high",
                "reason": f"Low new info rate: {progress['new_info_rate']}"
            }
        
        # High priority: Strong consensus, should conclude
        if (progress['consensus_level'] > 0.8 and
            progress['coverage_score'] > 0.7 and
            progress['message_count'] >= 10):
            return {
                "should_intervene": True,
                "action": "propose_conclusion",
                "message": self._generate_conclusion_message(progress),
                "urgency": "medium",
                "reason": f"High consensus ({progress['consensus_level']}) + good coverage"
            }
        
        # Medium priority: High polarization
        if progress['polarization'] > 0.8 and progress['message_count'] > 8:
            return {
                "should_intervene": True,
                "action": "seek_common_ground",
                "message": self._generate_common_ground_message(),
                "urgency": "medium",
                "reason": f"High polarization: {progress['polarization']}"
            }
        
        # Low priority: Poor coverage
        if (progress['coverage_score'] < 0.5 and
            progress['message_count'] > 6):
            return {
                "should_intervene": True,
                "action": "redirect_to_outcomes",
                "message": self._generate_coverage_message(progress),
                "urgency": "low",
                "reason": f"Low coverage: {progress['coverage_score']}"
            }
        
        # No intervention needed
        return {
            "should_intervene": False,
            "action": "none",
            "message": None,
            "urgency": "none",
            "reason": "Debate progressing well"
        }
    
    def _generate_redirect_message(self, progress: Dict) -> str:
        """Generate message to redirect away from repetition"""
        return (
            "I'm noticing we're starting to repeat similar points. "
            "Let's shift our focus. What perspectives haven't we explored yet? "
            "Or let's dive deeper into the implications of what's been said."
        )
    
    def _generate_conclusion_message(self, progress: Dict) -> str:
        """Generate message proposing conclusion"""
        consensus_pct = int(progress['consensus_level'] * 100)
        return (
            f"I'm seeing strong agreement emerging ({consensus_pct}% consensus). "
            "Should we move toward a conclusion? Or are there any final objections "
            "or concerns we should address first?"
        )
    
    def _generate_common_ground_message(self) -> str:
        """Generate message seeking common ground"""
        return (
            "We have strong disagreements here, which is valuable. "
            "But let's find our common ground: What do we ALL agree on? "
            "Let's build from there rather than further polarizing."
        )
    
    def _generate_coverage_message(self, progress: Dict) -> str:
        """Generate message about coverage gaps"""
        coverage_pct = int(progress['coverage_score'] * 100)
        return (
            f"We've explored about {coverage_pct}% of our intended topics. "
            "Let's make sure we address the remaining areas before concluding. "
            "What hasn't been discussed yet that's critical to our decision?"
        )
    
    def format_intervention(
        self,
        intervention: Dict[str, Any],
        debate_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Format intervention as an event to be inserted into debate
        
        Returns event structure ready for insertion
        """
        return {
            "type": "host_intervention",
            "sender_type": "host",
            "content": {
                "text": intervention['message'],
                "action": intervention['action'],
                "urgency": intervention['urgency'],
                "actor": "Strategic Host"
            }
        }


class HostPersonality:
    """
    Defines host's personality and intervention style
    
    Can be customized per workspace/user
    """
    
    STYLES = {
        "assertive": {
            "intervention_threshold": 0.3,  # Intervenes more often
            "tone": "direct",
            "examples": [
                "Let's get back on track.",
                "That's not moving us forward. Focus on X instead.",
                "Time to conclude. Here's what I'm hearing..."
            ]
        },
        "gentle": {
            "intervention_threshold": 0.7,  # Intervenes less often
            "tone": "suggestive",
            "examples": [
                "I'm wondering if we might explore...",
                "Perhaps we could consider...",
                "What if we looked at it from..."
            ]
        },
        "socratic": {
            "intervention_threshold": 0.5,
            "tone": "questioning",
            "examples": [
                "What assumptions are we making?",
                "Why do we believe X?",
                "What evidence would change your mind?"
            ]
        },
        "data_driven": {
            "intervention_threshold": 0.4,
            "tone": "analytical",
            "examples": [
                "The data shows...",
                "Looking at our metrics...",
                "Based on the progress so far..."
            ]
        }
    }
    
    def __init__(self, style: str = "gentle"):
        self.style = style if style in self.STYLES else "gentle"
        self.config = self.STYLES[self.style]
    
    def should_intervene_by_personality(self, calculated_urgency: float) -> bool:
        """
        Decide if this personality type would intervene given urgency
        
        Args:
            calculated_urgency: 0-1, how urgent the situation is
        
        Returns:
            True if this personality would intervene
        """
        return calculated_urgency >= self.config['intervention_threshold']
    
    def adapt_message(self, base_message: str) -> str:
        """Adapt message to match personality"""
        tone = self.config['tone']
        
        if tone == "direct":
            return base_message
        elif tone == "suggestive":
            return f"I'm noticing that {base_message.lower()}"
        elif tone == "questioning":
            return f"Should we consider: {base_message}?"
        elif tone == "analytical":
            return f"Based on the discussion metrics, {base_message.lower()}"
        
        return base_message
