"""Defects a six-journey walk of the running app turned up.

Grouped here because they share a cause rather than a module: something failed
in a way the user could not see. A pipeline degraded silently, a delete
committed before validation, a malformed id became a 500 carrying the Postgres
error, a metric reported soundness it had never checked.
"""
import os
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.main import app
from src.database import get_db_connection, get_cursor

client = TestClient(app)
WS = '00000000-0000-0000-0000-000000000101'


def _debate(title='Sweep regression'):
    r = client.post('/debates', json={'workspace_id': WS, 'title': title})
    assert r.status_code in (200, 201), r.text
    return r.json()['debate_id']


# ── The constitutional pipeline ─────────────────────────────────────────────

def test_round_instruction_survives_a_session_with_no_round_limit():
    """
    A session created without a policy carries max_rounds = None.

    Comparing that to an int raised on EVERY turn, and the caller wrapped the
    whole three-stage pipeline in a bare except — so the product's core
    reasoning silently degraded to one plain LLM call for every review it has
    ever produced, and the log said only 'pipeline error'.
    """
    from src.agent_response_generator import _round_instruction

    for current, maximum in [(None, None), (1, None), (None, 3), (1, 1)]:
        text = _round_instruction(current, maximum)
        assert isinstance(text, str) and text, f'{current}/{maximum} produced nothing'

    # The normal path still differentiates rounds.
    assert 'ROUND 1' in _round_instruction(1, 3)
    assert 'FINAL' in _round_instruction(3, 3)


def test_turn_info_defaults_apply_when_the_key_holds_none():
    """
    `.get("max_rounds", 1)` returns None when the key exists with value None,
    so the default never applied — which is how the None reached the compare.
    """
    turn_info = {'current_round': None, 'max_rounds': None}
    assert (turn_info.get('current_round') or 1) == 1
    assert (turn_info.get('max_rounds') or 1) == 1


# ── Malformed input ─────────────────────────────────────────────────────────

@pytest.mark.parametrize('path', [
    '/debates/not-a-uuid',
    '/debates/12345',
    '/debates/abc-def-ghi',
])
def test_a_mistyped_id_is_not_a_server_error(path):
    """
    Eighty-odd routes hand debate_id straight to Postgres. One wrong character
    returned a 500 whose body was the raw Postgres error.
    """
    r = client.get(path)
    assert r.status_code in (404, 422), f'{path} -> {r.status_code} {r.text[:200]}'
    assert 'psycopg2' not in r.text
    assert 'invalid input syntax' not in r.text


def test_an_over_long_title_is_rejected_readably():
    """A title longer than the column returned a 500 that leaked the schema."""
    r = client.post('/debates', json={'workspace_id': WS, 'title': 'x' * 5000})
    assert r.status_code == 422, f'-> {r.status_code} {r.text[:200]}'
    assert 'psycopg2' not in r.text


def test_database_errors_never_leak_their_text():
    """Postgres errors name tables, columns and constraints."""
    r = client.get(f'/debates/{"z" * 40}')
    assert r.status_code in (404, 422)
    for leak in ('relation', 'column', 'psycopg2', 'DETAIL'):
        assert leak not in r.text, f'leaked {leak!r}'


# ── Materials ───────────────────────────────────────────────────────────────

def test_an_unusable_payload_changes_nothing():
    """
    This endpoint replaces the existing materials. It used to delete them and
    commit that delete before looking at the payload, so a request carrying
    nothing usable destroyed saved work and answered with a bare 500.
    """
    debate_id = _debate()
    r = client.post(f'/debates/{debate_id}/materials', json={
        'materials': [{'kind': 'text', 'title': 'Keep me', 'body_text': 'Original content.'}]
    })
    assert r.status_code == 200, r.text

    # A payload with nothing usable in it.
    r = client.post(f'/debates/{debate_id}/materials', json={
        'materials': [{'kind': 'text', 'title': 'empty', 'body_text': '   '}]
    })
    assert r.status_code == 400, f'-> {r.status_code} {r.text[:200]}'
    assert 'Nothing was changed' in r.json()['detail']

    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            "SELECT COUNT(*) AS n FROM meeting_materials WHERE debate_id = %s AND kind = 'text'",
            (debate_id,),
        )
        assert cur.fetchone()['n'] == 1, 'the original material was destroyed'


def test_an_unrecognised_kind_is_refused_rather_than_stranded():
    """
    Any kind was accepted, stored, never chunked, and sat at 'pending' forever
    — after the delete had already run.
    """
    debate_id = _debate()
    r = client.post(f'/debates/{debate_id}/materials', json={
        'materials': [{'kind': 'video', 'title': 'v', 'body_text': 'x'}]
    })
    assert r.status_code == 422, f'-> {r.status_code} {r.text[:200]}'


# ── Lifecycle responses ─────────────────────────────────────────────────────

