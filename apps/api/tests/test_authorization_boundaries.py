"""Authorization boundaries, guarded structurally and behaviourally.

These exist because a review found live holes that the whole suite stayed
green through: four autonomous routes with no auth dependency at all, sixteen
handlers that authenticated the caller and then never compared the resource's
workspace to theirs, an invitation token that worked for whoever held it, a
removal that freed the seat but not the access, and a supervisory check that
asked "elevated anywhere?" instead of "elevated here?".

The structural test below is the one that would have caught them. Behavioural
tests prove each specific hole is shut.
"""
import ast
import glob
import os
import re
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
ROUTES_DIR = os.path.join(os.path.dirname(__file__), '..', 'src', 'routes')

# Helpers that establish the caller may reach *this* resource. A handler that
# takes a resource id and calls none of them is unguarded, whatever else it does.
GUARD_CALLS = {
    'authorize_debate',
    'check_workspace_access',
    'require_org_role',
    '_may_access_debate',
    '_verify_debate',
    '_may_access_document',
}

# Dependencies that establish *who* is calling.
AUTH_DEPENDENCIES = {'get_current_user', 'require_auth', 'get_current_user_ws'}


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


@pytest.fixture
def auth_on(monkeypatch):
    monkeypatch.setattr(settings, 'require_auth', True)
    monkeypatch.setattr(settings, 'supabase_jwt_secret', SECRET)


# ── Structural: every resource-scoped handler is guarded ────────────────────

def _handlers():
    """Yield (file, name, source, decorators) for every @router.* handler."""
    for path in sorted(glob.glob(os.path.join(ROUTES_DIR, '*.py'))):
        src = open(path).read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            decorated = any(
                isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                and isinstance(d.func.value, ast.Name) and d.func.value.id == 'router'
                for d in node.decorator_list
            )
            if not decorated:
                continue
            body = ast.get_source_segment(src, node) or ''
            yield os.path.basename(path), node.name, node, body


def _takes_resource_id(node) -> bool:
    args = node.args
    names = [a.arg for a in list(args.args) + list(args.kwonlyargs)]
    return 'debate_id' in names or 'workspace_id' in names or 'org_id' in names


def _calls_a_guard(body: str) -> bool:
    if any(re.search(rf'\b{g}\s*\(', body) for g in GUARD_CALLS):
        return True
    # An inline comparison of the resource's workspace against the caller's.
    return bool(re.search(r'!=\s*_?\w*workspace_id', body))


def test_every_resource_scoped_handler_calls_a_guard():
    """
    A handler that takes debate_id, workspace_id or org_id must check that the
    caller may reach it.

    Authenticating is not authorizing: Depends(get_current_user) proves who is
    asking and says nothing about whether the thing they asked for is theirs.
    """
    unguarded = [
        f'{f}:{name}'
        for f, name, node, body in _handlers()
        if _takes_resource_id(node) and not _calls_a_guard(body)
    ]
    assert not unguarded, (
        'Handlers take a resource id but never authorize it:\n  '
        + '\n  '.join(unguarded)
    )


def test_every_mutating_handler_authenticates():
    """
    Every POST/PUT/PATCH/DELETE route depends on an authentication dependency.

    Four autonomous routes once had no Depends at all; an unauthenticated POST
    paused a running session over the public internet.
    """
    def _is_mutating(node):
        for d in node.decorator_list:
            if (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                    and d.func.attr in ('post', 'put', 'patch', 'delete')):
                return True
        return False

    naked = []
    for f, name, node, body in _handlers():
        if not _is_mutating(node):
            continue
        if not any(dep in body for dep in AUTH_DEPENDENCIES):
            naked.append(f'{f}:{name}')
    assert not naked, (
        'Mutating routes with no authentication dependency:\n  ' + '\n  '.join(naked)
    )


@pytest.mark.parametrize('route,method', [
    ('/api/debates/{d}/start-autonomous', 'post'),
    ('/api/debates/{d}/pause-autonomous', 'post'),
    ('/api/debates/{d}/resume-autonomous', 'post'),
    ('/api/debates/{d}/autonomous-status', 'get'),
])
def test_autonomous_routes_reject_anonymous_callers(auth_on, route, method):
    """No token at all must never reach the autonomous engine."""
    url = route.format(d=str(uuid.uuid4()))
    r = getattr(client, method)(url, json={}) if method == 'post' else client.get(url)
    assert r.status_code in (401, 403), f'{method.upper()} {url} -> {r.status_code}'


# ── Behavioural: the specific holes ─────────────────────────────────────────

def _found_org_with_course(admin, admin_email):
    r = client.post('/organizations', json={'name': 'Boundary U'}, headers=_h(admin, admin_email))
    assert r.status_code == 201, r.text
    org_id = r.json()['org_id']
    r = client.post(f'/organizations/{org_id}/courses', json={'name': 'Course A'},
                    headers=_h(admin, admin_email))
    assert r.status_code == 201, r.text
    return org_id, r.json()['workspace_id']


def _invite(org_id, admin, admin_email, email, role, workspace_id=None):
    payload = {'email': email, 'role': role}
    if workspace_id:
        payload['workspace_id'] = workspace_id
    r = client.post(f'/organizations/{org_id}/invitations', json=payload,
                    headers=_h(admin, admin_email))
    assert r.status_code in (200, 201), r.text
    return r.json()['token']


