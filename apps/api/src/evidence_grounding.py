"""
Evidence Grounding System - Force citations or mark opinions

Anthropic-inspired: Intellectual honesty. Separate facts from opinions.
Prevents LLM hallucination of "facts".
"""
import re
from typing import Dict, Any, List, Optional, Tuple


class EvidenceGroundingValidator:
    """
    Validates that factual claims are either:
    1. Cited with sources
    2. Marked as opinions/estimates
    3. Clearly hedged ("likely", "probably", "appears")
    """
    
    # Patterns that indicate factual claims
    FACTUAL_CLAIM_PATTERNS = [
        r'\b\d+%',  # Percentages
        r'\b\d+,?\d*\s+(people|voters|workers|members|users)',  # Numbers of people
        r'\b(has|have|had)\s+\d+',  # "has 15,000 workers"
        r'\b(according to|based on|data shows|studies show)',  # Citation indicators
        r'\b(fact|data|evidence|study|research|report|survey)',  # Fact-claiming words
    ]
    
    # Patterns that indicate proper hedging/opinions
    HEDGING_PATTERNS = [
        r'\b(likely|probably|possibly|may|might|could|appears|seems|suggests)\b',
        r'\b(in my view|I believe|I think|my opinion|arguably|potentially)\b',
        r'\b(Opinion:|Estimate:|Speculation:)\b',  # Explicit labels
        r'\[Opinion:.*?\]',  # Bracketed opinions
        r'\[Source:.*?\]',  # Bracketed sources
    ]
    
    def __init__(self):
        pass
    
    def validate(self, message: str, agent_name: str) -> Dict[str, Any]:
        """
        Validate that factual claims are properly grounded
        
        Returns:
            {
                "valid": bool,
                "violations": [{"claim": str, "issue": str, "suggestion": str}],
                "grounded_claims": int,
                "ungrounded_claims": int
            }
        """
        violations = []
        grounded_claims = 0
        ungrounded_claims = 0
        
        # Extract sentences
        sentences = self._split_sentences(message)
        
        for sentence in sentences:
            if self._is_factual_claim(sentence):
                if self._is_grounded(sentence):
                    grounded_claims += 1
                else:
                    ungrounded_claims += 1
                    violations.append({
                        "claim": sentence.strip(),
                        "issue": "Factual claim without citation or hedging",
                        "suggestion": f"Add [Source: ...] or rephrase as opinion: 'I believe {sentence.strip().lower()}'"
                    })
        
        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "grounded_claims": grounded_claims,
            "ungrounded_claims": ungrounded_claims,
            "grounding_rate": grounded_claims / (grounded_claims + ungrounded_claims) if (grounded_claims + ungrounded_claims) > 0 else 1.0
        }
    
    def suggest_improvements(self, message: str) -> str:
        """
        Automatically improve message by adding opinion markers
        """
        sentences = self._split_sentences(message)
        improved_sentences = []
        
        for sentence in sentences:
            if self._is_factual_claim(sentence) and not self._is_grounded(sentence):
                # Add opinion marker
                improved = f"{sentence.strip()} [Opinion: based on available information]"
                improved_sentences.append(improved)
            else:
                improved_sentences.append(sentence)
        
        return " ".join(improved_sentences)
    
    def _is_factual_claim(self, text: str) -> bool:
        """Check if text contains a factual claim"""
        text_lower = text.lower()
        
        # Check for factual indicators
        for pattern in self.FACTUAL_CLAIM_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        
        return False
    
    def _is_grounded(self, text: str) -> bool:
        """Check if claim is properly grounded"""
        text_lower = text.lower()
        
        # Check for hedging/opinion markers
        for pattern in self.HEDGING_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        
        return False
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Simple sentence splitter
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]


class EvidenceCitationHelper:
    """
    Helps agents cite sources properly
    
    In production, this could connect to:
    - Web search APIs
    - Knowledge bases
    - Fact-checking services
    """
    
    def __init__(self):
        pass
    
    def format_citation(self, claim: str, source: str, year: Optional[int] = None) -> str:
        """Format a proper citation"""
        if year:
            return f"{claim} [Source: {source}, {year}]"
        else:
            return f"{claim} [Source: {source}]"
    
    def suggest_sources(self, claim: str) -> List[str]:
        """Suggest where to find sources for a claim"""
        suggestions = []
        
        claim_lower = claim.lower()
        
        if 'election' in claim_lower or 'vote' in claim_lower:
            suggestions.append("Election Commission data")
            suggestions.append("Recent polling data")
        
        if 'data' in claim_lower or 'statistics' in claim_lower:
            suggestions.append("Government statistical databases")
            suggestions.append("Academic research")
        
        if 'company' in claim_lower or 'business' in claim_lower:
            suggestions.append("Company financial reports")
            suggestions.append("Industry analysis")
        
        if not suggestions:
            suggestions.append("Academic sources")
            suggestions.append("Industry reports")
            suggestions.append("News from reputable outlets")
        
        return suggestions
