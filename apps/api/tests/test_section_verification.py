"""
Citing part of a document that does not exist in it.

The no-materials rule cannot catch this: a document DOES exist, so every
locator in the message is plausible. Observed live — a reviewer cited
"Section 2.3" of a paper whose sections are 1, 2, 2.1, 2.2, 3 and 4.

Verification is THREE-VALUED, because absence of evidence is weak evidence
of absence:

    verified      the locator appears in the extracted document
    absent        the document has locators of that family but not this one
                  — the only verdict acted on
    unverifiable  the document has no locator of that family at all, so
                  extraction may have dropped the structure. Stay silent.

It reads memory_chunks, not the prompt's material context: that context is
truncated (449 chars from an 812-byte upload), so absence from it proves
nothing.
"""
from unittest.mock import patch

import pytest

from src.agent_constitutional_validator import ConstitutionalValidator
from src.services import locator_index as LI

STRUCTURED = (
    "Section 1. Introduction\n"
    "Section 2. Methods\n"
    "2.1 Participant Selection. Forty undergraduates.\n"
    "2.2 Measures. Self-report at baseline and week six.\n"
    "Section 3. Results\nTable 1 reports means.\n"
    "Section 4. Discussion\n"
)
PROSE = "A brief describing a mindfulness trial with forty undergraduates and no active control."


@pytest.fixture(autouse=True)
def _clear():
    LI.clear_cache()
    yield
    LI.clear_cache()


def _with_doc(text):
    return patch.object(LI, "_chunk_text_for", lambda debate_id: (text, 1))


class TestIndex:
    def test_bare_numbered_headings_count_as_present(self):
        """The document writes "2.1 Participant Selection" without the word
        "Section"; missing those would make a legitimate citation look fake."""
        with _with_doc(STRUCTURED):
            index = LI.build_index("d")
        assert "2.1" in index["section"] and "2.2" in index["section"]

    def test_families_absent_from_the_document_stay_empty(self):
        with _with_doc(STRUCTURED):
            index = LI.build_index("d")
        assert index["figure"] == set()

    def test_pages_are_never_indexed(self):
        """391 of 398 live chunks carry no page_num, so there is no page
        structure to verify against and any page verdict would be noise."""
        assert "page" not in LI._FAMILY_PATTERNS


class TestVerdicts:
    def test_absent_member_of_a_present_family_is_flagged(self):
        with _with_doc(STRUCTURED):
            out = LI.find_absent_locators("d", "As stated in Section 2.3, allocation was concealed.")
        assert len(out) == 1
        assert out[0]["cited"] == "2.3"
        assert "2.1" in out[0]["present"]

    def test_a_real_citation_passes(self):
        with _with_doc(STRUCTURED):
            assert LI.find_absent_locators("d", "Section 2.1 describes recruitment.") == []
            assert LI.find_absent_locators("d", "Table 1 reports the means.") == []

    def test_missing_family_is_unverifiable_not_fabricated(self):
        """The document has no figures. Extraction may have dropped them —
        that must not read as the reviewer lying."""
        with _with_doc(STRUCTURED):
            assert LI.find_absent_locators("d", "Figure 3 shows the decay.") == []

    def test_unstructured_document_verifies_nothing(self):
        with _with_doc(PROSE):
            assert LI.find_absent_locators("d", "Section 2.1 and Table 6 both matter.") == []

    def test_verification_failure_never_fails_the_turn(self):
        def boom(debate_id):
            raise RuntimeError("db down")

        with patch.object(LI, "_chunk_text_for", boom):
            assert LI.find_absent_locators("d", "Section 99 says so.") == []

    def test_cache_notices_a_mid_session_upload(self):
        calls = {"n": 0}

        def counted(debate_id):
            calls["n"] += 1
            return (STRUCTURED, calls["n"])  # chunk count changes each call

        with patch.object(LI, "_chunk_text_for", counted):
            LI.build_index("d")
            LI.build_index("d")
        assert calls["n"] == 2, "a changed chunk count must rebuild the index"


class TestValidatorRule:
    def test_violation_is_critical(self):
        v = ConstitutionalValidator.__new__(ConstitutionalValidator)
        out = v._check_contradicted_citation(
            [{"family": "section", "cited": "2.3", "present": ["1", "2", "2.1"]}]
        )
        assert out["severity"] == "critical"
        assert out["rule"] == "no_contradicted_citation"
        assert "2.3" in out["details"] and "2.1" in out["details"]

    def test_silent_with_nothing_absent(self):
        v = ConstitutionalValidator.__new__(ConstitutionalValidator)
        assert v._check_contradicted_citation([]) is None
        assert v._check_contradicted_citation(None) is None