def test_invitation_token_is_not_a_bearer_credential(auth_on):
    """
    Someone who obtains the token but is not its addressee cannot redeem it.

    The invited role may be org_admin, so a forwarded email was a path to
    administrative control of a university.
    """
    admin, admin_email = _uid(), f'admin-{_uid()[:8]}@boundary.edu'
    org_id, workspace_id = _found_org_with_course(admin, admin_email)

    invited_email = f'invited-{_uid()[:8]}@boundary.edu'
    token = _invite(org_id, admin, admin_email, invited_email, 'org_admin', workspace_id)

    interloper, interloper_email = _uid(), f'other-{_uid()[:8]}@elsewhere.com'
    r = client.post(f'/invitations/{token}/accept', headers=_h(interloper, interloper_email))
    assert r.status_code == 403, f'interloper redeemed an invitation: {r.status_code} {r.text}'

    # The rightful addressee still can.
    invitee = _uid()
    r = client.post(f'/invitations/{token}/accept', headers=_h(invitee, invited_email))
    assert r.status_code == 200, r.text
    assert r.json()['accepted'] is True


def test_removing_a_member_also_revokes_course_access(auth_on):
    """
    Removal must clear user_workspaces, not just the seat.

    Deleting only the organization row freed the seat while leaving the person
    full access to every course in it - unbilled and still reading.
    """
    admin, admin_email = _uid(), f'admin-{_uid()[:8]}@boundary.edu'
    org_id, workspace_id = _found_org_with_course(admin, admin_email)

    student, student_email = _uid(), f'stu-{_uid()[:8]}@boundary.edu'
    token = _invite(org_id, admin, admin_email, student_email, 'student', workspace_id)
    r = client.post(f'/invitations/{token}/accept', headers=_h(student, student_email))
    assert r.status_code == 200, r.text

    # In the course before removal.
    r = client.get('/me/workspaces', headers=_h(student, student_email))
    assert r.status_code == 200, r.text
    assert workspace_id in [w['workspace_id'] for w in r.json()['workspaces']]

    r = client.delete(f'/organizations/{org_id}/members/{student}',
                      headers=_h(admin, admin_email))
    assert r.status_code == 200, r.text

    # And out of it afterwards.
    r = client.get('/me/workspaces', headers=_h(student, student_email))
    assert r.status_code == 200, r.text
    assert workspace_id not in [w['workspace_id'] for w in r.json()['workspaces']], (
        'removed member still holds course access'
    )

    r = client.get(f'/debates?workspace_id={workspace_id}',
                   headers=_h(student, student_email))
    assert r.status_code == 403, f'removed member still reads the course: {r.status_code}'


def test_demotion_reaches_the_course_role(auth_on):
    """
    A professor demoted to student loses professor powers inside the course.

    Workspace role is read from user_workspaces; updating only the
    organization row left the demoted user supervising the cohort.
    """
    admin, admin_email = _uid(), f'admin-{_uid()[:8]}@boundary.edu'
    org_id, workspace_id = _found_org_with_course(admin, admin_email)

    prof, prof_email = _uid(), f'prof-{_uid()[:8]}@boundary.edu'
    token = _invite(org_id, admin, admin_email, prof_email, 'professor', workspace_id)
    assert client.post(f'/invitations/{token}/accept',
                       headers=_h(prof, prof_email)).status_code == 200

    r = client.patch(f'/organizations/{org_id}/members/{prof}',
                     json={'role': 'student'}, headers=_h(admin, admin_email))
    assert r.status_code == 200, r.text

    r = client.get('/me/workspaces', headers=_h(prof, prof_email))
    assert r.status_code == 200, r.text
    mine = [w for w in r.json()['workspaces'] if w['workspace_id'] == workspace_id]
    assert mine, 'demoted member should stay enrolled'
    assert mine[0]['role'] == 'student', (
        f"demotion did not reach the course role: {mine[0]['role']}"
    )


def test_elevation_in_one_organization_does_not_expose_another(auth_on):
    """
    Whole-cohort visibility is scoped to the organization owning the course.

    A TA at one university who also studies at a second saw every session in
    the second one's courses, because the check asked only whether they held
    an elevated role *somewhere*.
    """
    from src.routes.debates import _may_see_whole_workspace

    ws_a, org_a = str(uuid.uuid4()), str(uuid.uuid4())
    ws_b, org_b = str(uuid.uuid4()), str(uuid.uuid4())

    user = {
        'user_id': _uid(),
        # A student in course B, and a TA over in organization A.
        'workspaces': [
            {'workspace_id': ws_a, 'role': 'ta', 'tenant_id': org_a},
            {'workspace_id': ws_b, 'role': 'student', 'tenant_id': org_b},
        ],
        'organizations': [{'org_id': org_a, 'org_role': 'ta'}],
    }

    assert _may_see_whole_workspace(user, ws_a) is True, 'TA should supervise their own course'
    assert _may_see_whole_workspace(user, ws_b) is False, (
        'elevated role in another organization exposed this one'
    )
