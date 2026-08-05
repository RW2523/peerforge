"""
_split_long_paragraph silently dropped text.

    start = max(start + chunk_size - overlap, end)

When a sentence break landed past the halfway mark but before start+800 —
and the text after it had no sentence punctuation for a while — `end` was
less than start+800, so the next window began at start+800 and everything
between was in NO chunk. That is the shape of a table block, an affiliation
list, or a caption cluster.

Measured before the fix: 198 characters of a 1901-char paragraph present in
the document and in no chunk, taking a section heading with them. The
overlap was also never applied, because the max() almost always chose the
larger left-hand term.

This matters beyond chunking: retrieval, grounding, and the locator index
all read chunk_text, so dropped text is invisible to every one of them.
"""
import random

import pytest

from src.utils.chunking import TextChunker

# The exact failing shape: an early sentence break, then 380 chars with no
# sentence punctuation at all.
TABLE_BLOCK = "a" * 600 + ". " + "SECTION-2-3-MARKER " + "b" * 380 + "c" * 900


def _covered(text, chunk_size=1000, overlap=200):
    """Every character of the input must appear in at least one chunk."""
    chunks = TextChunker._split_long_paragraph(text, chunk_size, overlap)
    joined = "".join(chunks)
    probes = [text[i:i + 40] for i in range(0, max(1, len(text) - 40), 37)]
    missing = [p for p in probes if p.strip() and p not in joined]
    return chunks, missing


def test_the_table_block_shape_loses_nothing():
    chunks, missing = _covered(TABLE_BLOCK)
    assert not missing, f"{len(missing)} spans dropped, e.g. {missing[0]!r}"
    assert "SECTION-2-3-MARKER" in "".join(chunks)


@pytest.mark.parametrize("label,text", [
    ("clean prose", " ".join(f"Sentence number {i} about the study design." for i in range(120))),
    ("no punctuation at all", "z" * 5000),
    ("single short sentence", "one sentence only."),
    ("headings with no blank lines", "\n".join(
        f"{i} Heading {i}\n" + ("filler " * 60) for i in range(1, 12))),
])
def test_other_shapes_lose_nothing(label, text):
    _, missing = _covered(text)
    assert not missing, f"{label}: dropped {missing[0]!r}"


def test_randomised_shapes_lose_nothing():
    rng = random.Random(0)
    for _ in range(40):
        text = "".join(
            rng.choice(["word ", "text. ", "more! ", "x" * rng.randint(5, 60) + " "])
            for _ in range(rng.randint(50, 400))
        )
        _, missing = _covered(text)
        assert not missing, f"dropped {missing[0]!r} from {len(text)}-char input"


def test_it_terminates_on_pathological_input():
    """The guard against a next_start that does not advance."""
    chunks = TextChunker._split_long_paragraph("." * 3000, 1000, 999)
    assert 0 < len(chunks) < 200


def test_overlap_is_actually_applied():
    """The old max() defeated the overlap it was meant to create."""
    text = " ".join(f"Sentence {i} of the document." for i in range(200))
    chunks = TextChunker._split_long_paragraph(text, 1000, 200)
    assert len(chunks) > 2
    # consecutive chunks should share text
    shared = sum(1 for a, b in zip(chunks, chunks[1:]) if a[-100:].strip()[:40] in b)
    assert shared > 0, "no consecutive chunks overlap"
