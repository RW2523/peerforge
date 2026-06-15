import os
import time
import uuid
import pytest
import psycopg2

from src.config import settings


def _wait_for_db(dsn: str, timeout_s: int = 20) -> None:
    last_err = None
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            conn = psycopg2.connect(dsn)
            conn.close()
            return
        except Exception as e:
            last_err = e
            time.sleep(0.5)
    raise RuntimeError(f"Database not reachable within {timeout_s}s: {last_err}")


@pytest.fixture(scope="session", autouse=True)
def require_real_db_for_tests():
    """
    Tests are DB-backed (no DebateService mocks).
    If DB isn't reachable, fail fast with a helpful error.
    """
    _wait_for_db(settings.database_url, timeout_s=30)

    # Ensure the demo tenant/workspace exist so tests don't depend on seed scripts.
    tenant_id = "00000000-0000-0000-0000-000000000001"
    workspace_id = "00000000-0000-0000-0000-000000000101"
    conn = psycopg2.connect(settings.database_url)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tenants (tenant_id, name, slug, status, settings) VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (tenant_id) DO NOTHING",
            (tenant_id, "Demo Organization", "demo-org", "active", "{}"),
        )
        cur.execute(
            "INSERT INTO workspaces (workspace_id, tenant_id, name, slug, description, settings) VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (workspace_id) DO NOTHING",
            (workspace_id, tenant_id, "Product Strategy", "product-strategy", "Test workspace for API suite", "{}"),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def force_test_auth_mode(monkeypatch):
    """
    Default most API tests to auth-disabled so control flow can be verified without
    requiring Supabase Cloud credentials. Auth-specific tests should override this.
    """
    original = settings.require_auth
    settings.require_auth = False
    yield
    settings.require_auth = original


@pytest.fixture
def demo_workspace_id() -> str:
    return "00000000-0000-0000-0000-000000000101"


@pytest.fixture
def create_debate_payload(demo_workspace_id):
    return {"workspace_id": demo_workspace_id, "title": "Test Debate"}
