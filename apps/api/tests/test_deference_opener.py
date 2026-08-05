"""
Opening by positioning against the other reviewers instead of leading with
your own point.

Removing the mandated final-turn sentence did not remove the habit, it moved
it. The next live session had five of six turns opening

    @"Dr. Ada" and @"Dr. Lee," while I acknowledge ...

and _AGREEMENT_OPENER — built for "X is correct" — scored that at 0.00.

The pattern below is fitted to 46 openers labelled from real transcripts, at
full recall and precision. It is shared between the live constitutional guard
and the offline harness so both agree on what deference looks like.

The distinction that matters: naming someone and then making a CLAIM is
engagement and is wanted. '@"Dr. Ada" is wrong about the effect size: d =
1.31 is not credible with n = 40' must not match. Naming someone and then
conceding is what replaces the review.
"""
import pytest

from src.agent_constitutional_validator import ConstitutionalValidator
from src.services.transcript_quality import _DEFERENCE_OPENER, Thresholds, Turn, analyse

DEFERENCE = [
    '@"Dr. Ada," while the findings are promising, we must critically examine the design.',
    '@"Dr. Ada" and @"Dr. Lee," while I acknowledge the results, the methodology is weak.',
    '@"Dr. Lee" and @"Mr. Sam," you both raised valid concerns, but statistical rigor matters.',
    '@"Dr. Ada" and @"Dr. Lee," I appreciate the focus on rigor, but clarity is lacking.',
    # Unquoted, with a space — the form a naive character class misses.
    '@Dr. Ada, while the findings on the six-week programme are promising, there is more.',
    '@Dr. Lee, I see your point regarding comparison, but I want to challenge the premise.',
    '@"Dr. Lee", your critique regarding the lack of a comparative intervention is valid; however,',
    "@\"Dr. Ada\", you're correct in emphasizing the null hypothesis, yet the power is unreported.",
    # Nominalisation of the debate itself.
    "The critique regarding convenience sampling in Prof. Adeyemi's review highlights a concern.",
    'The concerns raised by Prof. Adeyemi regarding sampling are indeed valid, as noted above.',
    'The ongoing discussion about the lack of a robust control group misses a further point.',
    'The conversation has veered into critical territory, but both reviewers are missing this.',
    # Nameless second person.
    "You both raise valid concerns, but let's dig deeper into the methodology and sample size.",
    'You all make good points, though the allocation problem is more serious than any of them.',
    'That is a fair point about timing, but the reliability question is unresolved.',
    # Explicit formulas.
    'Building on what my colleagues have said, the sample size is inadequate for this claim.',
    'I agree with the points raised so far, but there is another issue worth naming here.',
]

SUBSTANTIVE = [
    'The methodology employed in this study is fundamentally flawed due to inadequate sampling.',
    'The absence of a robust control group significantly undermines the causal claims made.',
    'Test-retest reliability of the anxiety instrument is never reported anywhere.',
    'No preregistration means the primary outcome could have been chosen after seeing the data.',
    'Allocation was performed by the first author, who also delivered the intervention.',
    # Naming someone and then making a claim is ENGAGEMENT — deliberately allowed.
    '@"Dr. Ada" is wrong about the effect size: d = 1.31 is not credible with n = 40.',
    '@Dr. Ada, your effect size is not credible: d = 1.31 with n = 40 and no blinding.',
    '@Dr. Lee, the study never reports test-retest reliability, which undercuts your reading.',
    'You both misread the effect size: d = 1.31 with n = 40 is not credible.',
    'You are wrong that the waitlist controls for expectancy — it does not.',
    "You're overstating the novelty of this work. Similar interventions exist in the literature.",
    'Section 2.1 says allocation was by coin flip performed by the first author.',
]


@pytest.mark.parametrize("text", DEFERENCE)
def test_deference_openers_are_detected(text):
    assert _DEFERENCE_OPENER.search(text) is not None, text


@pytest.mark.parametrize("text", SUBSTANTIVE)
def test_substantive_openers_are_left_alone(text):
    assert _DEFERENCE_OPENER.search(text) is None, text


class TestValidatorRule:
    def _v(self):
        return ConstitutionalValidator.__new__(ConstitutionalValidator)

    def test_violation_is_critical(self):
        out = self._v()._check_deference_opener(DEFERENCE[0], anyone_has_spoken=True)
        assert out["severity"] == "critical"
        assert out["rule"] == "no_deference_opener"

    def test_first_speaker_is_exempt(self):
        """Nobody to defer to on the opening turn."""
        assert self._v()._check_deference_opener(DEFERENCE[0], anyone_has_spoken=False) is None

    def test_details_quote_the_offending_opener(self):
        out = self._v()._check_deference_opener(DEFERENCE[0], anyone_has_spoken=True)
        assert "Dr. Ada" in out["details"]


