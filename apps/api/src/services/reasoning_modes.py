"""
Reasoning Modes
===============
Three tiers that control which LLM models are used across every AI activity
in the review platform and the discussion engine.

  Light  — Single cheap model for all tasks. Fast, low-cost, good for iteration.
  Medium — Different models per task/persona. Balanced quality vs. cost.
  Heavy  — Frontier models for every activity. Production-grade, highest quality.

Usage
-----
    from .reasoning_modes import get_model, get_persona_model, MODES

    model = get_model("analysis", mode="medium")
    persona_model = get_persona_model("Skeptical Reviewer", mode="heavy")
"""
from __future__ import annotations

from typing import Dict, Literal

ReasoningMode = Literal["light", "medium", "heavy"]

# ── Model registry ────────────────────────────────────────────────────────
# All IDs are OpenRouter-compatible slugs.

# Light: one cheap, fast model for everything.
# User said "summary we use claude" → summary/report always claude even in light.
_LIGHT_DEFAULT  = "openai/gpt-4o-mini"
_LIGHT_SUMMARY  = "anthropic/claude-sonnet-4-5"

# Medium: task-aware model selection; smarter where it counts.
_MEDIUM: Dict[str, str] = {
    "analysis":           "anthropic/claude-sonnet-4-5",
    "question_generation":"anthropic/claude-sonnet-4-5",
    "answer_evaluation":  "openai/gpt-4o",
    "summary":            "anthropic/claude-sonnet-4-5",
    "readiness_report":   "anthropic/claude-sonnet-4-5",
    "persona_suggestion": "anthropic/claude-sonnet-4-5",
    "reasoning":          "openai/gpt-4o",
    "response_generation":"openai/gpt-4o-mini",
    "preflight":          "anthropic/claude-sonnet-4-5",
    # Per-persona overrides (committee roles in Medium tier)
    "persona:Advisor":                "anthropic/claude-sonnet-4-5",
    "persona:Methodology Professor":  "openai/gpt-4o",
    "persona:Domain Expert":          "anthropic/claude-sonnet-4-5",
    "persona:Skeptical Reviewer":     "openai/gpt-4o",
    "persona:Friendly Professor":     "openai/gpt-4o-mini",
    "persona:Independent Reviewer":   "anthropic/claude-sonnet-4-5",
}

# Heavy: frontier models for everything.
_HEAVY_DEFAULT = "anthropic/claude-opus-4"
_HEAVY: Dict[str, str] = {
    "analysis":           "anthropic/claude-opus-4",
    "question_generation":"anthropic/claude-opus-4",
    "answer_evaluation":  "anthropic/claude-opus-4",
    "summary":            "anthropic/claude-opus-4",
    "readiness_report":   "anthropic/claude-opus-4",
    "persona_suggestion": "anthropic/claude-opus-4",
    "reasoning":          "anthropic/claude-opus-4",
    "response_generation":"anthropic/claude-opus-4",
    "preflight":          "anthropic/claude-opus-4",
    # All personas get the frontier model
    "persona:Advisor":                "anthropic/claude-opus-4",
    "persona:Methodology Professor":  "anthropic/claude-opus-4",
    "persona:Domain Expert":          "anthropic/claude-opus-4",
    "persona:Skeptical Reviewer":     "anthropic/claude-opus-4",
    "persona:Friendly Professor":     "anthropic/claude-opus-4",
    "persona:Independent Reviewer":   "anthropic/claude-opus-4",
}

# ── Public metadata (used in UI) ──────────────────────────────────────────
MODES: Dict[str, Dict] = {
    "light": {
        "label":       "⚡ Light",
        "description": "Fast & affordable — single model for all tasks. Good for practice runs.",
        "default_model": _LIGHT_DEFAULT,
        "summary_model": _LIGHT_SUMMARY,
        "cost_hint":   "~$0.01–0.05 per session",
    },
    "medium": {
        "label":       "⚖️ Medium",
        "description": "Balanced — smarter models for complex roles, lighter models elsewhere.",
        "default_model": _MEDIUM.get("analysis", "anthropic/claude-sonnet-4-5"),
        "summary_model": _MEDIUM.get("summary",   "anthropic/claude-sonnet-4-5"),
        "cost_hint":   "~$0.10–0.40 per session",
    },
    "heavy": {
        "label":       "🔥 Heavy",
        "description": "Frontier — most powerful models for every activity. Production-grade.",
        "default_model": _HEAVY_DEFAULT,
        "summary_model": _HEAVY_DEFAULT,
        "cost_hint":   "~$1–5 per session",
    },
}


# ── API ───────────────────────────────────────────────────────────────────

def get_model(task: str, mode: ReasoningMode = "medium") -> str:
    """
    Return the model ID to use for *task* at the given *mode*.

    task examples: "analysis", "question_generation", "answer_evaluation",
                   "summary", "readiness_report", "preflight", "reasoning",
                   "response_generation", "persona_suggestion"
    """
    if mode == "light":
        return _LIGHT_SUMMARY if task in ("summary", "readiness_report") else _LIGHT_DEFAULT
    if mode == "heavy":
        return _HEAVY.get(task, _HEAVY_DEFAULT)
    # medium
    return _MEDIUM.get(task, "anthropic/claude-sonnet-4-5")


def get_persona_model(persona_name: str, mode: ReasoningMode = "medium") -> str:
    """
    Return the model ID to use for a specific reviewer persona at the given mode.

    Falls back to the generic task model for "response_generation" if persona
    key not found.
    """
    if mode == "light":
        return _LIGHT_DEFAULT
    if mode == "heavy":
        return _HEAVY.get(f"persona:{persona_name}", _HEAVY_DEFAULT)
    # medium
    return _MEDIUM.get(f"persona:{persona_name}", _MEDIUM.get("response_generation", "openai/gpt-4o-mini"))


def mode_from_policy(policy_config: dict) -> ReasoningMode:
    """Extract reasoning mode from a debate's policy_config dict."""
    raw = (policy_config or {}).get("reasoning_mode", "medium")
    if raw in ("light", "medium", "heavy"):
        return raw  # type: ignore[return-value]
    return "medium"