def test_start_reports_the_panel_it_actually_has():
    """
    start/pause/resume/end each built a five-field response by hand, so the
    schema's defaults serialised participants:[] and policy_config:null — the
    opposite of the truth, and contradicting GET for the same id.
    """
    debate_id = _debate()
    client.post(f'/debates/{debate_id}/participants', json={'participants': [
        {'name': 'Dr Ada', 'role_description': 'methodology professor',
         'model_id': 'openai/gpt-4o-mini', 'system_prompt': 'Interrogate the method.'},
        {'name': 'Dr Bo', 'role_description': 'skeptical reviewer',
         'model_id': 'openai/gpt-4o-mini', 'system_prompt': 'Find the weakest claim.'},
    ]})

    started = client.post(f'/debates/{debate_id}/start')
    assert started.status_code == 200, started.text
    body = started.json()
    assert len(body['participants']) == 2, f'start reported {body["participants"]}'

    fetched = client.get(f'/debates/{debate_id}').json()
    assert len(body['participants']) == len(fetched['participants']), (
        'start and get disagree about the same session'
    )


# ── Conversational setup ────────────────────────────────────────────────────

def test_a_proposal_wrapped_in_prose_is_salvaged():
    """
    A minority of turns arrive as "Sure! {...} Let me know." Treating those as
    unparseable discarded the change the user had just agreed to and printed
    the braces at them instead.
    """
    from src.services.conversational_setup import _salvage_object

    obj = _salvage_object('Sure! {"reply":"ok","proposal":{"title":"T"}} Anything else?')
    assert obj is not None and obj['reply'] == 'ok'

    # A brace inside a string must not end the scan early.
    obj = _salvage_object('{"reply":"a } brace","rounds":3}')
    assert obj is not None and obj['rounds'] == 3

    assert _salvage_object('no object here at all') is None
    assert _salvage_object('') is None


# ── The quality harness ─────────────────────────────────────────────────────

def test_the_citation_metric_does_not_claim_to_verify_citations():
    """
    It matches the SHAPE of a citation. Reporting that as `grounding_rate` told
    callers a fabricated "Section 4.2" was sound — 1.0 and healthy: true.
    """
    from src.services.transcript_quality import QualityReport, Turn, analyse

    assert hasattr(QualityReport, '__dataclass_fields__')
    fields = QualityReport.__dataclass_fields__
    assert 'citation_form_rate' in fields
    assert 'grounding_rate' not in fields, (
        'the old name promised verification this harness never performs'
    )

    # A wholly invented citation still scores on form — which is the point of
    # naming it after form.
    report = analyse([
        Turn(speaker='Dr Ada',
             text='As stated in Section 9.7, the authors prove the theorem.'),
    ])
    assert report.citation_form_rate == 1.0


# ── Fabrication ─────────────────────────────────────────────────────────────

def test_a_session_with_no_turns_cannot_be_summarised():
    """
    With an empty transcript the prompt carries only a title, and the model
    obliges by inventing the rest. A started-and-ended session with no
    reviewers speaking produced two thousand characters of minutes naming
    methodological concerns and "the panel's overall verdict … major revision".

    For a peer-review tool that is the worst output available: an
    official-looking record of a review nobody performed.
    """
    debate_id = _debate('Untitled Session')
    client.post(f'/debates/{debate_id}/participants', json={'participants': [
        {'name': 'Dr A', 'role_description': 'methodology professor',
         'model_id': 'openai/gpt-4o-mini', 'system_prompt': 'Assess the method.'},
    ]})
    client.post(f'/debates/{debate_id}/start')
    client.post(f'/debates/{debate_id}/end')

    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            "SELECT COUNT(*) AS n FROM events WHERE debate_id = %s AND event_type = 'agent_message'",
            (debate_id,),
        )
        assert cur.fetchone()['n'] == 0, 'precondition: nobody spoke'

    r = client.post(f'/debates/{debate_id}/summarize',
                    json={'model_id': 'openai/gpt-4o-mini'})
    assert r.status_code == 400, f'-> {r.status_code} {r.text[:200]}'
    assert 'no reviewer turns' in r.json()['detail']


def test_prior_claims_survive_a_speaker_name_with_a_full_stop():
    """
    The avoidance list is what stops reviewer three restating reviewer one.

    It was built by splitting on sentence punctuation, and every speaker is
    "Prof. X:" or "Dr. Y:" — so the extracted "claim" was the string "Prof."
    and the instruction told the next reviewer to avoid nothing.
    """
    from src.agent_response_generator import _already_raised

    raised = _already_raised([
        {'role': 'assistant',
         'content': 'Prof. Halvorsen: The claim is undermined by the absence of '
                    'inter-rater reliability statistics, since two of three raters '
                    'were co-authors.'},
        {'role': 'user', 'content': '[Moderator note: keep going]'},
    ])
    assert len(raised) == 1
    assert 'inter-rater reliability' in raised[0], raised
    assert raised[0] not in ('Prof.', 'Dr.')