class TestHarnessCountsIt:
    def test_opener_rate_reflects_deference(self):
        turns = [Turn(speaker=f"R{i%3}", text=t) for i, t in enumerate(DEFERENCE[:6])]
        r = analyse(turns)
        assert r.opener_template_rate > Thresholds().max_opener_template_rate

    def test_substantive_turns_score_zero(self):
        turns = [Turn(speaker=f"R{i%3}", text=t) for i, t in enumerate(SUBSTANTIVE[:6])]
        assert analyse(turns).opener_template_rate == 0.0


class TestRetryIsRevalidated:
    """
    The rule fired correctly and the output was wrong anyway, because the
    turns that deferred were REGENERATED messages and nothing re-checked a
    retry. The same gap produced three separate bugs: a retry introducing
    "Figure 3"/"Table 2", a retry re-citing a missing section, and a retry
    opening with deference under a log line that mentioned only repetition.
    """

    def test_regeneration_is_rechecked(self):
        import inspect
        from src import turn_orchestrator

        src = inspect.getsource(
            turn_orchestrator.TurnOrchestrator._generate_with_constitutional_pipeline
        )
        after_retry = src.split("Fallback: Use legacy approach")[1]
        assert "recheck" in after_retry
        assert "Regeneration still violates" in after_retry

    def test_second_attempt_is_bounded_and_only_kept_if_better(self):
        import inspect
        from src import turn_orchestrator

        src = inspect.getsource(
            turn_orchestrator.TurnOrchestrator._generate_with_constitutional_pipeline
        )
        assert "n_after < len(still_bad)" in src, (
            "a worse second attempt must not replace the first"
        )
        assert src.count("one more attempt") == 1, "exactly one extra attempt"


class TestStructuralBranch:
    """
    The word list kept needing another entry.

    "while" -> "you're correct" -> "I see your point" -> "you're highlighting",
    each one found by running a session and each costing a round trip. The
    shape underneath never changed: name the reviewer, restate what they said,
    pivot to your own point. Branch (d) matches the shape instead of the
    vocabulary.

    A rebuttal also names someone and may contain "but", so an opener that
    disagrees BEFORE the pivot is excluded — and only markers aimed at the
    other reviewer count. An earlier attempt treated generic words about the
    paper ("lack", "absent", "fails") as rebuttal and silently lost seven
    true positives, because conceding about the paper is exactly what a
    deference opener does.
    """

    NOVEL_CONCESSIONS = [
        # The phrasing that slipped the word list in a live run.
        '@"Dr. Sarah", you\'re highlighting the significant reduction in anxiety, but I\'m concerned about self-report bias.',
        '@Dr. Lee, you note the effect size is large, but the design cannot support a causal reading of it.',
        '@Dr. Ada, your framing of the power question is helpful, but it sidesteps the allocation problem.',
        '@Dr. Ada, your emphasis on blinding is well taken, however the sample size is the deeper issue.',
        '@Dr. Lee and @Dr. Ada, your points about measurement land, yet neither addresses attrition.',
    ]

    REBUTTALS = [
        '@Dr. Ada, you are wrong about the effect size, but I will grant the write-up is clear.',
        '@Dr. Lee, that reading misreads the table, but the deeper issue is the missing control.',
        '@Dr. Ada, I disagree with your reading of Table 1, but the sample size worries me more.',
        '@Dr. Ada, your claim is not credible given n = 40, but the framing is at least honest.',
    ]

    # Observed live: addressing the panel while ASSERTING, not conceding.
    CHALLENGES = [
        "You're both fixating too much on the surface outcomes without questioning the foundations.",
        "You're both missing a critical aspect of this study: the originality of the contribution.",
    ]

    @pytest.mark.parametrize("text", NOVEL_CONCESSIONS)
    def test_catches_concessions_the_word_list_never_saw(self, text):
        assert _DEFERENCE_OPENER.search(text) is not None, text

    @pytest.mark.parametrize("text", REBUTTALS)
    def test_a_rebuttal_containing_but_is_not_deference(self, text):
        assert _DEFERENCE_OPENER.search(text) is None, text

    @pytest.mark.parametrize("text", CHALLENGES)
    def test_challenging_the_panel_is_not_deference(self, text):
        assert _DEFERENCE_OPENER.search(text) is None, text

    def test_a_pivot_far_past_the_opening_does_not_count(self):
        """Only the opening is judged; a "but" in the third sentence is
        ordinary prose."""
        text = ("@Dr. Ada, the allocation was performed by the first author who also "
                "delivered the intervention, which is a concealment failure on its own terms. "
                + ("Filler sentence about the design. " * 6) + "but that is secondary.")
        assert _DEFERENCE_OPENER.search(text) is None

    def test_no_name_no_structural_match(self):
        assert _DEFERENCE_OPENER.search("The design cannot support causal claims, but the write-up is clear.") is None

    def test_the_word_list_branches_still_work(self):
        """Branch (d) supplements the lists; it must not have replaced them."""
        assert _DEFERENCE_OPENER.search('@"Dr. Ada," while I acknowledge the results, the design is weak.') is not None
        assert _DEFERENCE_OPENER.search('The concerns raised by Prof. Adeyemi are indeed valid, as noted.') is not None
        assert _DEFERENCE_OPENER.search('You both raise valid concerns, but the sample size matters more.') is not None
