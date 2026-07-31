"""The regression detector for review quality.

The fixtures are shortened from real transcripts this project produced before
and after the persona-lane fix, so the thresholds are calibrated against
behaviour that actually occurred rather than a guess.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.transcript_quality import (
    Thresholds,
    Turn,
    analyse,
    turns_from_events,
)

# Every reviewer opened by endorsing the last one and asked the same
# "falsification challenge" — the signature of all lanes collapsing to one.
COLLAPSED = [
    Turn('Dr. Ada', 'The central claim rests on an unvalidated assumption of '
                    'environmental stability. Here is my falsification challenge: '
                    'what result would make you abandon it?', 'skeptical reviewer'),
    Turn('Dr. Ben', '@"Dr. Ada" is entirely correct to call out the lack of '
                    'empirical fault injection. Here is my falsification challenge: '
                    'what evidence would refute the stability claim?', 'skeptical reviewer'),
    Turn('Dr. Cleo', '@"Dr. Ada" and @"Dr. Ben" are completely right to tear into '
                     'the evaluation. Here is my falsification challenge: what '
                     'outcome would invalidate the stability claim?', 'skeptical reviewer'),
    Turn('Dr. Ada', '@"Dr. Ben" and @"Dr. Cleo" are entirely right about the sample '
                    'size. Here is my falsification challenge: what result would '
                    'overturn the stability assumption?', 'skeptical reviewer'),
]

# Distinct lanes: sampling, prior work, and clarity respectively.
DIFFERENTIATED = [
    Turn('Dr. Ada', 'Training on 412 structures without cross-validation cannot '
                    'support the variance claim in Section 4. A single seed makes '
                    'the reported margin uninterpretable.', 'methodology professor'),
    Turn('Dr. Ben', 'Jumper et al. (2021) already addressed this folding regime; '
                    'the manuscript never positions itself against that literature, '
                    'so the novelty claim is unsupported.', 'domain expert'),
    Turn('Dr. Cleo', 'The abstract promises a general method but Section 2 quietly '
                     'narrows it to one protein family. A reader would not notice '
                     'that shift — rewrite the opening sentence.', 'friendly professor'),
]


def test_collapsed_panel_is_reported_as_a_failure():
    """The exact regression this harness exists to catch."""
    report = analyse(COLLAPSED)
    failures = report.failures(Thresholds())

    assert failures, 'a panel where every reviewer endorses the last must fail'
    assert report.opener_template_rate >= 0.9
    assert any('endorsing' in f for f in failures)


def test_a_differentiated_panel_passes():
    report = analyse(DIFFERENTIATED)
    assert report.failures(Thresholds()) == []
    assert report.opener_template_rate == 0.0


def test_leaked_prompt_scaffolding_is_surfaced():
    """Phrases the prompt told agents to use, echoed verbatim every turn."""
    phrases = analyse(COLLAPSED).repeated_phrases
    assert any('falsification challenge' in p for p in phrases), phrases


def test_role_differentiation_ignores_shared_lanes():
    """Two reviewers in one lane are meant to overlap; that is not a defect."""
    same_lane = [
        Turn('A', 'The sample size cannot support this variance claim.', 'methodology professor'),
        Turn('B', 'The sample size cannot support this variance claim.', 'methodology professor'),
    ]
    # One distinct role means there is nothing to differentiate between.
    assert analyse(same_lane).role_differentiation == 1.0


def test_placeholder_names_and_invented_citations_are_caught():
    leaky = [
        Turn('A', 'As @Name argued, the result is unclear (Author, URL).', 'advisor'),
        Turn('B', 'I agree with the point about scope [source not provided].', 'domain expert'),
    ]
    report = analyse(leaky)
    assert report.placeholder_rate == 1.0
    assert any('placeholder' in f for f in report.failures(Thresholds()))


def test_grounding_is_measured():
    grounded = analyse(DIFFERENTIATED).grounding_rate
    ungrounded = analyse([
        Turn('A', 'This work feels underdeveloped and needs more rigour.', 'advisor'),
        Turn('B', 'I share those concerns about the overall approach.', 'domain expert'),
    ]).grounding_rate
    assert grounded > ungrounded


@pytest.mark.parametrize('turns', [[], [Turn('A', 'Only one turn.', 'advisor')]])
def test_degenerate_transcripts_do_not_raise(turns):
    """A session with nothing in it is not a quality failure."""
    report = analyse(turns)
    assert report.failures(Thresholds()) == []


def test_events_are_converted_to_turns():
    events = [
        {'event_type': 'agent_message',
         'content': {'message': 'A methodological concern.', 'agent_name': 'Dr. Ada'}},
        {'event_type': 'agent_thinking', 'content': {'message': 'ignored'}},
        {'event_type': 'agent_message',
         'content': {'message': 'A different concern.', 'agent_name': 'Dr. Ben'}},
    ]
    turns = turns_from_events(events)
    assert [t.speaker for t in turns] == ['Dr. Ada', 'Dr. Ben']
