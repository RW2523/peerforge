"""
The quality harness passed the transcript it exists to catch.

Six reviewers made the identical point about convenience sampling and it
scored 0.35 self_similarity against a 0.45 limit — a clean pass. The metric
was the problem, not just the threshold: self_similarity is pairwise Jaccard
on consecutive turns, so six reviewers saying ONE thing in different words
score LOW on it, and Jaccard's union denominator rewards padding.

restatement_rate measures containment against the shorter side, over every
earlier turn — the same measure the live repetition guard uses. On four real
transcripts it separates cleanly where the others barely do:

                          bad          good
    restatement_rate      0.80-1.00    0.00-0.20
    self_similarity       0.19-0.35    0.13-0.14
    role_differentiation  0.65-0.75    0.81-0.83
"""
import pytest

from src.services.transcript_quality import Thresholds, Turn, analyse

RESTATEMENT = (
    "The reliance on convenience sampling in this study fundamentally "
    "undermines its external validity and raises significant concerns "
    "regarding bias. The authors used a convenience sample drawn mainly "
    "from a single demographic group, which limits representativeness."
)
PARAPHRASES = [
    RESTATEMENT,
    "The study's reliance on convenience sampling poses serious concerns that "
    "compromise external validity. The sample was predominantly from a "
    "singular demographic group, introducing significant bias and limiting "
    "how far the findings generalise.",
    "Convenience sampling fundamentally weakens this work: drawing "
    "predominantly from one demographic group introduces bias and constrains "
    "the external validity of every conclusion the authors reach.",
]
DISTINCT = [
    "The instrument's test-retest reliability is never reported, so we cannot "
    "tell whether the null result reflects the intervention or measurement noise.",
    "No preregistration means the primary outcome could have been chosen after "
    "seeing the data; a large effect is consistent with optional stopping.",
    "Six weeks cannot distinguish durable change from the relief of finishing "
    "the semester, and there is no follow-up measurement to separate them.",
]


def _report(texts):
    return analyse([Turn(speaker=f"R{i}", text=t) for i, t in enumerate(texts)])


class TestRestatementRate:
    def test_paraphrases_of_one_point_are_caught(self):
        r = _report(PARAPHRASES)
        assert r.restatement_rate >= 0.5, (
            f"three paraphrases of one point scored {r.restatement_rate}"
        )
        assert r.failures(Thresholds()), "a panel making one point must not pass"

    def test_distinct_critiques_pass(self):
        r = _report(DISTINCT)
        assert r.restatement_rate == 0.0
        assert not r.failures(Thresholds())

    def test_it_catches_what_self_similarity_misses(self):
        """The whole reason the metric exists: vocabulary overlap alone rated
        the paraphrase set as acceptable."""
        r = _report(PARAPHRASES)
        assert r.restatement_rate > r.self_similarity

    def test_single_turn_transcript_is_not_divided_by_zero(self):
        assert _report(["Only one turn here, nothing to restate."]).restatement_rate == 0.0

    def test_empty_transcript_is_safe(self):
        assert analyse([]).restatement_rate == 0.0


class TestOnlyDiscriminatingMetricsGate:
    """
    Re-measured across TEN real transcripts, labelled by the metrics that do
    discriminate, self_similarity and role_differentiation overlap completely
    between good and bad:

        self_similarity       bad 0.132-0.346   good 0.143-0.174
        role_differentiation  bad 0.649-0.832   good 0.758-0.808

    The worst transcript scored the LOWEST self_similarity and the HIGHEST
    role_differentiation, because six reviewers restating one point in
    different words look lexically diverse. An earlier calibration fitted to
    four transcripts enforced both and failed the cleanest session measured.
    """

    def test_restatement_limit_sits_in_the_measured_gap(self):
        t = Thresholds()
        assert 0.20 < t.max_restatement_rate < 0.80

    def test_self_similarity_does_not_fail_a_transcript(self):
        r = _report(DISTINCT)
        r.self_similarity = 0.99
        assert not r.failures(Thresholds()), (
            "self_similarity must be reported, not enforced"
        )

    def test_role_differentiation_does_not_fail_a_transcript(self):
        r = _report(DISTINCT)
        r.role_differentiation = 0.0
        assert not r.failures(Thresholds())

    def test_the_two_gates_still_fail_a_bad_transcript(self):
        r = _report(PARAPHRASES)
        assert r.failures(Thresholds())


class TestFinalTurnIsNotTemplated:
    """
    The final-turn instruction mandated a verbatim opening:

        "Given this is my final turn (Round N/N), I'll conclude by stating my
         decision: ..."

    Every reviewer reaches a final turn, so the closing round read as one
    voice repeated three times. A live end-to-end session scored 100%
    restatement largely because of it.
    """

    def test_no_verbatim_opening_is_mandated(self):
        import inspect
        from src import turn_orchestrator

        src = inspect.getsource(turn_orchestrator.TurnOrchestrator.trigger_next_turn)
        assert "MANDATORY FORMAT" not in src
        assert "Given this is my final turn" not in src

    def test_it_still_demands_a_definitive_verdict(self):
        import inspect
        from src import turn_orchestrator

        src = inspect.getsource(turn_orchestrator.TurnOrchestrator.trigger_next_turn)
        assert "Accept / Minor Revision / Major Revision / Reject" in src

    def test_the_generic_debate_examples_are_gone(self):
        """Leftovers from a non-academic app: "Coffee is superior",
        "@ExpertAnalyst"."""
        import inspect
        from src import turn_orchestrator

        src = inspect.getsource(turn_orchestrator.TurnOrchestrator.trigger_next_turn)
        assert "Coffee is superior" not in src
        assert "ExpertAnalyst" not in src
