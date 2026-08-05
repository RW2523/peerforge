"""Rules the institution tier has to keep, found by an end-to-end run.

Each of these was reachable through the normal API by someone with a role the
product hands out freely:

  - redeeming an invitation rewrote org_role, and that was the one path around
    the last-admin guard, so a professor could strip the only administrator
  - a course cohort listed everyone in the university, not the course
  - invitations reserved no seat, so the refusal landed on a student instead of
    the admin who oversubscribed
  - applying a setup proposal deleted the panel of a session already running
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.main import app
from src.config import settings
from src.database import get_db_connection, get_cursor

client = TestClient(app)
SECRET = 'q' * 40


def _uid() -> str:
    return str(uuid.uuid4())


def _h(user_id: str, email: str = None) -> dict:
    now = datetime.now(timezone.utc)
    payload = {
        'sub': user_id,
        'role': 'authenticated',
        'iat': int((now - timedelta(minutes=1)).timestamp()),
        'exp': int((now + timedelta(hours=1)).timestamp()),
    }
    if email:
        payload['email'] = email
    return {'Authorization': f'Bearer {jwt.encode(payload, SECRET, algorithm="HS256")}'}


@pytest.fixture
def auth_on(monkeypatch):
    monkeypatch.setattr(settings, 'require_auth', True)
    monkeypatch.setattr(settings, 'supabase_jwt_secret', SECRET)


def _org_with_course(admin, admin_email, course='Course A'):
    r = client.post('/organizations', json={'name': 'Integrity U'}, headers=_h(admin, admin_email))
    assert r.status_code == 201, r.text
    org_id = r.json()['org_id']
    r = client.post(f'/organizations/{org_id}/courses', json={'name': course},
                    headers=_h(admin, admin_email))
    assert r.status_code == 201, r.text
    return org_id, r.json()['workspace_id']


def _invite(org_id, actor, actor_email, email, role, workspace_id=None):
    payload = {'email': email, 'role': role}
    if workspace_id:
        payload['workspace_id'] = workspace_id
    return client.post(f'/organizations/{org_id}/invitations', json=payload,
                       headers=_h(actor, actor_email))



def _seed_invitation(org_id, email, role, workspace_id=None):
    """
    Write an invitation straight to the table.

    The endpoint now refuses to invite someone already on the roster, which
    closes this attack one step earlier. The redemption guard is still the
    thing under test here — an invitation can predate the membership it would
    overwrite — so reach it directly rather than through the endpoint.
    """
    import secrets
    from datetime import datetime, timedelta, timezone
    token = secrets.token_urlsafe(32)
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            """INSERT INTO invitations (invite_id, org_id, workspace_id, email,
                                        invited_role, token, expires_at, created_at)
               VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, NOW())""",
            (org_id, workspace_id, email, role, token,
             datetime.now(timezone.utc) + timedelta(days=7)),
        )
        conn.commit()
    return token


# ── The last administrator ──────────────────────────────────────────────────

def test_redeeming_an_invitation_cannot_strip_the_last_admin(auth_on):
    """
    Accepting an invitation is a role change, and must obey the same guard.

    A professor may invite students. Inviting the sole administrator's address
    as 'student' and having it redeemed left the organization with nobody able
    to administer it — the one path around the check PATCH and DELETE enforce.
    """
    admin, admin_email = _uid(), f'admin-{_uid()[:8]}@integrity.edu'
    org_id, workspace_id = _org_with_course(admin, admin_email)

    token = _seed_invitation(org_id, admin_email, 'student', workspace_id)

    r = client.post(f'/invitations/{token}/accept', headers=_h(admin, admin_email))
    assert r.status_code == 409, (
        f'the last administrator was demoted to student: {r.status_code} {r.text}'
    )

    # Still an admin, so the organization is still manageable.
    r = client.get('/me/organizations', headers=_h(admin, admin_email))
    mine = [o for o in r.json()['organizations'] if o['org_id'] == org_id]
    assert mine and mine[0]['org_role'] == 'org_admin'


def test_a_second_admin_makes_the_demotion_allowed(auth_on):
    """The guard protects the last admin, not every admin."""
    admin, admin_email = _uid(), f'admin-{_uid()[:8]}@integrity.edu'
    org_id, workspace_id = _org_with_course(admin, admin_email)

    other, other_email = _uid(), f'admin2-{_uid()[:8]}@integrity.edu'
    r = _invite(org_id, admin, admin_email, other_email, 'org_admin', workspace_id)
    client.post(f'/invitations/{r.json()["token"]}/accept', headers=_h(other, other_email))

    token = _seed_invitation(org_id, admin_email, 'student', workspace_id)
    r = client.post(f'/invitations/{token}/accept', headers=_h(admin, admin_email))
    assert r.status_code == 200, r.text


# ── Cohort scoping ──────────────────────────────────────────────────────────

def test_a_course_cohort_lists_only_that_course(auth_on):
    """
    Filtering the debates but not the members showed every student in the
    university under each individual course.
    """
    admin, admin_email = _uid(), f'admin-{_uid()[:8]}@integrity.edu'
    org_id, ws_a = _org_with_course(admin, admin_email, 'Course A')

    r = client.post(f'/organizations/{org_id}/courses', json={'name': 'Course B'},
                    headers=_h(admin, admin_email))
    ws_b = r.json()['workspace_id']

    in_a, in_a_email = _uid(), f'a-{_uid()[:8]}@integrity.edu'
    in_b, in_b_email = _uid(), f'b-{_uid()[:8]}@integrity.edu'
    for uid, email, ws in ((in_a, in_a_email, ws_a), (in_b, in_b_email, ws_b)):
        r = _invite(org_id, admin, admin_email, email, 'student', ws)
        assert client.post(f'/invitations/{r.json()["token"]}/accept',
                           headers=_h(uid, email)).status_code == 200

    r = client.get(f'/organizations/{org_id}/cohort?workspace_id={ws_a}',
                   headers=_h(admin, admin_email))
    assert r.status_code == 200, r.text
    emails = {p.get('email') for p in r.json().get('people', [])}
    assert in_a_email in emails, 'the course\'s own student is missing'
    assert in_b_email not in emails, (
        'a student from another course appeared in this course\'s cohort'
    )

    # Unscoped still shows the whole organization.
    r = client.get(f'/organizations/{org_id}/cohort', headers=_h(admin, admin_email))
    all_emails = {p.get('email') for p in r.json().get('people', [])}
    assert {in_a_email, in_b_email} <= all_emails


# ── Seats ───────────────────────────────────────────────────────────────────

def _set_seats(org_id, n, admin, admin_email):
    r = client.put(f'/organizations/{org_id}/seats', json={'seats_purchased': n},
                   headers=_h(admin, admin_email))
    assert r.status_code == 200, r.text


def test_pending_invitations_hold_seats(auth_on):
    """
    An outstanding invitation is a seat already promised.

    Counting only accepted members let an admin oversubscribe freely, and the
    409 then surfaced to a student at accept time — the one person who could
    do nothing about it.
    """
    admin, admin_email = _uid(), f'admin-{_uid()[:8]}@integrity.edu'
    org_id, workspace_id = _org_with_course(admin, admin_email)
    _set_seats(org_id, 1, admin, admin_email)

    first = _invite(org_id, admin, admin_email, f's1-{_uid()[:8]}@integrity.edu',
                    'student', workspace_id)
    assert first.status_code in (200, 201), first.text

    second = _invite(org_id, admin, admin_email, f's2-{_uid()[:8]}@integrity.edu',
                     'student', workspace_id)
    assert second.status_code == 409, (
        f'a second invitation was issued against one seat: {second.status_code}'
    )
    assert 'awaiting acceptance' in second.json()['detail']


def test_an_invitation_does_not_block_its_own_redemption(auth_on):
    """The reservation must not count against the person redeeming it."""
    admin, admin_email = _uid(), f'admin-{_uid()[:8]}@integrity.edu'
    org_id, workspace_id = _org_with_course(admin, admin_email)
    _set_seats(org_id, 1, admin, admin_email)

    student, student_email = _uid(), f'stu-{_uid()[:8]}@integrity.edu'
    r = _invite(org_id, admin, admin_email, student_email, 'student', workspace_id)
    r = client.post(f'/invitations/{r.json()["token"]}/accept', headers=_h(student, student_email))
    assert r.status_code == 200, f'the reservation blocked its own redemption: {r.text}'


def test_seats_report_what_is_committed(auth_on):
    """Reporting only seats_used advertised capacity the next invite refuses."""
    admin, admin_email = _uid(), f'admin-{_uid()[:8]}@integrity.edu'
    org_id, workspace_id = _org_with_course(admin, admin_email)
    _set_seats(org_id, 5, admin, admin_email)

    _invite(org_id, admin, admin_email, f's-{_uid()[:8]}@integrity.edu', 'student', workspace_id)

    r = client.get(f'/organizations/{org_id}/seats', headers=_h(admin, admin_email))
    body = r.json()
    assert body['seats_pending'] == 1, body
    assert body['seats_committed'] == body['seats_used'] + body['seats_pending']
    assert body['seats_available'] == 5 - body['seats_committed']


# ── Setup apply ─────────────────────────────────────────────────────────────

def _session_in_state(state: str) -> str:
    r = client.post('/debates', json={
        'workspace_id': '00000000-0000-0000-0000-000000000101',
        'title': 'Apply guard',
    })
    debate_id = r.json()['debate_id']
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("UPDATE debates SET state = %s WHERE debate_id = %s", (state, debate_id))
        conn.commit()
    return debate_id


def _apply_body():
    return {
        'title': 'A session',
        'problem_statement': 'Whether the ablation supports the claim.',
        'panel': [
            {'name': 'Dr Ada', 'role': 'methodology professor', 'focus': 'stats'},
            {'name': 'Dr Bo', 'role': 'domain expert', 'focus': 'the field'},
        ],
        'rounds': 2,
    }


@pytest.mark.parametrize('state', ['running', 'paused', 'ended'])
def test_apply_refuses_to_replace_a_panel_mid_session(state):
    """
    Applying deletes and re-creates the panel. Doing that to a session already
    under way orphaned every turn the deleted reviewers had produced.
    """
    debate_id = _session_in_state(state)
    r = client.post(f'/debates/{debate_id}/setup/apply', json=_apply_body())
    assert r.status_code == 409, f'panel replaced while {state}: {r.status_code} {r.text}'


@pytest.mark.parametrize('state', ['draft', 'pending'])
def test_apply_still_works_before_the_session_starts(state):
    """The guard must not block the normal setup path."""
    debate_id = _session_in_state(state)
    r = client.post(f'/debates/{debate_id}/setup/apply', json=_apply_body())
    assert r.status_code == 200, f'apply blocked while {state}: {r.text}'
    assert len(r.json()['participant_ids']) == 2


# ── Role remapping ──────────────────────────────────────────────────────────

def test_unmapped_roles_stay_distinct_and_are_reported():
    """
    Every unrecognised role used to become 'skeptical reviewer', so two of them
    produced byte-identical personas, and the assistant claimed to have staffed
    a role it had not.
    """
    from src.services.conversational_setup import _clean_proposal

    cleaned = _clean_proposal({
        'title': 'T',
        'problem_statement': 'P',
        'rounds': 3,
        'panel': [
            {'name': 'One', 'role': 'ACL area chair', 'focus': 'venue fit'},
            {'name': 'Two', 'role': 'industry practitioner', 'focus': 'deployment'},
        ],
    })

    roles = [m['role'] for m in cleaned['panel']]
    assert len(set(roles)) == 2, f'unmapped roles collapsed into one lane: {roles}'

    assert len(cleaned['remapped_roles']) == 2
    assert {r['requested'] for r in cleaned['remapped_roles']} == {
        'acl area chair', 'industry practitioner'
    }

    # The requested role survives in the persona rather than being discarded.
    for member in cleaned['panel']:
        assert member['requested_role']
        assert member['requested_role'] in member['focus']


def test_a_recognised_role_is_left_alone():
    from src.services.conversational_setup import _clean_proposal

    cleaned = _clean_proposal({
        'title': 'T', 'problem_statement': 'P', 'rounds': 3,
        'panel': [{'name': 'One', 'role': 'Methodology Professor', 'focus': 'stats'}],
    })
    assert cleaned['panel'][0]['role'] == 'methodology professor'
    assert cleaned['remapped_roles'] == []
