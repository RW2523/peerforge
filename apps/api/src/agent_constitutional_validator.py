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


# A page inside a parenthetical that also carries an author-year is a
# reference to OTHER literature — "(Smith, 2019, p. 44)", "(see Cohen 1988,
# pp. 20-25)". A reviewer may legitimately know that page from memory; it is
# not a claim about the document under review, which is what the fabricated-
# citation rule exists to catch. A regex cannot tell which document a bare
# "p. 44" belongs to, but a neighbouring four-digit year is strong evidence
# that this one belongs to somebody else's.
_EXTERNAL_REF = re.compile(
    r"\([^()]{0,120}?\b(?:1[89]|20)\d{2}\b[^()]{0,120}?\)"
)


# Complaining that no document was supplied is not a review finding. The
# reader set the session up and already knows. When the no-document prompt
# branch was added, five of six turns opened with "the absence of submitted
# documentation significantly undermines..." — the panel reviewing its own
# inputs instead of the research. Naming a SPECIFIC missing detail ("the
# design does not say whether allocation was concealed") is useful and is
# deliberately not matched here.
_SESSION_META = re.compile(
    r"(?ix)"
    r"\b(?:absence|lack|without|no|missing|failure\s+to\s+(?:provide|submit))\b"
    r"[^.]{0,40}?"
    r"\b(?:submitted|provided|supplied|available|accompanying)?\s*"
    r"(?:document|documentation|manuscript|materials?|paper|submission)s?\b"
)


