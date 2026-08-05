"""
Constitutional Validator - Stage 3 of Constitutional AI Pipeline

Anthropic's Constitutional AI approach: Hard-coded rules that override
LLM outputs to ensure consistency and prevent flip-flopping.

This is the "safety layer" that catches bad behavior.
"""
import re
from typing import Tuple, Dict, Any, Optional, List



# Reused from the transcript quality harness so the live guard and the offline
# harness agree on what counts as substance.
from .services.transcript_quality import _content_words

# A locator points INTO a specific document: a page, a numbered section, a
# table, a figure. It is only checkable if a document was actually supplied.
# Deliberately does NOT match external literature — "(McKay et al., 2018)",
# "Smith 2019" — which a reviewer may legitimately know and cite from memory.
# Kept flag-free so it can be embedded in a larger pattern; inline (?xi) would
# be a global flag in the wrong position there.
#
# The page branch is bounded to 1-3 digits on purpose. Case-insensitively,
# "p.\s*\d+" matches the author initial in "(Jones, P. 2019)",
# "Peterson, A. P. 2019" and "See Smith, P. 2019" — all legitimate external
# references, all of which would have forced a regeneration. A year is four
# digits; a page almost never is.
_LOCATOR_BODY = r"""
    \b(?:pp?\.\s*\d{1,3}(?!\d)           # p. 12 / pp. 3-5 — see note below
       |pages?\s+\d{1,3}(?!\d)            # page 15
       |section\s+\d+(?:\.\d+)*           # Section 2.1
       |table\s+\d+(?:\.\d+)*             # Table 3
       |figure\s+\d+(?:\.\d+)*            # Figure 2
       |appendix\s+[A-Z0-9]\b               # Appendix B
       |(?:methodology|methods|results|discussion|introduction
         |conclusion|abstract|literature\s+review)\s+section
    )
"""

_DOC_LOCATOR = re.compile(_LOCATOR_BODY, re.IGNORECASE | re.VERBOSE)

# The same locator wrapped in its own bracket — "(p. 12)", "(Methods section,
# p. 5)" — which must be removed whole rather than leaving "()" behind.
_PAREN_LOCATOR = re.compile(
    r"\([^()]{0,80}?" + _LOCATOR_BODY + r"[^()]{0,80}?\)",
    re.IGNORECASE | re.VERBOSE,
)

_ADJACENT = re.compile(r"[a-z]{4,}")


