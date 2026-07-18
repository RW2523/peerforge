"""
Practice modes — what kind of academic evaluation is being rehearsed.

Each mode reframes the same uploaded research for a different real-world
evaluation (thesis defense, proposal defense, conference Q&A, journal review),
shifting which personas dominate and what the panel emphasises. It layers on
top of severity (challenge_levels) and reasoning mode (model tier).
"""
from __future__ import annotations
from typing import Dict, List

PRACTICE_MODES = ("thesis_defense", "proposal_defense", "conference_qa", "journal_review")
DEFAULT_MODE = "thesis_defense"

_MODES: Dict[str, Dict] = {
    "thesis_defense": {
        "label": "Thesis / Dissertation Defense",
        "focus": (
            "This is a thesis/dissertation defense. The committee examines the "
            "completed work end to end: problem, methodology, results, contribution, "
            "limitations, and the researcher's command of their own study. Ask across "
            "all categories; demand the researcher defend and justify every part."
        ),
        "emphasis": ["methodology", "evidence", "results", "limitations", "novelty"],
    },
    "proposal_defense": {
        "label": "Proposal Defense",
        "focus": (
            "This is a PROPOSAL defense — the work is planned, not finished. Focus on "
            "the research gap, the significance and feasibility of the plan, the proposed "
            "methodology and its risks, and whether the contribution would be worthwhile. "
            "Do NOT press for final results; press on whether the plan is sound and doable."
        ),
        "emphasis": ["research_gap", "methodology", "future_work", "practical_impact", "problem_statement"],
    },
    "conference_qa": {
        "label": "Conference Presentation Q&A",
        "focus": (
            "This is conference-talk Q&A from an informed audience. Questions are sharp, "
            "high-level, and time-pressured: the core takeaway, why it matters, how it "
            "compares to related work, and quick clarifications. Favour crisp, pointed "
            "questions over exhaustive committee-style interrogation."
        ),
        "emphasis": ["novelty", "practical_impact", "results", "problem_statement", "panel_challenge"],
    },
    "journal_review": {
        "label": "Journal / Conference Review",
        "focus": (
            "Act as peer REVIEWERS assessing this manuscript for publication. Evaluate "
            "novelty, rigour of methodology and experimental design, sufficiency of "
            "evidence, reproducibility, positioning against prior work, and validity of "
            "claims. Raise the objections a real reviewer would put in their report."
        ),
        "emphasis": ["novelty", "methodology", "evidence", "results", "research_gap"],
    },
}


def normalize(mode: str | None) -> str:
    m = (mode or "").strip().lower()
    return m if m in PRACTICE_MODES else DEFAULT_MODE


def mode_focus(mode: str | None) -> str:
    return _MODES[normalize(mode)]["focus"]


def mode_emphasis(mode: str | None) -> List[str]:
    return _MODES[normalize(mode)]["emphasis"]


def mode_label(mode: str | None) -> str:
    return _MODES[normalize(mode)]["label"]
