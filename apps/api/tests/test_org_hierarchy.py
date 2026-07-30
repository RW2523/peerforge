"""University -> professor -> student, exercised end to end."""
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

client = TestClient(app)

SECRET = 'p' * 40


def _uid() -> str:
    return str(uuid.uuid4())


def _token(user_id: str, email: str = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        'sub': user_id,
        'role': 'authenticated',
        'iat': int((now - timedelta(minutes=1)).timestamp()),
        'exp': int((now + timedelta(hours=1)).timestamp()),
    }
    if email:
        payload['email'] = email
    return jwt.encode(payload, SECRET, algorithm='HS256')


def _h(user_id: str, email: str = None, workspace_id: str = None) -> dict:
    headers = {'Authorization': f'Bearer {_token(user_id, email)}'}
    if workspace_id:
        headers['X-Workspace-Id'] = workspace_id
    return headers


@pytest.fixture(autouse=True)
def auth_on(monkeypatch):
    monkeypatch.setattr(settings, 'require_auth', True)
    monkeypatch.setattr(settings, 'supabase_jwt_secret', SECRET)


def test_university_professor_student_flow():
    """An admin founds a university, staffs it, and a student joins a course."""
    admin, professor, student = _uid(), _uid(), _uid()
    prof_email = f'prof-{professor[:8]}@university.edu'
    student_email = f'stu-{student[:8]}@university.edu'

    r = client.post('/organizations', json={'name': 'Test University'}, headers=_h(admin))
    assert r.status_code == 201, r.text
    org_id = r.json()['org_id']
    assert r.json()['your_role'] == 'org_admin'

    r = client.post(f'/organizations/{org_id}/invitations',
                    json={'email': prof_email, 'role': 'professor'}, headers=_h(admin))
    assert r.status_code == 201, r.text
    prof_invite = r.json()['token']

    r = client.post(f'/invitations/{prof_invite}/accept', headers=_h(professor, prof_email))
    assert r.status_code == 200, r.text
    assert r.json()['role'] == 'professor'

    r = client.post(f'/organizations/{org_id}/courses',
                    json={'name': 'Research Methods'}, headers=_h(professor))
    assert r.status_code == 201, r.text
    course_id = r.json()['workspace_id']

    r = client.post(f'/organizations/{org_id}/invitations',
                    json={'email': student_email, 'role': 'student',
                          'workspace_id': course_id},
                    headers=_h(professor))
    assert r.status_code == 201, r.text
    student_invite = r.json()['token']

    r = client.post(f'/invitations/{student_invite}/accept',
                    headers=_h(student, student_email))
    assert r.status_code == 200, r.text
    assert r.json()['workspace_id'] == course_id

    r = client.post('/debates', json={'workspace_id': course_id, 'title': 'My thesis'},
                    headers=_h(student, student_email, course_id))
    assert r.status_code == 201, r.text
    student_debate = r.json()['debate_id']

    r = client.get(f'/debates?workspace_id={course_id}', headers=_h(professor))
    assert r.status_code == 200, r.text
    assert student_debate in [d['debate_id'] for d in r.json()['items']], \
        'professor should see the whole cohort'

    other_student = _uid()
    other_email = f'other-{other_student[:8]}@university.edu'
    r = client.post(f'/organizations/{org_id}/invitations',
                    json={'email': other_email, 'role': 'student', 'workspace_id': course_id},
                    headers=_h(professor))
    client.post(f"/invitations/{r.json()['token']}/accept",
                headers=_h(other_student, other_email))

    r = client.get(f'/debates?workspace_id={course_id}',
                   headers=_h(other_student, other_email, course_id))
    assert r.status_code == 200, r.text
    assert student_debate not in [d['debate_id'] for d in r.json()['items']], \
        "a student must not see another student's session"

    r = client.get(f'/organizations/{org_id}/members', headers=_h(admin))
    assert r.status_code == 200, r.text
    roles = sorted(m['role'] for m in r.json()['members'])
    assert roles == ['org_admin', 'professor', 'student', 'student'], roles


def test_professor_cannot_mint_administrators():
    """Staffing authority stops short of creating peers or superiors."""
    admin, professor = _uid(), _uid()
    prof_email = f'p2-{professor[:8]}@university.edu'

    org_id = client.post('/organizations', json={'name': 'Role Limits U'},
                         headers=_h(admin)).json()['org_id']
    tok = client.post(f'/organizations/{org_id}/invitations',
                      json={'email': prof_email, 'role': 'professor'},
                      headers=_h(admin)).json()['token']
    client.post(f'/invitations/{tok}/accept', headers=_h(professor, prof_email))

    for forbidden in ('org_admin', 'professor'):
        r = client.post(f'/organizations/{org_id}/invitations',
                        json={'email': 'someone@university.edu', 'role': forbidden},
                        headers=_h(professor))
        assert r.status_code == 403, f'{forbidden}: {r.text}'


