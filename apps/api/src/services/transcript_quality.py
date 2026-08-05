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

# The same failure in its commoner disguise: opening by positioning against
# the other reviewers rather than leading with your own point. Removing the
# mandated final-turn sentence did not remove the habit — it moved it, and
# five of six turns in a live session then opened
#   @"Dr. Ada" and @"Dr. Lee," while I acknowledge ...
# which _AGREEMENT_OPENER (built for "X is correct") scored at 0.00.
#
# Three shapes, all measured against 30 openers labelled from real
# transcripts — 15 deference, 15 substantive — at full recall and precision:
#   (a) one to three reviewer names, then a concession
#   (b) a nominalisation of the debate itself ("the concerns raised by...",
#       "the ongoing discussion about...")
#   (c) explicit deference formulas ("building on...", "I agree with...")
#
# Deliberately NOT matched: an opener that names someone and then makes a
# claim — '@"Dr. Ada" is wrong about the effect size: d = 1.31 is not
# credible with n = 40' is engagement, which is what we want.
_REVIEWER_NAME = (
    r'(?:@"[^"]{2,40}"'
    # "@Dr. Ada" — the space is what a naive character class misses, and it is
    # the form the models actually emit. A pattern fitted only to the quoted
    # form scored 0.00 on a live run where four of six turns deferred.
    r'|@(?:Dr|Prof|Mr|Ms|Mrs)\.\s*[A-Z][\w\-]{1,20}'
    r'|@[\w.\-]{2,30}'
    r'|(?:Dr|Prof|Mr|Ms|Mrs)\.\s+[A-Z][\w\-]{1,20})'
)
_CONCESSION = (
    r"(?:while|whilst|although|though"
    r"|I\s+(?:agree|acknowledge|appreciate|concur|see\s+your\s+point|take\s+your\s+points?)"
    r"|you(?:'re|\s+are)\s+(?:correct|right)"
    r"|you\s+(?:both\s+)?(?:raised|make|are\s+right)"
    # "your critique regarding the lack of a comparative intervention is valid"
    r"|your\s+[\w\s]{0,60}?(?:is|are)\s+(?:indeed\s+)?valid"
    r"|(?:is|are)\s+(?:indeed\s+)?valid"
    r"|(?:highlights?|raises?)\s+(?:a\s+)?valid"
    r"|(?:is|are)\s+(?:essential|important)"
    r"|that\s+is\s+a\s+fair\s+point|fair\s+point|rightly"
    r"|valid\s+concerns?|good\s+points?|fair\s+points?)"
)

# Three branches, compiled separately rather than concatenated into one
# alternation: a single spliced pattern silently stopped matching branch (b)
# even though that branch worked in isolation. Separate patterns are also
# easier to reason about when one of them misfires.
_DEFERENCE_BRANCHES = (
    # (a) one to three reviewer names, then a concession
    re.compile(
        r'^\s*(?:' + _REVIEWER_NAME + r'[,\s]*(?:and|&|,)?\s*){1,3}[,:\s]*'
        + _CONCESSION,
        re.IGNORECASE,
    ),
    # (b) a nominalisation of the debate itself
    re.compile(
        r'^\s*(?:the\s+)?(?:\w+\s+){0,2}?'
        r'(?:critique|criticism|concerns?|points?|comments?|observations?'
        r'|discussion|conversation|debate|dialogue|exchange)\b'
        r'[^.]{0,90}?(?:\b(?:by|from|raised|put\s+forth|surrounding|about|regarding)\b'
        r'|has\s+veered)',
        re.IGNORECASE,
    ),
    # (c) explicit deference formulas, including the nameless second person.
    # "You both raise valid concerns, but..." slipped through branch (a),
    # which needs a name, and through the concession list, which had "raised"
    # but not "raise".
    re.compile(
        r'^\s*(?:building\s+on|I\s+agree\s+with|following\s+on\s+from'
        r'|as\s+(?:my\s+)?colleagues?'
        r'|you\s+(?:both\s+|all\s+)?(?:raise[sd]?|make|are)\b[^.]{0,40}?'
        r'(?:valid|good|fair|important|right)'
        r'|(?:that|these|those)\s+(?:is|are)\s+(?:a\s+)?(?:valid|fair|good)\s+point)',
        re.IGNORECASE,
    ),
)


# Branch (d) — the STRUCTURAL catch, for concessions the word list has not
# met yet.
#
# The list-based branches keep needing another entry: "while", then "you're
# correct", then "I see your point", then "you're highlighting". Each new
# model phrasing costs a round trip. The shape underneath does not change —
# name the reviewer, restate what they said, then pivot to your own point —
# so match the SHAPE: one to three names, then a pivot inside the opening.
#
# A rebuttal also names someone and may contain "but", so an opener that
# disagrees BEFORE the pivot is excluded. Only markers aimed at the other
# reviewer count; generic words about the paper ("lack", "absent", "fails")
# are exactly what a deference opener concedes about, and treating those as
# rebuttal silently lost seven true positives when it was tried.
_OPENING_WINDOW = 150
_PIVOT = re.compile(
    r'\b(?:but|however|yet|nevertheless|nonetheless|still)\b', re.IGNORECASE
)
_REBUTTAL = re.compile(
    r"\b(?:wrong|incorrect|mistaken|disagree\w*|misread\w*|misstat\w*"
    r"|not\s+credible|implausible|overstat\w*|is\s+not\s+supported)\b",
    re.IGNORECASE,
)
_NAME_PREFIX = re.compile(
    rf'\s*(?:{_REVIEWER_NAME}[,\s]*(?:and|&|,)?\s*){{1,3}}'
)


