"""
Agent Response Generator — Stage 2 of the Constitutional AI Pipeline.

Generates the actual debate/review message from the Stage 1 reasoning output.
Each reviewer role produces a role-specific structured response rather than
a generic reply so that reviewers provide complementary, not identical, analyses.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .openrouter_client import OpenRouterClient


# ── Role-specific response schemas ──────────────────────────────────────────
# Each schema defines what a reviewer in that role MUST address.
# This prevents different roles from producing effectively identical evaluations.

_ROLE_SCHEMA: Dict[str, Dict[str, str]] = {
    "advisor": {
        "dimensions":      "Research alignment, feasibility, scope, overall contribution",
        "strengths":       "Whether the work achieves its stated goals; originality of the research direction",
        "weaknesses":      "Scope creep, misalignment with stated research questions, feasibility concerns",
        "recommendations": "High-level changes to sharpen the contribution or tighten the scope",
        "evidence_req":    "Reference specific sections, research questions, or objectives from submitted materials",
    },
    "methodology professor": {
        "dimensions":      "Research design, baselines, controls, validity threats, statistical rigour, reproducibility",
        "strengths":       "Sound experimental design, appropriate controls, reproducible procedures",
        "weaknesses":      "Missing baselines, confounds, statistical errors, lack of ablation studies",
        "recommendations": "Specific additional experiments, corrected statistical tests, or clearer protocol descriptions",
        "evidence_req":    "Cite specific methods sections, tables, equations, or experimental procedures",
    },
    "domain expert": {
        "dimensions":      "Domain correctness, novelty within the field, related-work coverage, technical contribution",
        "strengths":       "Genuine technical advance, correct use of domain terminology and methods",
        "weaknesses":      "Missing related work, overclaimed novelty, incorrect domain assumptions",
        "recommendations": "Specific missing citations, comparison with state-of-the-art, clarification of contributions",
        "evidence_req":    "Reference specific related papers, benchmarks, or domain-standard practices",
    },
    "skeptical reviewer": {
        "dimensions":      "Claim validity, logical consistency, evidence sufficiency, generalisation limits",
        "strengths":       "Claims that are well-supported and hedged appropriately",
        "weaknesses":      "Over-generalised conclusions, unsupported assumptions, circular reasoning",
        "recommendations": "Specific experiments or data needed to validate disputed claims",
        "evidence_req":    "Quote specific claims from the paper and explain exactly why evidence is insufficient",
    },
    "friendly professor": {
        "dimensions":      "Clarity, communication quality, accessibility, terminological precision",
        "strengths":       "Clear exposition, well-structured arguments, good use of examples",
        "weaknesses":      "Jargon overload, undefined terms, confusing structure, poor figure captions",
        "recommendations": "Specific rewrites, additional explanations, or restructuring suggestions",
        "evidence_req":    "Point to specific sentences, figures, or sections that need clarification",
    },
    "external examiner": {
        "dimensions":      "Review readiness, depth of understanding, ability to justify design choices",
        "strengths":       "Strong justification for design decisions, awareness of alternatives",
        "weaknesses":      "Inability to justify choices, unresolved panel challenges, shallow understanding",
        "recommendations": "Preparation areas for the review, unresolved questions the panel will raise",
        "evidence_req":    "Cite specific design choices, parameter settings, or architectural decisions from the work",
    },
}

_DEFAULT_SCHEMA = {
    "dimensions":      "Academic quality, contribution, rigor",
    "strengths":       "Genuine strengths directly supported by the submitted materials",
    "weaknesses":      "Specific weaknesses with evidence from submitted materials",
    "recommendations": "Actionable, specific recommendations for the authors",
    "evidence_req":    "Every claim must cite a specific section, figure, or result from the submitted work",
}


def _get_schema(role_description: str) -> Dict[str, str]:
    """Match the closest role schema from the role description string."""
    desc = role_description.lower()
    # "Independent Reviewer" is the display name for the external-examiner lane;
    # match it before the generic word loop so "reviewer" doesn't hit the skeptical schema.
    if "independent" in desc or "external" in desc or "examiner" in desc:
        return _ROLE_SCHEMA["external examiner"]
    for key, schema in _ROLE_SCHEMA.items():
        if any(word in desc for word in key.split()):
            return schema
    return _DEFAULT_SCHEMA


def _round_instruction(current_round: int, max_rounds: int) -> str:
    """Return the structural requirement for this round."""
    if max_rounds < 2:
        return "Evaluate the submission directly from your reviewer perspective. Cite specific evidence."

    if current_round == 1:
        return (
            "ROUND 1 — INDEPENDENT EVALUATION: "
            "Assess the submission from your reviewer lens. "
            "Do NOT reference what other reviewers said yet (they may not have spoken). "
            "State your most important strength, your most critical weakness, "
            "and one specific recommendation. Cite evidence from the submitted materials."
        )
    elif current_round == max_rounds:
        return (
            f"ROUND {current_round} — FINAL POSITION: "
            "State your definitive recommendation (Accept / Minor Revision / Major Revision / Reject). "
            "Address at least one unresolved concern from earlier discussion. "
            "Justify your decision with evidence from the materials and the debate. "
            "Be decisive — this is your last contribution."
        )
    else:
        return (
            f"ROUND {current_round} — CHALLENGE AND ENGAGE: "
            "You MUST challenge, rebut, or meaningfully qualify at least one specific claim "
            "made by another reviewer. Name them directly (@ExactName). "
            "Explain exactly what evidence or reasoning contradicts their point. "
            "Then advance your own analysis to a new aspect not yet discussed."
        )


class AgentResponseGenerator:
    """
    Stage 2: Generate the debate/review message based on Stage 1 reasoning.
    """

    def __init__(self, openrouter_api_key: str):
        self.client = OpenRouterClient(openrouter_api_key)

    def generate_response(
        self,
        agent_name: str,
        agent_role_description: str,
        reasoning: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        debate_context: Dict[str, Any],
        turn_info: Dict[str, Any],
        debate_id: Optional[str] = None,
        material_context: Optional[str] = None,
        valid_participant_names: Optional[List[str]] = None,
    ) -> str:
        """
        Generate the debate/review message.

        Args:
            material_context:        Structured string of source materials.
            valid_participant_names:  Exact participant names — only these may be @mentioned.
        """
        schema = _get_schema(agent_role_description)
        current_round = turn_info.get("current_round", 1)
        max_rounds = turn_info.get("max_rounds", 1)

        system_prompt = self._build_system_prompt(
            agent_name=agent_name,
            role_description=agent_role_description,
            reasoning=reasoning,
            turn_info=turn_info,
            schema=schema,
            current_round=current_round,
            max_rounds=max_rounds,
            valid_participant_names=valid_participant_names or [],
        )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": self._format_debate_context(debate_context)},
        ]

        # Inject source materials for grounding
        if material_context:
            messages.append({
                "role": "system",
                "content": (
                    "SOURCE MATERIALS — ground every evaluative claim in these documents:\n\n"
                    + material_context
                ),
            })

        messages.extend(conversation_history)

        # Inject reasoning as a final instruction
        key_points_str = "; ".join(reasoning.get("key_points", []))
        unique = reasoning.get("unique_contribution", "raise a fresh concern")
        messages.append({
            "role": "system",
            "content": (
                f"Your internal reasoning summary:\n"
                f"  Stance: {reasoning.get('current_stance', '')}\n"
                f"  Confidence: {reasoning.get('confidence', '')}\n"
                f"  Unique contribution this turn: {unique}\n"
                f"  Key points: {key_points_str}\n\n"
                f"{_round_instruction(current_round, max_rounds)}\n\n"
                "Generate your review message now. "
                "Do NOT start with filler phrases. Open with your substantive point."
            ),
        })

        try:
            response = self.client.chat_completion(
                model="openai/gpt-4o-mini",
                messages=messages,
                temperature=0.8,
                max_tokens=900,
                _debate_id=debate_id,
                _stage="response_generation",
                _participant=agent_name,
            )
            return response["content"].strip()
        except Exception as exc:
            print(f"    [response_gen] Error for {agent_name}: {exc}")
            stance = reasoning.get("current_stance", "")
            pts = ". ".join(reasoning.get("key_points", []))
            return f"{stance}. {pts}"

    # ── Prompt builders ──────────────────────────────────────────────────────

    def _build_system_prompt(
        self,
        agent_name: str,
        role_description: str,
        reasoning: Dict[str, Any],
        turn_info: Dict[str, Any],
        schema: Dict[str, str],
        current_round: int,
        max_rounds: int,
        valid_participant_names: List[str],
    ) -> str:
        # Stance-change instruction
        if reasoning.get("stance_changed"):
            stance_note = (
                f"You are revising your position. Begin with: "
                f"'I'm revising my view because {reasoning.get('reason_for_change', 'new evidence changes the picture')}…'"
            )
        else:
            stance_note = "Maintain your position. Build on it. Defend it if challenged."

        # Disagreement target
        disagree_note = ""
        targets = reasoning.get("should_disagree_with") or []
        if targets:
            # Only use valid names that actually exist in our participant list
            valid = [t for t in targets if t in valid_participant_names]
            if valid:
                names = ", ".join(f'@"{n}"' for n in valid)
                disagree_note = (
                    f"REQUIRED: Directly challenge {names}. "
                    "Quote or paraphrase their specific claim, then explain the flaw or counter-evidence."
                )

        # Valid-name guard
        names_str = (
            ", ".join(f'"{n}"' for n in valid_participant_names)
            if valid_participant_names else "none yet — you are first"
        )

        return f"""{role_description}

