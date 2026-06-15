"""
Debate Progress Tracker - Real-time debate health monitoring

Anthropic-inspired: Measure what matters. Track if the debate is actually
making progress toward desired outcomes.
"""
from typing import Dict, Any, List, Optional
from .database import get_db_connection, get_cursor


class DebateProgressTracker:
    """
    Tracks debate health and progress toward outcomes
    
    Provides actionable intelligence:
    - Are we covering all desired outcomes?
    - Are we adding new information or repeating?
    - Is there consensus or polarization?
    - Should we conclude or continue?
    """
    
    def __init__(self, debate_id: str):
        self.debate_id = debate_id
    
    def analyze(self) -> Dict[str, Any]:
        """
        Analyze current debate state
        
        Returns:
            {
                "coverage_score": 0.0-1.0,
                "depth_score": 0.0-1.0,
                "new_info_rate": 0.0-1.0,
                "consensus_level": 0.0-1.0,
                "polarization": 0.0-1.0,
                "action_items": [str],
                "should_conclude": bool,
                "health": "poor/fair/good/excellent"
            }
        """
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            
            # Get debate info
            cursor.execute("""
                SELECT title, description, policy_config
                FROM debates
                WHERE debate_id = %s
            """, (self.debate_id,))
            debate = cursor.fetchone()
            
            if not debate:
                return self._empty_analysis()
            
            policy_config = debate['policy_config'] or {}
            desired_outcomes = policy_config.get('desired_outcomes', [])
            
            # Get all agent messages
            cursor.execute("""
                SELECT content
                FROM events
                WHERE debate_id = %s AND event_type = 'agent_message'
                ORDER BY sequence_number ASC
            """, (self.debate_id,))
            
            messages = [row['content'] for row in cursor.fetchall()]
            
            if len(messages) < 2:
                return self._early_debate_analysis(desired_outcomes)
            
            # Calculate metrics
            coverage_score = self._calculate_coverage(messages, desired_outcomes)
            depth_score = self._calculate_depth(messages, desired_outcomes)
            new_info_rate = self._calculate_new_info_rate(messages)
            consensus_level = self._calculate_consensus(messages)
            polarization = self._calculate_polarization(messages)
            
            # Generate action items
            action_items = self._generate_action_items(
                coverage_score,
                depth_score,
                new_info_rate,
                consensus_level,
                desired_outcomes,
                len(messages)
            )
            
            # Should conclude?
            should_conclude = (
                coverage_score > 0.8 and
                consensus_level > 0.7 and
                len(messages) >= 10
            )
            
            # Overall health
            avg_score = (coverage_score + depth_score + new_info_rate) / 3
            if avg_score >= 0.8:
                health = "excellent"
            elif avg_score >= 0.6:
                health = "good"
            elif avg_score >= 0.4:
                health = "fair"
            else:
                health = "poor"
            
            cursor.close()
            
            return {
                "coverage_score": round(coverage_score, 2),
                "depth_score": round(depth_score, 2),
                "new_info_rate": round(new_info_rate, 2),
                "consensus_level": round(consensus_level, 2),
                "polarization": round(polarization, 2),
                "action_items": action_items,
                "should_conclude": should_conclude,
                "health": health,
                "message_count": len(messages),
                "outcomes_total": len(desired_outcomes)
            }
    
    def _calculate_coverage(self, messages: List[Dict], outcomes: List[str]) -> float:
        """How many desired outcomes have been discussed?"""
        if not outcomes:
            return 1.0  # No outcomes defined = full coverage
        
        covered = 0
        for outcome in outcomes:
            # Simple keyword matching (in production, use semantic similarity)
            outcome_keywords = set(outcome.lower().split())
            
            for msg in messages:
                text = msg.get('text', '').lower()
                if any(keyword in text for keyword in outcome_keywords if len(keyword) > 4):
                    covered += 1
                    break
        
        return covered / len(outcomes) if outcomes else 1.0
    
    def _calculate_depth(self, messages: List[Dict], outcomes: List[str]) -> float:
        """How deeply have we explored each outcome?"""
        if not outcomes or len(messages) < 3:
            return 0.5
        
        # Measure: Do we have 3+ perspectives on each outcome?
        depth_scores = []
        for outcome in outcomes:
            outcome_keywords = set(outcome.lower().split())
            perspectives = 0
            
            agents_discussed = set()
            for msg in messages:
                text = msg.get('text', '').lower()
                agent = msg.get('agent_name')
                
                if any(keyword in text for keyword in outcome_keywords if len(keyword) > 4):
                    if agent not in agents_discussed:
                        perspectives += 1
                        agents_discussed.add(agent)
            
            # Score: 0 = no discussion, 1 = 3+ agents discussed it
            depth_scores.append(min(perspectives / 3.0, 1.0))
        
        return sum(depth_scores) / len(depth_scores) if depth_scores else 0.5
    
    def _calculate_new_info_rate(self, messages: List[Dict]) -> float:
        """What % of recent messages add new information?"""
        if len(messages) < 3:
            return 1.0
        
        # Check last 5 messages
        recent = messages[-5:]
        unique_count = 0
        
        for i, msg in enumerate(recent):
            text = msg.get('text', '')
            words = set(w.lower() for w in text.split() if len(w) > 4)
            
            # Compare with previous messages in recent window
            is_unique = True
            for prev_msg in recent[:i]:
                prev_words = set(w.lower() for w in prev_msg.get('text', '').split() if len(w) > 4)
                overlap = len(words & prev_words)
                if overlap / len(words) > 0.6 if words else False:
                    is_unique = False
                    break
            
            if is_unique:
                unique_count += 1
        
        return unique_count / len(recent)
    
    def _calculate_consensus(self, messages: List[Dict]) -> float:
        """How much agreement is there?"""
        if len(messages) < 3:
            return 0.0
        
        # Simple heuristic: count agreement vs disagreement phrases
        agreement_phrases = ['agree', 'correct', 'right', 'yes', 'exactly', 'same']
        disagreement_phrases = ['disagree', 'wrong', 'incorrect', 'no', 'but', 'however']
        
        agree_count = 0
        disagree_count = 0
        
        for msg in messages:
            text = msg.get('text', '').lower()
            if any(phrase in text for phrase in agreement_phrases):
                agree_count += 1
            if any(phrase in text for phrase in disagreement_phrases):
                disagree_count += 1
        
        total = agree_count + disagree_count
        return agree_count / total if total > 0 else 0.5
    
    def _calculate_polarization(self, messages: List[Dict]) -> float:
        """How polarized is the debate?"""
        if len(messages) < 3:
            return 0.0
        
        # Inverse of consensus (high consensus = low polarization)
        consensus = self._calculate_consensus(messages)
        return 1.0 - consensus
    
    def _generate_action_items(
        self,
        coverage: float,
        depth: float,
        new_info_rate: float,
        consensus: float,
        outcomes: List[str],
        message_count: int
    ) -> List[str]:
        """Generate actionable recommendations"""
        items = []
        
        # Coverage issues
        if coverage < 0.7 and outcomes:
            items.append(f"⚠️ Only {int(coverage*100)}% of outcomes covered. Ask agents to address missing topics.")
        
        # Depth issues
        if depth < 0.5 and message_count > 5:
            items.append("💭 Shallow discussion. Encourage agents to provide more detailed analysis.")
        
        # Repetition issues
        if new_info_rate < 0.4:
            items.append("🔄 High repetition detected. Consider redirecting or introducing new angle.")
        
        # Consensus opportunities
        if consensus > 0.8 and message_count > 8:
            items.append("✅ High consensus reached. Consider concluding or proposing a vote.")
        
        # Polarization issues
        if consensus < 0.3 and message_count > 8:
            items.append("⚡ High polarization. Seek common ground or ask for evidence.")
        
        # No issues
        if not items:
            items.append("✨ Debate is progressing well. Continue.")
        
        return items
    
    def _empty_analysis(self) -> Dict[str, Any]:
        """Return empty analysis for non-existent debate"""
        return {
            "coverage_score": 0.0,
            "depth_score": 0.0,
            "new_info_rate": 0.0,
            "consensus_level": 0.0,
            "polarization": 0.0,
            "action_items": ["⚠️ Debate not found"],
            "should_conclude": False,
            "health": "poor",
            "message_count": 0,
            "outcomes_total": 0
        }
    
    def _early_debate_analysis(self, outcomes: List[str]) -> Dict[str, Any]:
        """Analysis for debates with <2 messages"""
        return {
            "coverage_score": 0.0,
            "depth_score": 0.0,
            "new_info_rate": 1.0,
            "consensus_level": 0.0,
            "polarization": 0.0,
            "action_items": ["🚀 Debate just started. Let agents develop their positions."],
            "should_conclude": False,
            "health": "good",
            "message_count": 0,
            "outcomes_total": len(outcomes)
        }
