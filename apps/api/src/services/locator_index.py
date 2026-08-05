"""
What locators a session's document actually contains.

A reviewer citing "Section 2.3" of a paper whose sections are 1, 2, 2.1, 2.2
and 3 is making a false statement about someone's work. Observed live. The
no-materials guard in agent_constitutional_validator cannot catch it: a
document does exist, so every locator in the message is plausible.

Verification is deliberately THREE-VALUED, because absence of evidence here
is weak evidence of absence:

    verified      the cited locator appears in the extracted document
    absent        the document has locators of that family, but not this one
                  — the discriminating case, and the only one we act on
    unverifiable  the document has no locator of that family at all, so
                  extraction may simply have dropped the structure (a PDF
                  whose headings did not survive, a plain-prose brief).
                  Stay silent.

Page numbers are NEVER verified. chunk_metadata->>'page_num' is NULL for 391
of 398 material chunks in the live database, so the extracted text carries no
page structure to check against and any page verdict would be noise.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, Optional, Set, Tuple

from ..database import get_db_connection, get_cursor

logger = logging.getLogger(__name__)

# Families we can check. "page" is absent on purpose — see the module docstring.
_FAMILY_PATTERNS: Dict[str, re.Pattern] = {
    "section": re.compile(r"\bsections?\s+(\d+(?:\.\d+)*)", re.IGNORECASE),
    "table": re.compile(r"\btables?\s+(\d+)", re.IGNORECASE),
    "figure": re.compile(r"\bfigures?\s+(\d+)", re.IGNORECASE),
    "appendix": re.compile(r"\bappendix\s+([A-Z0-9])\b"),
}

# Presence is judged as generously as possible, and this is the whole design.
#
# The first version tried to recognise HEADINGS: the word "Section" followed
# by a number, plus a bare dotted heading like "2.1 Participant Selection".
# It measured beautifully on a paper that wrote "Section 1. Introduction" and
# then falsely accused three of five truthful citations on a paper whose
# top-level headings are bare-numbered — "1 Introduction", "2 Methods" — which
# the dotted pattern skips. Because "2.1" WAS indexed, the family looked
# populated, so absence read as fabrication rather than as ignorance.
#
# The two errors are not symmetric. Missing a real fabrication costs a
# citation nobody checks. Falsely accusing costs a reviewer their correct
# sentence, replaced with a marker saying they made it up. So an identifier
# counts as present if it appears ANYWHERE in the document as a standalone
# number — heading, cross-reference, table cell, list item, running text.
# Only a locator whose number occurs nowhere at all is called absent.
# (?![\d.]) rejected a TRAILING FULL STOP, so a document that writes its
# headings as "Section 3. Results" registered neither 3 nor 4 — and a
# reviewer citing Section 4 was told, in a real end-to-end run, that it is
# "[not in the submitted document]". The same lookahead bug was fixed in
# the strip regex hours earlier and not checked here. Reject a following
# digit, or a period that begins a longer dotted number; allow a period
# that ends a sentence.
_STANDALONE_NUMBER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)*)(?!\d)(?!\.\d)")

# A line that opens with a dotted number is a heading, not prose.
_DOTTED_HEADING = re.compile(r"(?m)^\s*(\d+(?:\.\d+)+)\s+\S")

# Letter-keyed families (Appendix B) need their own scan.
_STANDALONE_LETTER = re.compile(r"(?<![\w])([A-Z])(?![\w])")


# Materials rarely change mid-session, and rebuilding costs one indexed query.
# Keyed by debate; the chunk count is carried so an upload mid-debate is
# noticed rather than served stale.
_CACHE: Dict[str, Tuple[int, Dict[str, Set[str]]]] = {}


def _chunk_text_for(debate_id: str) -> Tuple[str, int]:
    """Full extracted text for a session's materials, plus the chunk count.

    Reads memory_chunks rather than the prompt's material context: that
    context is truncated (449 chars from an 812-byte upload), so absence from
    it proves nothing about the document.
    """
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            """
            SELECT chunk_text
            FROM   memory_chunks
            WHERE  source_debate_id = %s AND agent_id IS NULL
            ORDER BY created_at
            """,
            (debate_id,),
        )
        rows = cur.fetchall()
    return "\n".join((r["chunk_text"] or "") for r in rows), len(rows)


def build_index(debate_id: str) -> Dict[str, Set[str]]:
    """Locators present in the session's document, by family."""
    document, chunk_count = _chunk_text_for(debate_id)

    cached = _CACHE.get(debate_id)
    if cached is not None and cached[0] == chunk_count:
        return cached[1]

    # One generous pool of identifiers the document mentions at all, rather
    # than a per-family guess at what its headings look like.
    present_numbers = {m for m in _STANDALONE_NUMBER.findall(document)}
    present_letters = {m for m in _STANDALONE_LETTER.findall(document)}

    index: Dict[str, Set[str]] = {}
    for family, pattern in _FAMILY_PATTERNS.items():
        # A family is only checkable if the document evidences it. A paper with
        # no figures may simply have lost them in extraction, so a citation to
        # "Figure 3" there is unverifiable, never fabricated.
        named = re.search(rf"\b{family}s?\b", document, re.IGNORECASE) is not None
        if family == "section" and not named:
            # Plenty of papers number their sections without ever writing the
            # word — "1 Introduction", "2.1 Participant Selection". Two or more
            # distinct dotted numbers is good evidence of numbered sectioning;
            # one could be a p-value or a version string.
            named = len({n for n in present_numbers if "." in n}) >= 2
        if not named:
            index[family] = set()
            continue
        index[family] = {n.lower() for n in (
            present_letters if family == "appendix" else present_numbers
        )}

    _CACHE[debate_id] = (chunk_count, index)
    return index