def _pivots_after_naming(text: str):
    """Names a reviewer, concedes, then pivots — without rebutting first."""
    head = (text or "")[:_OPENING_WINDOW]
    named = _NAME_PREFIX.match(head)
    if not named:
        return None
    rest = head[named.end():]
    pivot = _PIVOT.search(rest)
    if not pivot:
        return None
    if _REBUTTAL.search(rest[:pivot.start()]):
        return None
    return named


class _DeferenceOpener:
    """Any of the four branches. Exposes .search() so callers read normally."""

    @staticmethod
    def search(text: str):
        for pattern in _DEFERENCE_BRANCHES:
            m = pattern.search(text or "")
            if m:
                return m
        return _pivots_after_naming(text)


_DEFERENCE_OPENER = _DeferenceOpener()

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
    # Share of turns that restate a point an earlier turn already made.
    restatement_rate: float = 0.0
    repeated_phrases: List[str] = field(default_factory=list)

    def failures(self, thresholds: "Thresholds") -> List[str]:
        """Human-readable reasons this transcript falls short."""
        out = []
        if self.opener_template_rate > thresholds.max_opener_template_rate:
            out.append(
                f"{self.opener_template_rate:.0%} of turns open by endorsing another "
                f"reviewer (limit {thresholds.max_opener_template_rate:.0%})"
            )
        if self.restatement_rate > thresholds.max_restatement_rate:
            out.append(
                f"{self.restatement_rate:.0%} of turns restate a point already "
                f"made (limit {thresholds.max_restatement_rate:.0%})"
            )
        # self_similarity and role_differentiation are REPORTED but are not
        # gates. Measured across ten real transcripts, labelled by the two
        # metrics that do discriminate, their ranges overlap completely:
        #
        #   self_similarity       bad 0.132-0.346   good 0.143-0.174
        #   role_differentiation  bad 0.649-0.832   good 0.758-0.808
        #
        # The worst transcript in the set scored the LOWEST self_similarity
        # (0.132) and the HIGHEST role_differentiation (0.832), because six
        # reviewers restating one point in different words look lexically
        # diverse. Failing a session on either produced false failures on the
        # cleanest run measured. They stay in the report as diagnostics.
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

    Recalibrated against four real transcripts — two where every reviewer
    restated the same point, two after the repetition and citation fixes:

                            bad          good
        restatement_rate    0.80-1.00    0.00-0.20
        self_similarity     0.19-0.35    0.13-0.14
        role_differentiation 0.65-0.75   0.81-0.83

    restatement_rate and opener_template_rate are the gates. Re-measured
    later across TEN transcripts, self_similarity and role_differentiation
    turned out to have no discriminative power at all — their good and bad
    ranges overlap completely — so they are reported and not enforced. The
    earlier calibration of those two was fitted to four transcripts and was
    wrong; it failed the cleanest session measured.
    """
    max_opener_template_rate: float = 0.5
    max_restatement_rate: float = 0.5
    max_placeholder_rate: float = 0.2
    # Kept so callers that report these numbers keep working; they no longer
    # gate a transcript. See QualityReport.failures for the measurement.
    max_self_similarity: float = 0.17
    min_role_differentiation: float = 0.78


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
        hits = sum(
            1 for t in respondable
            if _AGREEMENT_OPENER.search(t) or _DEFERENCE_OPENER.search(t)
        )
        report.opener_template_rate = hits / len(respondable)

    report.placeholder_rate = sum(1 for t in texts if _PLACEHOLDER.search(t)) / len(texts)
    report.citation_form_rate = sum(
        1 for t in texts if _CITATION_FORM.search(t)
    ) / len(texts)

    # How much consecutive turns restate each other.
    words = [_content_words(t) for t in texts]
    pairs = [_jaccard(a, b) for a, b in zip(words, words[1:])]
    report.self_similarity = sum(pairs) / len(pairs) if pairs else 0.0

    # How many turns restate a point an EARLIER turn already made.
    #
    # self_similarity above is pairwise Jaccard on consecutive turns, which is
    # why it passed a transcript where all six reviewers made the identical
    # point: they used different words for it, and Jaccard divides by the
    # union so verbose restatements score low. This measures containment
    # against the shorter side and looks at every earlier turn, not just the
    # previous one — the same measure the live repetition guard uses, where it
    # separated real restatements (0.38-0.68) from genuinely new critiques
    # (0.00-0.07).
    restated = 0
    for i in range(1, len(words)):
        if not words[i]:
            continue
        best = max(
            (len(words[i] & w) / min(len(words[i]), len(w)) for w in words[:i] if w),
            default=0.0,
        )
        if best > 0.35:
            restated += 1
    report.restatement_rate = restated / (len(words) - 1) if len(words) > 1 else 0.0

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
