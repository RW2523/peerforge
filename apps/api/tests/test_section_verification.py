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


BARE_NUMBERED = (
    "1 Introduction\n"
    "Exam anxiety affects undergraduates.\n\n"
    "2 Methods\n2.1 Participant Selection\nForty undergraduates were recruited.\n\n"
    "2.2 Measures\nSelf-report at baseline.\n\n"
    "3 Results\nTable 2 reports the means.\n"
)


class TestIndex:
    def test_bare_numbered_headings_count_as_present(self):
        """The document writes "2.1 Participant Selection" without the word
        "Section"; missing those would make a legitimate citation look fake."""
        with _with_doc(STRUCTURED):
            index = LI.build_index("d")
        assert "2.1" in index["section"] and "2.2" in index["section"]

    def test_top_level_headings_with_no_dot_count_as_present(self):
        """THE BUG THIS DESIGN EXISTS TO PREVENT.

        The first version recognised headings via a dotted pattern, so
        "1 Introduction" and "2 Methods" were never indexed — while "2.1" WAS,
        which made the family look populated and turned three of five truthful
        citations into accusations of fabrication. Missing a real fabrication
        costs a citation nobody checks; a false accusation replaces a
        reviewer's correct sentence with a marker saying they invented it.
        """
        with _with_doc(BARE_NUMBERED):
            for truthful in ("Section 1 introduces the problem.",
                             "Section 2 describes the methods.",
                             "Section 2.1 covers recruitment.",
                             "Section 3 reports results.",
                             "Table 2 has the means."):
                assert LI.find_absent_locators("d", truthful) == [], (
                    f"false accusation on a truthful citation: {truthful}"
                )

    def test_still_catches_fabrication_in_a_bare_numbered_document(self):
        with _with_doc(BARE_NUMBERED):
            assert LI.find_absent_locators("d", "Section 9 is about ethics.")
            assert LI.find_absent_locators("d", "Table 7 lists the cohort.")

    def test_reported_set_lists_only_explicit_headings(self):
        """The presence pool is deliberately generous — every standalone number
        in the text. Enumerating THAT in the violation told the model the paper
        "has: 1, 1.31, 12.4, 40", which invites the retry to cite Section 40.
        The message must name only what the document explicitly labels."""
        doc = (
            "Section 1. Introduction\nSection 2. Methods\n"
            "2.1 Participant Selection. Forty (40) undergraduates.\n"
            "Section 3. Results\nThe arm fell 12.4 points (d = 1.31).\n"
            "Table 1 reports means.\n"
        )
        with _with_doc(doc):
            out = LI.find_absent_locators("d", "As stated in Section 9, allocation was concealed.")
        assert out and out[0]["cited"] == "9"
        assert set(out[0]["present"]) <= {"1", "2", "2.1", "3"}
        assert "40" not in out[0]["present"] and "12.4" not in out[0]["present"]

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
    The obvious way this feature goes wrong: document text lost in chunking,
    so a real citation reads as fabricated. Verified against the real chunker
    rather than assumed — see test_chunking_coverage.py for the data-loss bug
    this exposed.
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

        with _with_doc(joined):
            for i in range(1, 13):
                for cite in (f"Section {i} says so.", f"Section {i}.1 says so."):
                    assert LI.find_absent_locators("d", cite) == [], (
                        f"chunking lost structure: {cite}"
                    )
            for cite in ("Table 1 reports the means.", "Table 2 reports the variances."):
                assert LI.find_absent_locators("d", cite) == []

    def test_a_table_block_paragraph_does_not_lose_its_heading(self):
        """The chunker dropped 198 chars of this shape, heading included."""
        from src.utils.chunking import TextChunker

        doc = "a" * 600 + ". " + "Section 7 Data Analysis " + "b" * 380 + "c" * 900
        chunks = TextChunker.chunk_text(doc, "mat-x", {})
        joined = "\n".join(c["chunk_text"] for c in chunks)

        with _with_doc(joined):
            assert LI.find_absent_locators("d", "Section 7 covers the analysis.") == []


class TestTrailingPeriodBlindSpot:
    """
    A live end-to-end run marked a TRUTHFUL citation as fabricated.

    _STANDALONE_NUMBER ended in (?![\\d.]), which rejects a trailing full stop.
    A document that writes its headings as "Section 3. Results" therefore
    registered neither 3 nor 4, and a reviewer citing Section 4 was told it is
    "[not in the submitted document]" — the exact false accusation the
    three-valued design exists to prevent.

    The same lookahead bug had been fixed in strip_contradicted_locators hours
    earlier and was not checked here.
    """

    DOC = (
        "Section 1. Introduction\n"
        "Section 2. Methods\n"
        "2.1 Participant Selection. Forty undergraduates.\n"
        "Section 3. Results\nTable 1 reports means.\n"
        "Section 4. Discussion\n"
    )

    def test_headings_written_with_a_trailing_period_are_indexed(self):
        with _with_doc(self.DOC):
            sections = LI.build_index("d")["section"]
        for n in ("1", "2", "3", "4", "2.1"):
            assert n in sections, f"Section {n}. was not indexed"

    @pytest.mark.parametrize("text", [
        "The claim in Section 4 that the app causes a durable reduction is overstated.",
        "As noted in Section 3, the effect was large.",
        "Section 2.1 describes recruitment.",
        "Table 1 reports the means.",
    ])
    def test_truthful_citations_are_not_accused(self, text):
        with _with_doc(self.DOC):
            assert LI.find_absent_locators("d", text) == [], text

    @pytest.mark.parametrize("text", [
        "Section 9 does not exist.",
        "Table 7 shows nothing.",
    ])
    def test_fabrications_are_still_caught(self, text):
        with _with_doc(self.DOC):
            assert LI.find_absent_locators("d", text) != [], text