def _external_ref_spans(text: str):
    """Character ranges covered by an author-year parenthetical."""
    return [(m.start(), m.end()) for m in _EXTERNAL_REF.finditer(text)]


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
        has_materials: bool = True,
        absent_locators: Optional[List[Dict[str, Any]]] = None
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

        # Rule 4.55: Reviewing the session setup instead of the work
        session_meta = self._check_session_meta(message, has_materials)
        if session_meta:
            violations.append(session_meta)

        # Rule 4.6: Citing part of a document that does not exist in it
        contradicted = self._check_contradicted_citation(absent_locators)
        if contradicted:
            violations.append(contradicted)

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
                active_participants,
                anyone_has_spoken=bool(recent_other_messages)
            )
            if engagement_violation:
                violations.append(engagement_violation)
        
        # Determine severity. Only "critical" affects `valid`, so anything
        # below it is recorded and then ignored — no regeneration, and the
        # caller logs a pass.
        #
        # Which severity a rule gets was decided by measuring it against 111
        # real turns rather than by how bad it sounds:
        #
        #   no_self_contradiction    0%   -> critical
        #   role_consistency         0%   -> critical
        #   persona_authenticity     1%   -> critical
        #   must_address_others     44%   -> stays advisory
        #
        # must_address_others is not escalated on purpose. At 44% it would
        # force a regeneration on nearly half of all turns, and inspection of
        # those turns shows they are fine: they open with the reviewer's own
        # substantive point, which is exactly what the round-1 instruction in
        # agent_response_generator tells them to do. Escalating it would make
        # two parts of the system fight each other. It stays a signal, not a
        # verdict.
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
                    "severity": "critical",
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
                    "severity": "critical",
                    "details": f"{agent_role} should disagree but message is too agreeable"
                }
        
        # Visionary should be forward-looking
        if "visionary" in role_lower:
            future_phrases = ["future", "will", "trend", "emerging", "next", "tomorrow", "ahead"]
            has_future_focus = any(phrase in message_lower for phrase in future_phrases)
            
            if not has_future_focus:
                return {
                    "rule": "role_consistency",
                    "severity": "critical",
                    "details": "Visionary should focus on future implications"
                }
        
        return None
    
    def _check_engagement(
        self,
        message: str,
        active_participants: List[str],
        anyone_has_spoken: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Check whether the agent engages with what others have said.

        Measured against 111 real turns, the original fired on 79% of them —
        a rule that objects to four turns in five is describing its own
        thresholds, not the output. Two causes:

          - it demanded an "@name" or one of eight hard-coded phrases, so
            "Prof. Adeyemi's concern about sampling overlooks..." — engagement
            by name, in the ordinary register of a review — counted as none;
          - it fired on the FIRST speaker of a debate, who has nobody to
            engage with. 24 of the 88 hits were that.

        Naming another reviewer at all now counts, which is what the rule was
        always trying to detect.
        """
        if not anyone_has_spoken or not active_participants:
            return None

        lowered = message.lower()

        # An @mention, or the participant's name used in the ordinary way.
        def _names_of(participant: str):
            parts = [p for p in participant.replace('"', "").split() if len(p) > 2]
            return {participant.lower(), *(p.lower() for p in parts)}

        has_mention = False
        for name in active_participants:
            if f"@{name}" in message or f'@"{name}"' in message:
                has_mention = True
                break
            # Surname alone is how reviewers actually refer to each other.
            if any(len(n) > 3 and n in lowered for n in _names_of(name)):
                has_mention = True
                break

        reference_phrases = (
            "you said", "you mentioned", "your point", "as you noted",
            "building on", "responding to", "agree with", "disagree with",
            "as noted by", "raised by", "pointed out", "argues that",
            "the concern about", "the point about", "others have",
            "my colleague", "the panel", "earlier reviewer", "previous reviewer",
            "contrary to", "in response to", "counter to",
        )
        has_reference = any(phrase in lowered for phrase in reference_phrases)

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

        # An author-year parenthetical is somebody else's paper, not the
        # submitted one. Detection already exempts these; the strip has to as
        # well, or the backstop rewrites "(Smith, 2019, p. 44)" — a reference
        # the reviewer may legitimately know — into a placeholder.
        external = _external_ref_spans(message)

        def _sub_outside(pattern, source):
            spans = _external_ref_spans(source)
            out, last, hits = [], 0, 0
            for m in pattern.finditer(source):
                if any(a <= m.start() and m.end() <= b for a, b in spans):
                    continue
                out.append(source[last:m.start()])
                out.append(marker)
                last = m.end()
                hits += 1
            out.append(source[last:])
            return "".join(out), hits

        text, paren_hits = _sub_outside(_PAREN_LOCATOR, message)
        text, bare_hits = _sub_outside(_DOC_LOCATOR, text)
        # Two locators in one clause ("the methodology section (p. 12)") leave
        # the marker twice in a row; collapse those and tidy the spacing.
        text = re.sub(r"(?:\[source not provided\][\s,]*){2,}", marker + " ", text)
        text = re.sub(r"\s{2,}", " ", text)
        text = re.sub(r"\s+([,.;:])", r"\1", text)
        return text.strip(), paren_hits + bare_hits

    @staticmethod
    def strip_contradicted_locators(
        message: str,
        absent_locators: Optional[List[Dict[str, Any]]]
    ) -> Tuple[str, int]:
        """Mark the specific citations the document contradicts.

        Targeted, unlike strip_fabricated_locators: a session WITH a document
        has legitimate citations too, and "Section 2.1" must survive untouched
        while "Section 2.3" is marked. Only the identifiers the index reported
        as absent are replaced.

        Needed for the same reason as the no-materials backstop — a
        regenerated message is never re-validated, so without this the rule
        fires, the retry cites the same missing section again, and it is
        published anyway. Measured: 11 contradicted citations reached the
        transcript across four turns while the rule fired on every one.
        """
        if not absent_locators:
            return message, 0

        text = message
        replaced = 0
        for item in absent_locators:
            family = re.escape(item["family"])
            ident = re.escape(item["cited"])
            # Bound the match so "Section 3.4" does not fire inside "Section
            # 3.45", while still matching "Section 3.4." at the end of a
            # sentence. (?![\d.]) rejected that trailing full stop and let two
            # contradicted citations through a live run.
            pattern = re.compile(
                rf"\b{family}s?\s+{ident}(?!\d)(?!\.\d)",
                re.IGNORECASE,
            )
            text, n = pattern.subn("[not in the submitted document]", text)
            replaced += n

        text = re.sub(r"(?:\[not in the submitted document\][\s,]*){2,}",
                      "[not in the submitted document] ", text)
        text = re.sub(r"\s{2,}", " ", text)
        text = re.sub(r"\s+([,.;:])", r"\1", text)
        return text.strip(), replaced

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

        external = _external_ref_spans(message)

        found = []
        for m in _DOC_LOCATOR.finditer(message):
            # Skip a locator sitting inside an author-year reference.
            if any(start <= m.start() and m.end() <= end for start, end in external):
                continue
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

    def _check_session_meta(
        self,
        message: str,
        has_materials: bool
    ) -> Optional[Dict[str, Any]]:
        """Catch a turn that reviews the session setup instead of the work.

        Only meaningful when nothing was submitted — with a document in hand,
        "the materials lack a power analysis" is a real finding about the
        work. Without one, "the absence of submitted documentation undermines
        this review" tells the reader something they already know and costs
        them a turn of actual review.

        Scoped to the OPENING, because a passing mention mid-argument is
        usually fine; it is leading with it that replaces the review.
        """
        if has_materials:
            return None

        opening = message[:200]
        m = _SESSION_META.search(opening)
        if not m:
            return None

        return {
            "rule": "no_session_meta_commentary",
            "severity": "critical",
            "details": (
                f"The turn opens by complaining that no document was supplied "
                f"(\"{m.group(0).strip()}\"). That is not a review finding — "
                f"review the research described in the problem statement, and "
                f"name specific missing details only where they block a "
                f"specific judgement."
            ),
        }

    def _check_contradicted_citation(
        self,
        absent_locators: Optional[List[Dict[str, Any]]]
    ) -> Optional[Dict[str, Any]]:
        """Catch a citation the submitted document contradicts.

        The no-materials rule cannot see this one: a document DOES exist, so
        every locator in the message is plausible. Observed live — a reviewer
        cited "Section 2.3" of a paper whose sections are 1, 2, 2.1, 2.2, 3
        and 4.

        The verdict is computed in services.locator_index and passed in, so
        this class stays free of database access. Only the "absent" verdict
        reaches here: a locator whose FAMILY exists in the document but whose
        specific member does not. A document with no sections at all yields
        "unverifiable" and never gets this far, because extraction losing a
        PDF's headings must not read as the reviewer lying.
        """
        if not absent_locators:
            return None

        parts = []
        for item in absent_locators[:3]:
            present = ", ".join(item["present"])
            # Only name what the document explicitly labels. Listing an empty
            # or noisy set would invite the retry to cite whatever it saw.
            parts.append(
                f"{item['family']} {item['cited']}"
                + (f" (it has: {present})" if present else "")
            )
        return {
            "rule": "no_contradicted_citation",
            "severity": "critical",
            "details": (
                "The submitted document does not contain " + "; ".join(parts) +
                ". Cite only what is actually there, or say the document does "
                "not address the point."
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
                "severity": "critical",
                "details": f"Message uses generic phrases that any agent could say: {', '.join(found_generic_phrases)}. Must use unique character voice for {agent_name} ({agent_role})."
            }
        
        # Check for "agreement then but" pattern
        agreement_but_pattern = r"(absolutely|definitely|certainly|i agree|you\'re right)[^.!?]*(\.|,)\s*(but|however|though|although)"
        if re.search(agreement_but_pattern, message_lower, re.IGNORECASE):
            return {
                "rule": "persona_authenticity",
                "severity": "critical",
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
