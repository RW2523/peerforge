"""
Reviewer agents invented document citations.

Observed live, three six-turn runs against a problem statement with NO
uploaded document — 33 fabricated locators across 18 turns:

    "As noted in the methodology section (p. 12), the authors employed a
     convenience sampling method..."
    "As stated in Section 2.1, 'Participant Selection'..."
    "the authors acknowledge on page 15 that further research is needed"

There was no document. Worse, every reviewer then anchored on the same
invented detail, which is part of why the panel converged on one point.

ROOT CAUSE, a three-link chain:
  _load_material_context() returns "" when a debate has no materials
    -> generate_response(material_context=None)
    -> the `if material_context:` branch is skipped
    -> and that branch held the ONLY anti-fabrication instruction
       ("NEVER invent placeholder citations").

So the rule was sent exactly when a document existed and withheld exactly
when there was nothing to cite — while the rest of the prompt still demanded
"Cite specific methods sections, tables, equations" and referred to "the
paper". With no source and an order to cite, the model invented one.

The corpus in tests/fixtures/fabricated_citations.json is the real output.
"""
import json
import os

import pytest

from src.agent_constitutional_validator import ConstitutionalValidator

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "fabricated_citations.json")


@pytest.fixture(scope="module")
def real_turns():
    with open(FIXTURE) as fh:
        return json.load(fh)["turns"]


@pytest.fixture
def validator():
    return ConstitutionalValidator.__new__(ConstitutionalValidator)


class TestDetector:
    def test_catches_the_real_fabrications(self, validator, real_turns):
        caught = [t for t in real_turns if validator._check_fabricated_citation(t, has_materials=False)]
        assert len(caught) >= 15, (
            f"only {len(caught)}/{len(real_turns)} real fabricating turns flagged"
        )

    def test_silent_when_a_document_actually_exists(self, validator, real_turns):
        """Page verification is not viable — 391 of 398 material chunks in the
        live database carry no page_num — so a locator is only judged
        fabricated when nothing at all was submitted."""
        for t in real_turns:
            assert validator._check_fabricated_citation(t, has_materials=True) is None

    @pytest.mark.parametrize("text", [
        "This aligns with prior work (McKay et al., 2018) on demographic representation.",
        "As Smith 2019 demonstrated, effect sizes shrink under preregistration.",
        "grounding the intervention in Mindfulness-Based Stress Reduction (Kabat-Zinn, 1990)",
        "The problem statement lacks critical details regarding the sampling strategy.",
        "A 6-week intervention is short relative to comparable trials in the field.",
        "Test-retest reliability of the anxiety instrument is never reported.",
        "I recommend Major Revision: the causal claim outruns the design.",
        "What is the null hypothesis, and what significance threshold are the authors using?",
        # An author initial followed by a year reads as "p. 2019" to a
        # case-insensitive page pattern. All three of these would have forced
        # a regeneration on a perfectly legitimate external reference.
        "This builds on (Jones, P. 2019) and later work.",
        "Peterson, A. P. 2019 reports a similar effect in a larger cohort.",
        "See Smith, P. 2019 for the replication attempt.",
        "Kabat-Zinn (1990) defines the construct this intervention borrows.",
    ])
    def test_leaves_legitimate_review_language_alone(self, validator, text):
        """External literature a reviewer genuinely knows is not fabrication,
        and naming a gap is a legitimate review point."""
        assert validator._check_fabricated_citation(text, has_materials=False) is None

    @pytest.mark.parametrize("text", [
        "As noted in the methodology section (p. 12), they used convenience sampling.",
        "The authors state in Section 2.1, 'Participant Selection', that...",
        "the authors acknowledge on page 15 that further research is needed",
        "See Table 3 for the confusion matrix.",
        "Figure 2 shows the effect decaying over time.",
        "Appendix B contains the full protocol.",
        "pp. 4-6 describe the recruitment procedure.",
        "Section 3.2.1 defines the primary outcome.",
    ])
    def test_catches_each_locator_form(self, validator, text):
        assert validator._check_fabricated_citation(text, has_materials=False) is not None

    def test_violation_is_critical_so_it_forces_regeneration(self, validator):
        """`valid` counts only critical violations — a "high" one is recorded
        and then ignored, which is how no_repetition sat inert."""
        v = validator._check_fabricated_citation("See Section 2.1.", has_materials=False)
        assert v["severity"] == "critical"
        assert v["rule"] == "no_fabricated_citation"

    def test_details_name_the_offending_locators(self, validator):
        v = validator._check_fabricated_citation(
            "As noted on p. 12 and in Section 2.1, the sample was small.",
            has_materials=False,
        )
        assert "p. 12" in v["details"] and "Section 2.1" in v["details"]


