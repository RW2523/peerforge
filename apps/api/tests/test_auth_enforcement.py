"""What must hold the moment authentication is switched on."""
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
from src.debate_service import DebateService

client = TestClient(app)
SECRET = 'e' * 48
WS = '00000000-0000-0000-0000-000000000101'


def _uid():
    return str(uuid.uuid4())


def _token(user_id, email=None):
    now = datetime.now(timezone.utc)
    payload = {
        'sub': user_id, 'role': 'authenticated',
        'iat': int((now - timedelta(minutes=1)).timestamp()),
        'exp': int((now + timedelta(hours=1)).timestamp()),
    }
    if email:
        payload['email'] = email
    return jwt.encode(payload, SECRET, algorithm='HS256')


@pytest.fixture(autouse=True)
def auth_on(monkeypatch):
    monkeypatch.setattr(settings, 'require_auth', True)
    monkeypatch.setattr(settings, 'supabase_jwt_secret', SECRET)


@pytest.mark.parametrize('method,path', [
    ('get', f'/debates?workspace_id={WS}'),
    ('get', '/me/workspaces'),
    ('get', '/me/organizations'),
    ('post', '/organizations'),
])
def test_protected_routes_refuse_anonymous_callers(method, path):
    r = getattr(client, method)(path, **({'json': {}} if method == 'post' else {}))
    assert r.status_code == 401, f'{path} answered {r.status_code}'


def test_a_forged_token_is_refused():
    """Signed with the wrong key — the whole point of the secret."""
    forged = jwt.encode({'sub': _uid(), 'exp': 9999999999}, 'wrong-secret', algorithm='HS256')
    r = client.get('/me/workspaces', headers={'Authorization': f'Bearer {forged}'})
    assert r.status_code == 401


def test_readiness_reports_ready_once_auth_and_secret_are_set():
    body = client.get('/readiness').json()
    by_name = {c['name']: c for c in body['checks']}
    assert by_name['authentication']['ok'] is True
    assert by_name['jwt_secret']['ok'] is True


def test_websocket_refuses_a_debate_the_caller_cannot_reach():
    """Authenticating is not authorising: a session belongs to a workspace."""
    from src.routes.websocket import _may_access_debate

    debate_id = DebateService().create_debate(workspace_id=WS, title='Private')['debate_id']
    stranger = _uid()

    assert _may_access_debate(stranger, debate_id) is False


def test_websocket_access_check_fails_closed_on_a_bad_id():
    from src.routes.websocket import _may_access_debate

    assert _may_access_debate(_uid(), 'not-a-uuid') is False
    assert _may_access_debate(_uid(), str(uuid.uuid4())) is False


def test_document_websocket_refuses_an_unknown_document():
    from src.websocket.document_hub import _may_access_document

    assert _may_access_document(_uid(), str(uuid.uuid4())) is False
