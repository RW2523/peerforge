"""Regression test: the assessment routes must not read across workspaces."""
import os, sys, jwt
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from fastapi.testclient import TestClient
from src.main import app
from src.config import settings
from src.database import get_db_connection, get_cursor
import pytest

client = TestClient(app)
OUTSIDER = '00000000-0000-0000-0000-000000000993'
OTHER_WS = '00000000-0000-0000-0000-000000000103'
VICTIM_WS = '00000000-0000-0000-0000-000000000101'


def _token(user_id, secret):
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': user_id, 'role': 'authenticated',
                       'iat': int((now - timedelta(minutes=1)).timestamp()),
                       'exp': int((now + timedelta(hours=1)).timestamp())},
                      secret, algorithm='HS256')


@pytest.fixture(autouse=True)
def auth_on(monkeypatch):
    monkeypatch.setattr(settings, 'require_auth', True)


def test_outsider_cannot_read_another_workspaces_assessment(monkeypatch):
    secret = 'z' * 40
    monkeypatch.setattr(settings, 'supabase_jwt_secret', secret)

    from src.debate_service import DebateService
    victim = DebateService().create_debate(workspace_id=VICTIM_WS, title='Victim session')

    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("""INSERT INTO workspaces (workspace_id, tenant_id, name, slug)
                       VALUES (%s,'00000000-0000-0000-0000-000000000001','Outsider','outsider-ws')
                       ON CONFLICT (workspace_id) DO NOTHING""", (OTHER_WS,))
        cur.execute("""INSERT INTO user_workspaces (user_id, workspace_id, role)
                       VALUES (%s,%s,'member') ON CONFLICT DO NOTHING""", (OUTSIDER, OTHER_WS))
        conn.commit()

    h = {'Authorization': f'Bearer {_token(OUTSIDER, secret)}'}
    did = victim['debate_id']
    for path in (f'/debates/{did}/assessment',
                 f'/debates/{did}/assessment/history',
                 f'/debates/{did}/certificate'):
        r = client.get(path, headers=h)
        assert r.status_code == 403, f'{path} returned {r.status_code}: {r.text[:120]}'

    r = client.post(f'/debates/{did}/certificate/issue', headers=h)
    assert r.status_code == 403, r.text
    r = client.get(f'/workspaces/{VICTIM_WS}/readiness-overview', headers=h)
    assert r.status_code == 403, r.text
