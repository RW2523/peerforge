"""
Measuring review quality from a transcript.

The repetition problem in this codebase was found by reading transcripts by
hand and then written up in prose across several *_FIX.md documents. Nothing
measured it, so each prompt change could silently undo the last fix.

These metrics are deliberately computed from a recorded transcript with no
model calls, so they are cheap, deterministic, and can gate CI. They do not
judge whether a review is *good* — that needs a human or a judge model. They
detect the specific ways this panel is known to fail:

  opener_template_rate   reviewers all opening by endorsing each other
  role_differentiation   lanes collapsing so everyone writes the same critique
  self_similarity        the same points restated across turns
  placeholder_rate       "@Name" and invented citations leaking into output
  citation_form_rate     turns that CITE something — form only, see below
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

# "@"Dr. Ada" and @"Dr. Ben" are entirely right to ..." — the shape that
# dominated transcripts before the persona lanes were fixed.
_AGREEMENT_OPENER = re.compile(
    r'^\s*(?:@?"?[\w.\- ]{2,40}"?\s*(?:,|and)?\s*){1,3}'
    r'(?:is|are)\s+(?:entirely|completely|absolutely|quite|so)?\s*'
    r'(?:correct|right)\b',
    re.IGNORECASE,
)

# Names the model was told never to emit.
_PLACEHOLDER = re.compile(
    r'@(?:Name|Agent|Person|Someone|Participant|Reviewer)\b'
    r'|\[(?:source not provided|website|Author, URL|citation needed)\]'
    r'|\((?:Author|Kaggle),\s*URL\)',
    re.IGNORECASE,
)

# A claim tied to the materials rather than asserted freely.
# Matches the SHAPE of a citation, not its truth. A reviewer that invents
# "Section 4.2" scores exactly like one quoting a real passage, so this must
# never be reported as "grounding": it was, and a turn with fabricated
# citations came back grounding_rate 1.0 and healthy: true. Verifying a
# citation means checking it against the retrieved chunks, which this harness
# deliberately does not do.
_CITATION_FORM = re.compile(
    r'\bexcerpt\b|\bas stated\b|\bSection\s+\d|\bTable\s+\d|\bFigure\s+\d'
    r'|\bp\.\s*\d+|\bquotes?\b|"[^"]{12,}"',
    re.IGNORECASE,
)

_WORD = re.compile(r"[a-z]{4,}")

# Words every academic review uses; counting them as shared content would make
# any two reviews look similar regardless of what they actually said.
_STOPWORDS = frozenset("""
this that with from have been they there their which would could should
about your work paper study these those than then when what where more most
some such very much only also into over under while because however
""".split())


@dataclass
class Turn:
    speaker: str
    text: str
    role: Optional[str] = None


@dataclass
class QualityReport:
    turns: int = 0
    opener_template_rate: float = 0.0
    self_similarity: float = 0.0
    role_differentiation: float = 1.0
    placeholder_rate: float = 0.0
    # Renamed from grounding_rate, which claimed more than it measured.
    citation_form_rate: float = 0.0
    repeated_phrases: List[str] = field(default_factory=list)

    def failures(self, thresholds: "Thresholds") -> List[str]:
        """Human-readable reasons this transcript falls short."""
        out = []
        if self.opener_template_rate > thresholds.max_opener_template_rate:
            out.append(
                f"{self.opener_template_rate:.0%} of turns open by endorsing another "
                f"reviewer (limit {thresholds.max_opener_template_rate:.0%})"
            )
        if self.self_similarity > thresholds.max_self_similarity:
            out.append(
                f"turns share {self.self_similarity:.0%} of their vocabulary "
                f"(limit {thresholds.max_self_similarity:.0%})"
            )
        if self.role_differentiation < thresholds.min_role_differentiation:
            out.append(
                f"reviewer lanes are {self.role_differentiation:.0%} distinct "
                f"(need {thresholds.min_role_differentiation:.0%})"
            )
        if self.placeholder_rate > thresholds.max_placeholder_rate:
            out.append(
                f"{self.placeholder_rate:.0%} of turns contain placeholder names "
                f"or invented citations"
            )
        return out


@dataclass(frozen=True)
class Thresholds:
    """
    Set from observed behaviour, not aspiration.

    The pre-fix transcript scored 0.80 on opener templates; the post-fix one
    scored 0.00. 0.5 sits well clear of the good case while still catching a
    regression to the old behaviour.
    """
    max_opener_template_rate: float = 0.5
    max_self_similarity: float = 0.45
    min_role_differentiation: float = 0.3
    max_placeholder_rate: float = 0.2


def _content_words(text: str) -> set:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def analyse(turns: Sequence[Turn]) -> QualityReport:
    """Measure a transcript. Safe on empty or single-turn input."""
    report = QualityReport(turns=len(turns))
    if not turns:
        return report

    texts = [t.text or "" for t in turns]

    # Opening move. The first turn has nobody to agree with, so it is excluded
    # rather than counted as a pass and diluting the rate.
    respondable = texts[1:]
    if respondable:
        hits = sum(1 for t in respondable if _AGREEMENT_OPENER.search(t))
        report.opener_template_rate = hits / len(respondable)

    report.placeholder_rate = sum(1 for t in texts if _PLACEHOLDER.search(t)) / len(texts)
    report.citation_form_rate = sum(
        1 for t in texts if _CITATION_FORM.search(t)
    ) / len(texts)

    # How much consecutive turns restate each other.
    words = [_content_words(t) for t in texts]
    pairs = [_jaccard(a, b) for a, b in zip(words, words[1:])]
    report.self_similarity = sum(pairs) / len(pairs) if pairs else 0.0

    report.role_differentiation = _role_differentiation(turns, words)
    report.repeated_phrases = _repeated_phrases(texts)
    return report


def _role_differentiation(turns: Sequence[Turn], words: Sequence[set]) -> float:
    """
    1.0 when reviewers in different lanes write about different things.

    Compares across roles rather than across speakers: two reviewers sharing a
    lane are *supposed* to overlap, and counting that as failure would punish
    a panel for being staffed the way it was asked to be.
    """
    by_role: Dict[str, set] = {}
    for turn, bag in zip(turns, words):
        key = (turn.role or turn.speaker or "").strip().lower()
        if not key:
            continue
        by_role.setdefault(key, set()).update(bag)

    roles = [v for v in by_role.values() if v]
    if len(roles) < 2:
        # Nothing to differentiate; do not report a problem that cannot exist.
        return 1.0

    overlaps = [
        _jaccard(roles[i], roles[j])
        for i in range(len(roles))
        for j in range(i + 1, len(roles))
    ]
    return 1.0 - (sum(overlaps) / len(overlaps))


def _repeated_phrases(texts: Sequence[str], n: int = 5, min_count: int = 3) -> List[str]:
    """Phrases recurring across turns — usually prompt scaffolding leaking out."""
    counts: Dict[str, int] = {}
    for text in texts:
        tokens = re.findall(r"[\w']+", text.lower())
        seen_here = set()
        for i in range(len(tokens) - n + 1):
            gram = " ".join(tokens[i:i + n])
            # Count a phrase once per turn, so one turn repeating itself does
            # not look like every reviewer saying the same thing.
            if gram not in seen_here:
                seen_here.add(gram)
                counts[gram] = counts.get(gram, 0) + 1
    return sorted(
        (g for g, c in counts.items() if c >= min_count),
        key=lambda g: -counts[g],
    )[:10]


def turns_from_events(events: Iterable[dict]) -> List[Turn]:
    """Build turns from stored agent_message events."""
    out = []
    for e in events:
        if e.get("event_type") not in (None, "agent_message"):
            continue
        content = e.get("content") or {}
        if isinstance(content, str):
            text, speaker, role = content, e.get("agent") or "", None
        else:
            text = content.get("message") or content.get("text") or ""
            speaker = content.get("agent_name") or e.get("agent") or ""
            role = content.get("role_description") or content.get("role")
        if text:
            out.append(Turn(speaker=speaker, text=text, role=role))
    return out