class TestTargetedStrip:
    """Unlike the no-materials strip, this must leave real citations alone."""

    ABSENT = [
        {"family": "section", "cited": "2.3", "present": ["1", "2", "2.1", "2.2"]},
        {"family": "table", "cited": "5", "present": ["1"]},
    ]

    def test_marks_only_the_contradicted_ones(self):
        text, n = ConstitutionalValidator.strip_contradicted_locators(
            "Section 2.1 covers recruitment; Section 2.3 covers concealment; "
            "Table 1 has means but Table 5 has the effect.",
            self.ABSENT,
        )
        assert n == 2
        assert "Section 2.1" in text and "Table 1" in text
        assert "Section 2.3" not in text and "Table 5" not in text
        assert text.count("[not in the submitted document]") == 2

    def test_matches_a_sentence_ending_locator(self):
        """(?![\\d.]) rejected the trailing full stop, and two contradicted
        citations survived a live run because of it."""
        text, n = ConstitutionalValidator.strip_contradicted_locators(
            "which should be detailed in Section 2.3. Additionally, the data...",
            self.ABSENT,
        )
        assert n == 1
        assert "Section 2.3" not in text

    def test_does_not_match_a_longer_number(self):
        text, n = ConstitutionalValidator.strip_contradicted_locators(
            "See Section 2.31 for detail.", self.ABSENT
        )
        assert n == 0 and "Section 2.31" in text

    def test_no_op_without_absent_locators(self):
        msg = "Section 2.1 covers recruitment."
        assert ConstitutionalValidator.strip_contradicted_locators(msg, []) == (msg, 0)


class TestWiredIntoTheTurn:
    def test_orchestrator_computes_and_passes_the_verdict(self):
        import inspect
        from src import turn_orchestrator

        src = inspect.getsource(turn_orchestrator.TurnOrchestrator._generate_with_constitutional_pipeline)
        assert "absent_locators=_absent_locators(" in src

    def test_backstop_runs_on_the_published_message(self):
        """Nothing re-validates a regenerated message: without this the rule
        fired on all four turns of a live run and all eleven bad citations
        were published regardless."""
        import inspect
        from src import turn_orchestrator

        src = inspect.getsource(turn_orchestrator.TurnOrchestrator._generate_with_constitutional_pipeline)
        tail = src.split("Complete thinking session")[0]
        assert "strip_contradicted_locators" in tail

    def test_regeneration_has_constraint_text(self):
        import inspect
        from src import turn_orchestrator

        src = inspect.getsource(turn_orchestrator.TurnOrchestrator._generate_with_constitutional_pipeline)
        assert "'no_contradicted_citation' in violation_rules" in src


class TestChunkBoundariesDoNotCreateFalsePositives:
    """
    The obvious way this feature goes wrong: a heading split across two chunks
    so neither contains it whole, making a legitimate citation read as
    fabricated. TextChunker is paragraph-aware with a 200-char overlap, which
    should prevent it — verified here rather than assumed.
    """

    def test_headings_survive_many_chunk_boundaries(self):
        from src.utils.chunking import TextChunker

        doc = "\n\n".join(
            f"Section {i}. Heading {i}\n{i}.1 Subheading\n"
            + ("Filler sentence about the study design. " * 12)
            for i in range(1, 13)
        ) + "\n\nTable 1 reports the means.\n\nTable 2 reports the variances.\n"

        chunks = TextChunker.chunk_text(doc, "mat-x", {})
        assert len(chunks) > 5, "test needs several boundaries to be meaningful"

        joined = "\n".join(c["chunk_text"] for c in chunks)
        found = {m.lower() for m in LI._FAMILY_PATTERNS["section"].findall(joined)}
        found |= {m.lower() for m in LI._BARE_HEADING.findall(joined)}

        expected = {str(i) for i in range(1, 13)} | {f"{i}.1" for i in range(1, 13)}
        assert expected <= found, f"headings lost at chunk boundaries: {sorted(expected - found)}"

        tables = {m.lower() for m in LI._FAMILY_PATTERNS["table"].findall(joined)}
        assert tables == {"1", "2"}