def build_evidenced(debate_id: str) -> Dict[str, Set[str]]:
    """Identifiers the document names EXPLICITLY, e.g. "Section 2.1", "Table 1".

    Reported to the model when a citation is rejected; the generous pool above
    is right for deciding presence but wrong for saying what the document
    contains. Enumerating it told a reviewer the paper "has: 1, 1.31, 12.4, 40"
    — every standalone number in the text — which invites the retry to cite
    "Section 40".
    """
    document, _ = _chunk_text_for(debate_id)
    evidenced: Dict[str, Set[str]] = {}
    for family, pattern in _FAMILY_PATTERNS.items():
        found = {m.lower() for m in pattern.findall(document)}
        if family == "section":
            found |= {m.lower() for m in _DOTTED_HEADING.findall(document)}
        evidenced[family] = found
    return evidenced


def verify_locator(family: str, identifier: str, index: Dict[str, Set[str]]) -> str:
    """One of "verified", "absent", "unverifiable"."""
    present = index.get(family) or set()
    if not present:
        return "unverifiable"
    return "verified" if identifier.lower() in present else "absent"


def find_absent_locators(debate_id: str, message: str) -> list:
    """Locators the message cites that the document contradicts.

    Returns [] when the message cites nothing, when everything checks out, or
    whenever the answer is merely unknown.
    """
    cited = []
    for family, pattern in _FAMILY_PATTERNS.items():
        for identifier in pattern.findall(message):
            cited.append((family, identifier))
    if not cited:
        return []

    try:
        index = build_index(debate_id)
        evidenced = build_evidenced(debate_id)
    except Exception:
        # Never fail a turn over verification. Unknown is not fabricated.
        logger.warning("locator index unavailable for %s", debate_id, exc_info=True)
        return []

    absent = []
    seen = set()
    for family, identifier in cited:
        key = (family, identifier.lower())
        if key in seen:
            continue
        seen.add(key)
        if verify_locator(family, identifier, index) == "absent":
            absent.append({
                "family": family,
                "cited": identifier,
                "present": sorted(evidenced.get(family) or ())[:6],
            })
    return absent


def clear_cache() -> None:
    _CACHE.clear()