class TestPromptNoLongerDemandsTheImpossible:
    def test_no_materials_branch_exists(self):
        """The anti-fabrication rule used to live only in the has-materials
        branch — present when a document existed, absent when it did not."""
        import inspect
        from src.agent_response_generator import AgentResponseGenerator

        src = inspect.getsource(AgentResponseGenerator.generate_response)
        assert "NO DOCUMENT HAS BEEN SUBMITTED" in src
        head, _, tail = src.partition("if material_context:")
        assert "else:" in tail, "the no-materials case has no branch at all"

    def test_evidence_requirement_is_conditional(self):
        import inspect
        from src.agent_response_generator import AgentResponseGenerator

        src = inspect.getsource(AgentResponseGenerator._build_system_prompt)
        assert "has_materials" in src
        assert "schema['evidence_req']" not in src, (
            "the role schema's evidence_req demands citing a manuscript; it must "
            "not be issued verbatim when no document was supplied"
        )

    def test_turn_instruction_is_document_aware(self):
        import inspect
        from src import turn_orchestrator

        clause = inspect.getsource(turn_orchestrator._evidence_clause)
        assert "No document was submitted" in clause
        trigger = inspect.getsource(turn_orchestrator.TurnOrchestrator.trigger_next_turn)
        assert "Cite evidence. 150-250 words." not in trigger, (
            "the turn instruction still demands citation unconditionally"
        )

    def test_template_footer_forbids_invented_locators(self):
        from src.agent_templates import ACADEMIC_REVIEW_FOOTER

        # The footer is hard-wrapped, so compare on normalised whitespace.
        flat = " ".join(ACADEMIC_REVIEW_FOOTER.split())
        assert "NEVER invent a page, section, table or figure" in flat
        assert "Cite specific papers, sections, or data points when making claims" \
            not in flat


class TestWiredIntoTheTurn:
    def test_orchestrator_passes_material_availability(self):
        import inspect
        from src import turn_orchestrator

        src = inspect.getsource(turn_orchestrator.TurnOrchestrator._generate_with_constitutional_pipeline)
        assert "has_materials=bool(material_context)" in src

    def test_regeneration_has_constraint_text_for_the_rule(self):
        import inspect
        from src import turn_orchestrator

        src = inspect.getsource(turn_orchestrator.TurnOrchestrator._generate_with_constitutional_pipeline)
        assert "'no_fabricated_citation' in violation_rules" in src

    def test_validator_defaults_to_silent_for_callers_that_do_not_know(self):
        """debate_validator and any other caller must not start flagging."""
        import inspect
        from src.agent_constitutional_validator import ConstitutionalValidator

        sig = inspect.signature(ConstitutionalValidator.validate)
        assert sig.parameters["has_materials"].default is True


class TestStripIsTheFinalBackstop:
    """
    Scoping the strip to the citation rule's own branch was not enough.

    Live adversarial run: turns regenerated for no_repetition, and the RETRY
    introduced "Figure 3" and "Table 2". Nothing re-validates a regenerated
    message, so those reached the transcript while the log showed only a
    repetition violation. The invariant — nothing submitted means no locator
    is published — belongs on the message that actually gets written, not on
    one rule's branch.
    """

    def test_strip_clears_the_entire_real_corpus(self, validator, real_turns):
        total = 0
        for turn in real_turns:
            cleaned, n = ConstitutionalValidator.strip_fabricated_locators(turn)
            total += n
            assert validator._check_fabricated_citation(cleaned, has_materials=False) is None, (
                "a locator survived the strip"
            )
        assert total >= 30, f"expected the corpus's ~33 locators, stripped {total}"

    def test_strip_leaves_external_literature_alone(self):
        text = "This aligns with prior work (McKay et al., 2018) on representation."
        cleaned, n = ConstitutionalValidator.strip_fabricated_locators(text)
        assert n == 0 and cleaned == text

    def test_marker_matches_the_codebase_convention(self):
        """'[source not provided]' is what the grounding prompt already tells
        agents to write, and transcript_quality counts it as a placeholder —
        so a stripped turn stays visible in quality reporting."""
        cleaned, _ = ConstitutionalValidator.strip_fabricated_locators("See Table 3.")
        assert "[source not provided]" in cleaned

        from src.services.transcript_quality import _PLACEHOLDER
        assert _PLACEHOLDER.search(cleaned), (
            "the marker must register as a placeholder in the quality harness"
        )

    def test_adjacent_markers_collapse(self):
        cleaned, n = ConstitutionalValidator.strip_fabricated_locators(
            "As noted in the methodology section (p. 12), the sample was small."
        )
        assert n == 2
        assert "[source not provided] [source not provided]" not in cleaned

    def test_backstop_guards_the_published_message_not_one_rule(self):
        import inspect
        from src import turn_orchestrator

        src = inspect.getsource(
            turn_orchestrator.TurnOrchestrator._generate_with_constitutional_pipeline
        )
        tail = src.split("Complete thinking session")[0]
        assert "strip_fabricated_locators" in tail, (
            "the strip must run on the message that is returned"
        )
        assert "if not material_context:" in tail
        # It must NOT be conditioned on which rule fired — that was the bug.
        strip_call = tail[tail.index("if not material_context:"):]
        assert "violation_rules" not in strip_call.split("strip_fabricated_locators")[0]
