"""
Challenge severity levels ("difficulty dial").

A single user-facing control that makes the whole panel gentler or harsher.
The same level is threaded into BOTH question generation and answer evaluation
so a chosen severity shifts what gets asked AND how strictly it is judged.
"""
from __future__ import annotations

SEVERITY_LEVELS = ("gentle", "standard", "rigorous", "hostile")
DEFAULT_SEVERITY = "standard"

# Directive injected into the QUESTION-GENERATION prompt.
_QUESTION_DIRECTIVE = {
    "gentle": (
        "Severity: GENTLE. Ask supportive, clarifying questions that help the "
        "researcher explain their work. Favour easy/medium difficulty; avoid "
        "hostile framing. Aim to build confidence."
    ),
    "standard": (
        "Severity: STANDARD. Ask a balanced mix of clarifying and probing "
        "questions as a fair committee would, spanning easy/medium/hard."
    ),
    "rigorous": (
        "Severity: RIGOROUS. Ask demanding, specific questions that pressure-test "
        "methodology, evidence, and claims. Skew toward hard difficulty and "
        "require justification for every non-trivial claim."
    ),
    "hostile": (
        "Severity: HOSTILE. Act as a skeptical, adversarial examiner. Attack weak "
        "points directly, demand evidence for every claim, surface contradictions "
        "and unstated assumptions, and ask the hardest version of each question. "
        "Be fair but relentless — this is worst-case defense preparation."
    ),
}

# Directive injected into the ANSWER-EVALUATION prompt.
_EVAL_DIRECTIVE = {
    "gentle": (
        "Grade encouragingly. Reward genuine effort and partial correctness; "
        "flag only the most important gaps."
    ),
    "standard": (
        "Grade fairly, as a balanced committee would — credit what is sound and "
        "name what is missing."
    ),
    "rigorous": (
        "Grade strictly. Penalise vague, unsupported, or hand-wavy answers; require "
        "concrete evidence and precise reasoning to score well."
    ),
    "hostile": (
        "Grade as a harsh adversarial examiner. Assume nothing is proven unless the "
        "answer defends it with specific evidence; heavily penalise unsupported "
        "claims, overgeneralisation, and evasion. Only a rigorous, evidence-backed "
        "answer earns a high score."
    ),
}


def normalize(severity: str | None) -> str:
    s = (severity or "").strip().lower()
    return s if s in SEVERITY_LEVELS else DEFAULT_SEVERITY


def question_directive(severity: str | None) -> str:
    return _QUESTION_DIRECTIVE[normalize(severity)]


def eval_directive(severity: str | None) -> str:
    return _EVAL_DIRECTIVE[normalize(severity)]