ROLE-SPECIFIC REVIEW DIMENSIONS:
  Focus on: {schema['dimensions']}
  When evaluating strengths: {schema['strengths']}
  When evaluating weaknesses: {schema['weaknesses']}
  Recommendation style: {schema['recommendations']}
  Evidence requirement: {schema['evidence_req']}

{stance_note}

{disagree_note}

VALID PARTICIPANT NAMES (only @mention these exact names — no others, no placeholders):
{names_str}

REVIEWER CONDUCT RULES:
1. Open with your substantive point — no filler phrases ("Let's dive in", "Good points", etc.)
2. Every evaluative claim must cite specific evidence from the submitted materials or the conversation.
3. Only use @mentions with names from the VALID list above.
4. Address challenges directed at you before making your own new point.
5. Do not repeat claims already made. Advance the analysis.
6. Do not produce a generic review that any role could have written — stay in your lane.

TURN: Round {current_round}/{max_rounds} | Urgency: {turn_info.get('urgency', 'Active review')}
LENGTH: {turn_info.get('length_instruction', '150–250 words, precise and substantive')}

Generate your review contribution now."""

    def _format_debate_context(self, context: Dict[str, Any]) -> str:
        parts = [f"Session: {context.get('title', 'Untitled')}"]
        if context.get("description"):
            parts.append(f"Research question / abstract: {context['description']}")
        if context.get("agenda"):
            items = "\n".join(f"  - {it}" for it in context["agenda"])
            parts.append(f"Review agenda:\n{items}")
        if context.get("desired_outcomes"):
            items = "\n".join(f"  - {it}" for it in context["desired_outcomes"])
            parts.append(f"Review objectives:\n{items}")
        return "\n\n".join(parts)