def _adjacent_pairs(text: str) -> set:
    """Adjacent content-word pairs — a cheap stand-in for phrasing."""
    words = [w for w in _ADJACENT.findall(text.lower())]
    return {f"{a} {b}" for a, b in zip(words, words[1:])}


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
        recent_other_messages: Optional[List[str]] = None,
        has_materials: bool = True
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
        # Gated on am_i_repeating == "repeat" this only ever fired when the
        # model confessed, which it does not do when it is paraphrasing. The
        # mechanical overlap check inside was unreachable. Run it every turn.
        if recent_other_messages:
            repetition_violation = self._check_repetition(
                message,
                recent_other_messages,
                reasoning
            )
            if repetition_violation:
                violations.append(repetition_violation)
        
        # Rule 4.5: Citing a document that was never submitted
        fabricated_citation = self._check_fabricated_citation(
            message,
            has_materials
        )
        if fabricated_citation:
            violations.append(fabricated_citation)

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
        
        # Determine severity.
        # NOTE: only "critical" affects `valid`, so a "high" violation is
        # recorded and then ignored — no regeneration, and the caller logs
        # "validation passed". no_repetition is critical for that reason:
        # repetition is exactly what the constrained-regeneration path in
        # turn_orchestrator was written to handle. The other "high" rules
        # (persona authenticity, role consistency, engagement) are still
        # advisory-only by this same mechanism.
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
                "severity": "critical",
                "details": f"Agent is repeating what others said: '{reasoning.get('what_others_said', 'N/A')[:100]}...'. Must add NEW information or disagree."
            }
        
        # Mechanical overlap check. Three things the old version got wrong:
        #   - it divided by the new message's own word count, so padding a
        #     restatement with filler dropped the ratio below the threshold;
        #   - it counted "should", "however", "paper" — words every review
        #     uses — as shared substance;
        #   - it only looked at the last 2 messages, so a reviewer could
        #     restate whatever was said three turns ago.
        message_words = _content_words(message)
        if not message_words:
            return None

        message_pairs = _adjacent_pairs(message)

        for other_msg in recent_other_messages[-6:]:
            other_words = _content_words(other_msg)
            if not other_words:
                continue

            # Containment against the shorter side: a long restatement of a
            # short point is still a restatement.
            shared = len(message_words & other_words)
            containment = shared / min(len(message_words), len(other_words))

            # 0.35 is calibrated, not guessed: on a live six-turn transcript
            # where every reviewer restated the same sampling critique, the
            # restatements scored 0.38-0.68 while three genuinely new points
            # (reliability, preregistration, follow-up window) scored 0.00-0.07
            # against the same transcript. 0.35 sits in that gap.
            if containment > 0.35:
                return {
                    "rule": "no_repetition",
                    "severity": "critical",
                    "details": (
                        f"Message shares {containment*100:.0f}% of its substantive "
                        f"vocabulary with a recent message. Must add a unique perspective."
                    )
                }

            # Reused phrasing: same two content words side by side. Catches a
            # lightly-reworded restatement that the word-set measure misses
            # because the padding pushed containment down.
            other_pairs = _adjacent_pairs(other_msg)
            if message_pairs and other_pairs:
                pair_overlap = len(message_pairs & other_pairs) / min(len(message_pairs), len(other_pairs))
                if pair_overlap > 0.25:
                    return {
                        "rule": "no_repetition",
                        "severity": "critical",
                        "details": (
                            f"Message reuses {pair_overlap*100:.0f}% of the phrasing of a "
                            f"recent message. Must add a unique perspective."
                        )
                    }

        return None
    
    @staticmethod
    def strip_fabricated_locators(message: str) -> Tuple[str, int]:
        """Replace invented document locators with the codebase's own marker.

        Last resort, used only when a constrained regeneration has ALREADY been
        tried and the model cited a document again. Regeneration was previously
        unverified: the retry's output went straight into the transcript, so
        "Figure 1" and "Table 3" survived a firing guard in a live adversarial
        run. Publishing an invented locator is publishing a false statement
        about someone's work, so when the model will not stop, say plainly that
        there was no source rather than repeating its claim.

        '[source not provided]' is the marker the material-grounding prompt
        already tells agents to use, and transcript_quality counts it as a
        placeholder — so it stays visible in quality reporting instead of
        looking like a clean turn.
        """
        marker = "[source not provided]"
        text, paren_hits = _PAREN_LOCATOR.subn(marker, message)
        text, bare_hits = _DOC_LOCATOR.subn(marker, text)
        # Two locators in one clause ("the methodology section (p. 12)") leave
        # the marker twice in a row; collapse those and tidy the spacing.
        text = re.sub(r"(?:\[source not provided\][\s,]*){2,}", marker + " ", text)
        text = re.sub(r"\s{2,}", " ", text)
        text = re.sub(r"\s+([,.;:])", r"\1", text)
        return text.strip(), paren_hits + bare_hits

    def _check_fabricated_citation(
        self,
        message: str,
        has_materials: bool
    ) -> Optional[Dict[str, Any]]:
        """Catch citations of a document that was never submitted.

        Only fires when NO material was supplied to this session, where the
        judgement is exact rather than probabilistic: if the reviewer was
        handed no document, every page number and section reference in their
        output is invented. Measured on three live runs with no upload, the
        panel produced 33 such locators across 18 turns — "(p. 12)",
        "Section 2.1, Participant Selection", "on page 15" — and then all
        anchored on the same fabricated detail.

        When a document DOES exist this stays silent. Verifying a cited page
        against the real one is not possible here: 391 of 398 material chunks
        in the live database carry no page_num at all, so a page check would
        reject almost every legitimate citation. Grounding for that case is
        provenance.ground_message, which matches text rather than locators.
        """
        if has_materials:
            return None

        found = []
        for m in _DOC_LOCATOR.finditer(message):
            token = " ".join(m.group(0).split())
            if token.lower() not in (f.lower() for f in found):
                found.append(token)

        if not found:
            return None

        shown = ", ".join(f'"{f}"' for f in found[:4])
        return {
            "rule": "no_fabricated_citation",
            "severity": "critical",
            "details": (
                f"No document was submitted to this session, but the message "
                f"cites {shown}. There is nothing those refer to. State the gap "
                f"instead — \"the problem statement does not say whether...\"."
            ),
        }

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
