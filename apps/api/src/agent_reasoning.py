"""
Agent Reasoning Module — Stage 1 of the Constitutional AI Pipeline.

This module implements:
  • Structured stance evaluation before every response
  • Grounding in provided source materials
  • Validation: valid participants, no placeholders, no topic drift
  • Automatic regeneration when reasoning is flagged as a repeat
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .openrouter_client import OpenRouterClient

# Placeholder names the LLM should never emit
_PLACEHOLDER_PATTERNS = re.compile(
    r"\b(agent\s*[a-z]|reviewer\s*[0-9]+|participant\s*[0-9]+|persona\s*[a-z]|"
    r"speaker\s*[0-9]+|person\s*[a-z]|panelist\s*[0-9]+|name[0-9]+)\b",
    re.IGNORECASE,
)


def _scrub_json(text: str) -> str:
    """Strip markdown fences so we can parse raw JSON."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


class AgentReasoningEngine:
    """
    Stage 1: Evaluate the agent's current stance before generating a response.

    Outputs structured reasoning that drives Stage 2 (response generation).
    """

    def __init__(self, openrouter_api_key: str):
        self.client = OpenRouterClient(openrouter_api_key)

    # ── Public API ──────────────────────────────────────────────────────────

    def evaluate_stance(
        self,
        agent_name: str,
        agent_role: str,
        past_positions: str,
        recent_conversation: str,
        user_intervention: Optional[str] = None,
        debate_id: Optional[str] = None,
        valid_participant_names: Optional[List[str]] = None,
        session_title: Optional[str] = None,
        material_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Think through the agent's position before responding.

        Returns a validated reasoning dict with keys:
          current_stance, confidence, stance_changed, reason_for_change,
          what_others_said, am_i_repeating, unique_contribution,
          key_points, should_disagree_with
        """
        valid_names = valid_participant_names or []

        prompt = self._build_reasoning_prompt(
            agent_name=agent_name,
            agent_role=agent_role,
            past_positions=past_positions,
            recent_conversation=recent_conversation,
            user_intervention=user_intervention,
            valid_participant_names=valid_names,
            session_title=session_title,
            material_context=material_context,
        )

        reasoning = self._call_and_parse(
            prompt=prompt,
            debate_id=debate_id,
            agent_name=agent_name,
        )

        # ── Validation ──────────────────────────────────────────────────
        is_valid, failure_reason = self._validate(
            reasoning=reasoning,
            valid_names=valid_names,
            session_title=session_title,
        )

        regenerated = False
        if not is_valid:
            print(f"    [reasoning] Validation failed for {agent_name}: {failure_reason}")
            regenerated_prompt = self._build_reasoning_prompt(
                agent_name=agent_name,
                agent_role=agent_role,
                past_positions=past_positions,
                recent_conversation=recent_conversation,
                user_intervention=user_intervention,
                valid_participant_names=valid_names,
                session_title=session_title,
                material_context=material_context,
                validation_failure=failure_reason,
            )
            reasoning = self._call_and_parse(
                prompt=regenerated_prompt,
                debate_id=debate_id,
                agent_name=agent_name,
            )
            regenerated = True

        # ── Repetition handling ─────────────────────────────────────────
        # Cap reasoning at two LLM calls/turn (BUG-027): if we already
        # regenerated for a validation failure, the reasoning is fresh — skip
        # the extra repetition regeneration to keep live turns responsive.
        if not regenerated and reasoning.get("am_i_repeating") == "repeat":
            print(f"    [reasoning] Repetition detected for {agent_name} — regenerating")
            repeat_prompt = self._build_reasoning_prompt(
                agent_name=agent_name,
                agent_role=agent_role,
                past_positions=past_positions,
                recent_conversation=recent_conversation,
                user_intervention=user_intervention,
                valid_participant_names=valid_names,
                session_title=session_title,
                material_context=material_context,
                repetition_notice=(
                    "You have been flagged for repeating previously stated arguments. "
                    "You MUST introduce a new evidence-based perspective, critique, concern, "
                    "or recommendation that has NOT yet been discussed. It must be consistent "
                    "with your assigned role and grounded in the provided materials."
                ),
            )
            reasoning = self._call_and_parse(
                prompt=repeat_prompt,
                debate_id=debate_id,
                agent_name=agent_name,
            )
            # Force am_i_repeating to 'new' after retry
            if reasoning.get("am_i_repeating") == "repeat":
                reasoning["am_i_repeating"] = "new"

        # ── Clean up should_disagree_with ────────────────────────────────
        if valid_names:
            raw_disagree = reasoning.get("should_disagree_with", []) or []
            reasoning["should_disagree_with"] = [
                n for n in raw_disagree
                if isinstance(n, str) and n in valid_names
            ]

        return reasoning

    # ── Internal helpers ────────────────────────────────────────────────────

    def _call_and_parse(
        self,
        prompt: str,
        debate_id: Optional[str],
        agent_name: str,
    ) -> Dict[str, Any]:
        """Call the LLM and parse JSON, returning a safe fallback on error."""
        try:
            response = self.client.chat_completion(
                model="openai/gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an internal reasoning engine. "
                            "Output ONLY valid JSON, no prose, no markdown fences. "
                            "Think step-by-step about the agent's position and return the JSON object."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=500,
                _debate_id=debate_id,
                _stage="reasoning",
                _participant=agent_name,
            )

            raw = _scrub_json(response["content"])
            reasoning = json.loads(raw)

            required = ["current_stance", "confidence", "stance_changed", "key_points"]
            if not all(k in reasoning for k in required):
                raise ValueError(f"Missing required keys: {list(reasoning.keys())}")

            return reasoning

        except (json.JSONDecodeError, ValueError) as exc:
            print(f"    [reasoning] Parse error for {agent_name}: {exc}")
        except Exception as exc:
            print(f"    [reasoning] Engine error for {agent_name}: {exc}")

        return {
            "current_stance": "maintain previous analytical position",
            "confidence": 0.7,
            "stance_changed": False,
            "reason_for_change": None,
            "what_others_said": "",
            "am_i_repeating": "new",
            "unique_contribution": "raise a fresh concern from my reviewer lane",
            "key_points": ["continue analysis from my reviewer perspective"],
            "should_disagree_with": [],
        }

    def _validate(
        self,
        reasoning: Dict[str, Any],
        valid_names: List[str],
        session_title: Optional[str],
    ) -> tuple[bool, str]:
        """
        Returns (is_valid, failure_reason).
        Checks:
          1. should_disagree_with has only valid participant names
          2. No placeholder names in any text field
          3. current_stance is not empty/generic
        """
        # Check 1: invalid participant references
        disagree_list = reasoning.get("should_disagree_with") or []
        if valid_names and disagree_list:
            invalid = [n for n in disagree_list if isinstance(n, str) and n not in valid_names]
            if invalid:
                return False, (
                    f"should_disagree_with contains invalid participant names: {invalid}. "
                    f"Valid names are: {valid_names}. Only use names from this list."
                )

        # Check 2: placeholder patterns in any text field
        text_fields = [
            reasoning.get("current_stance", ""),
            reasoning.get("unique_contribution", ""),
            " ".join(reasoning.get("key_points") or []),
            " ".join(disagree_list),
        ]
        combined = " ".join(str(f) for f in text_fields)
        if _PLACEHOLDER_PATTERNS.search(combined):
            return False, (
                "Reasoning contains placeholder participant identifiers such as 'Agent A', "
                "'Reviewer 1', or 'Participant 2'. Replace these with the actual participant "
                f"names from the session: {valid_names or 'use names from the context'}."
            )

        # Check 3: meaningful stance
        stance = reasoning.get("current_stance", "").strip()
        if len(stance) < 10 or stance.lower() in (
            "maintain previous position",
            "continue previous argument",
            "i agree",
            "no change",
        ):
            return False, (
                "current_stance is too generic or empty. Provide a specific, substantive "
                "one-sentence analytical position grounded in the research materials and "
                "session context."
            )

        return True, ""

    # ── Prompt builder ──────────────────────────────────────────────────────

    def _build_reasoning_prompt(
        self,
        agent_name: str,
        agent_role: str,
        past_positions: str,
        recent_conversation: str,
        user_intervention: Optional[str] = None,
        valid_participant_names: Optional[List[str]] = None,
        session_title: Optional[str] = None,
        material_context: Optional[str] = None,
        validation_failure: Optional[str] = None,
        repetition_notice: Optional[str] = None,
    ) -> str:

        # Build optional sections
        intervention_section = ""
        if user_intervention:
            intervention_section = f"""
MODERATOR / RESEARCHER JUST SAID:
{user_intervention}

Do not automatically agree. Evaluate objectively before deciding whether to adjust your position.
"""

        material_section = ""
        if material_context:
            material_section = f"""
SOURCE MATERIALS (available to all reviewers — ground your reasoning here):
{material_context}
"""

        valid_names_section = ""
        if valid_participant_names:
            valid_names_section = f"""
VALID SESSION PARTICIPANTS (only reference these exact names — no others):
{", ".join(valid_participant_names)}
"""

        failure_section = ""
        if validation_failure:
            failure_section = f"""
PREVIOUS REASONING FAILED VALIDATION — REASON:
{validation_failure}

Correct the above issue in your new output.
"""

        repetition_section = ""
        if repetition_notice:
            repetition_section = f"""
REPETITION WARNING:
{repetition_notice}
"""

        session_context = f"Session: {session_title}" if session_title else ""

        return f"""You are the internal reasoning engine for {agent_name} ({agent_role}).
{session_context}

{past_positions}

RECENT CONVERSATION:
{recent_conversation}

{material_section}
{valid_names_section}
{intervention_section}
{failure_section}
{repetition_section}

TASK: Reason through your analytical position step-by-step.

STEP 1 — Current stance (ONE specific sentence grounded in the research or materials)
STEP 2 — Confidence (0.0–1.0)
STEP 3 — Has your stance changed since your last message? (true/false)
STEP 4 — If changed: what new evidence or argument justifies it?
STEP 5 — What did others JUST say? (1 sentence summary of the recent conversation)
STEP 6 — Am I about to REPEAT what has already been said? (repeat / new / build_on)
STEP 7 — What is my ONE unique contribution that nobody else has made yet?
STEP 8 — Whose specific claims should I challenge? List valid participant names ONLY, or [].

RULES:
- current_stance must be specific and analytical — not "I maintain my position"
- should_disagree_with MUST only contain names from the VALID PARTICIPANTS list above
- Never reference Agent A, Reviewer 1, or any placeholder — use real session names only
- Key points must be distinct and not restate what others said
- Ground every analytical claim in the session topic or source materials

OUTPUT (valid JSON only — no markdown, no code fences):
{{
  "current_stance": "one specific analytical sentence",
  "confidence": 0.85,
  "stance_changed": false,
  "reason_for_change": null,
  "what_others_said": "one-sentence summary of recent conversation",
  "am_i_repeating": "new",
  "unique_contribution": "one sentence — what I am adding that is new",
  "key_points": ["distinct point 1", "distinct point 2", "distinct point 3"],
  "should_disagree_with": []
}}"""