def test_outsider_cannot_read_a_roster():
    admin, outsider = _uid(), _uid()
    org_id = client.post('/organizations', json={'name': 'Closed U'},
                         headers=_h(admin)).json()['org_id']

    r = client.get(f'/organizations/{org_id}/members', headers=_h(outsider))
    assert r.status_code == 403, r.text


def test_seat_limit_blocks_further_invitations():
    admin = _uid()
    org_id = client.post('/organizations', json={'name': 'Two Seat College'},
                         headers=_h(admin)).json()['org_id']

    r = client.put(f'/organizations/{org_id}/seats',
                   json={'seats_purchased': 2, 'plan': 'starter'}, headers=_h(admin))
    assert r.status_code == 200, r.text

    first = _uid()
    first_email = f'first-{first[:8]}@university.edu'
    tok = client.post(f'/organizations/{org_id}/invitations',
                      json={'email': first_email, 'role': 'student'},
                      headers=_h(admin)).json()['token']
    assert client.post(f'/invitations/{tok}/accept',
                       headers=_h(first, first_email)).status_code == 200

    r = client.get(f'/organizations/{org_id}/seats', headers=_h(admin))
    assert r.json()['seats_used'] == 2
    assert r.json()['seats_available'] == 0

    r = client.post(f'/organizations/{org_id}/invitations',
                    json={'email': 'third@university.edu', 'role': 'student'},
                    headers=_h(admin))
    assert r.status_code == 409, r.text
    assert 'seat' in r.json()['detail'].lower()


def test_invitation_cannot_be_reused_or_revoked_then_used():
    admin, joiner, latecomer = _uid(), _uid(), _uid()
    org_id = client.post('/organizations', json={'name': 'Single Use U'},
                         headers=_h(admin)).json()['org_id']

    email = f'once-{joiner[:8]}@university.edu'
    tok = client.post(f'/organizations/{org_id}/invitations',
                      json={'email': email, 'role': 'student'},
                      headers=_h(admin)).json()['token']

    assert client.post(f'/invitations/{tok}/accept',
                       headers=_h(joiner, email)).status_code == 200
    r = client.post(f'/invitations/{tok}/accept', headers=_h(latecomer, email))
    assert r.status_code == 409, r.text

    r = client.post(f'/organizations/{org_id}/invitations',
                    json={'email': 'revoked@university.edu', 'role': 'student'},
                    headers=_h(admin))
    invite_id, tok2 = r.json()['invite_id'], r.json()['token']
    assert client.delete(f'/organizations/{org_id}/invitations/{invite_id}',
                         headers=_h(admin)).status_code == 200
    r = client.post(f'/invitations/{tok2}/accept', headers=_h(_uid(), 'revoked@university.edu'))
    assert r.status_code == 410, r.text


def test_pending_invitation_is_redeemed_on_first_login():
    """An invited student must not be stranded in a personal workspace."""
    admin, newcomer = _uid(), _uid()
    email = f'firstlogin-{newcomer[:8]}@university.edu'

    org_id = client.post('/organizations', json={'name': 'First Login U'},
                         headers=_h(admin)).json()['org_id']
    course_id = client.post(f'/organizations/{org_id}/courses',
                            json={'name': 'Intro'}, headers=_h(admin)).json()['workspace_id']
    client.post(f'/organizations/{org_id}/invitations',
                json={'email': email, 'role': 'student', 'workspace_id': course_id},
                headers=_h(admin))

    r = client.get('/me/workspaces', headers=_h(newcomer, email))
    assert r.status_code == 200, r.text
    joined = [w['workspace_id'] for w in r.json()['workspaces']]
    assert course_id in joined, f'expected to land in the invited course, got {joined}'


def test_last_admin_cannot_be_demoted():
    admin = _uid()
    org_id = client.post('/organizations', json={'name': 'Sole Admin U'},
                         headers=_h(admin)).json()['org_id']

    r = client.patch(f'/organizations/{org_id}/members/{admin}',
                     json={'role': 'student'}, headers=_h(admin))
    assert r.status_code == 409, r.text
    assert 'last admin' in r.json()['detail'].lower()
