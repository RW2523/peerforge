"""Integration-ish auth tests: validate JWT enforcement without mocking DebateService."""
import os
import sys
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.main import app
from src.config import settings


client = TestClient(app)


def _grant_membership(user_id: str, workspace_id: str):
    """Membership in user_workspaces is what grants access — not the JWT claim."""
    from src.database import get_db_connection, get_cursor

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute("""
            INSERT INTO user_workspaces (user_id, workspace_id, role)
            VALUES (%s, %s, 'member')
            ON CONFLICT (user_id, workspace_id) DO NOTHING
        """, (user_id, workspace_id))
        conn.commit()


TEST_USER_ID = "00000000-0000-0000-0000-000000000994"


def _make_token(secret: str, workspace_id: str, tenant_id: str, exp_delta_s: int = 3600,
                user_id: str = TEST_USER_ID):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": "test@example.com",
        "role": "authenticated",
        "workspace_id": workspace_id,
        "tenant_id": tenant_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=exp_delta_s)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_create_debate_requires_auth_when_enabled(create_debate_payload, demo_workspace_id, monkeypatch):
    # Enable auth
    monkeypatch.setattr(settings, "require_auth", True)
    # Use a long-enough secret to avoid warnings
    secret = "x" * 40
    monkeypatch.setattr(settings, "supabase_jwt_secret", secret)

    # Missing token => 401
    resp = client.post("/debates", json=create_debate_payload)
    assert resp.status_code == 401, resp.text

    # Valid token for a user who actually belongs to the workspace => 201
    _grant_membership(TEST_USER_ID, demo_workspace_id)
    token = _make_token(
        secret=secret,
        workspace_id=demo_workspace_id,
        tenant_id="00000000-0000-0000-0000-000000000001",
    )
    resp = client.post(
        "/debates",
        json=create_debate_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text


def test_workspace_access_denied(monkeypatch, demo_workspace_id):
    # Enable auth
    monkeypatch.setattr(settings, "require_auth", True)
    secret = "y" * 40
    monkeypatch.setattr(settings, "supabase_jwt_secret", secret)

    # Create a debate in demo workspace using auth-disabled mode first (directly disable for setup)
    monkeypatch.setattr(settings, "require_auth", False)
    resp = client.post("/debates", json={"workspace_id": demo_workspace_id, "title": "Auth Workspace Test"})
    assert resp.status_code == 201, resp.text
    debate_id = resp.json()["debate_id"]

    # Re-enable auth and use a token for a different workspace
    monkeypatch.setattr(settings, "require_auth", True)
    token = _make_token(
        secret=secret,
        workspace_id="00000000-0000-0000-0000-000000000999",
        tenant_id="00000000-0000-0000-0000-000000000001",
    )
    resp = client.post(
        f"/debates/{debate_id}/start",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403, resp.text

