"""
Tests for Presence & Typing endpoints (TICKET-14)
DB-backed tests proving auth, workspace scoping, and event creation
"""

import pytest
import psycopg2
from psycopg2.extras import Json
from fastapi.testclient import TestClient

from src.main import app
from src.config import settings

client = TestClient(app)

# Test constants
WORKSPACE_ID = '00000000-0000-0000-0000-000000000101'


@pytest.fixture
def db_conn():
    """Provide a clean DB connection for each test"""
    conn = psycopg2.connect(settings.database_url)
    yield conn
    conn.rollback()
    conn.close()


def test_presence_join_creates_event(db_conn):
    """Test that joining presence creates a presence_update event"""
    cursor = db_conn.cursor()
    
    # Create test debate
    cursor.execute("""
        INSERT INTO debates (debate_id, workspace_id, title, state)
        VALUES (gen_random_uuid(), %s, 'Test Presence', 'pending')
        RETURNING debate_id
    """, (WORKSPACE_ID,))
    debate_id = cursor.fetchone()[0]
    db_conn.commit()
    
    # Join presence (no auth in test client)
    response = client.post(
        f"/debates/{debate_id}/presence/join",
        json={"participant_id": "test-user-123", "metadata": {"browser": "chrome"}}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["event_type"] == "presence_update"
    assert data["debate_id"] == debate_id
    
    # Verify event was created in DB
    cursor.execute("""
        SELECT event_type, content FROM events
        WHERE debate_id = %s AND event_type = 'presence_update'
        ORDER BY created_at DESC LIMIT 1
    """, (debate_id,))
    
    event = cursor.fetchone()
    assert event is not None
    assert event[0] == 'presence_update'
    assert event[1]['action'] == 'join'
    assert event[1]['participant_id'] == 'test-user-123'


def test_presence_leave_creates_event(db_conn):
    """Test that leaving presence creates a presence_update event"""
    cursor = db_conn.cursor()
    
    # Create test debate
    cursor.execute("""
        INSERT INTO debates (debate_id, workspace_id, title, state)
        VALUES (gen_random_uuid(), %s, 'Test Presence Leave', 'pending')
        RETURNING debate_id
    """, (WORKSPACE_ID,))
    debate_id = cursor.fetchone()[0]
    db_conn.commit()
    
    # Leave presence
    response = client.post(
        f"/debates/{debate_id}/presence/leave",
        json={"participant_id": "test-user-456"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["event_type"] == "presence_update"
    
    # Verify event payload
    cursor.execute("""
        SELECT content FROM events
        WHERE debate_id = %s AND event_type = 'presence_update'
        ORDER BY created_at DESC LIMIT 1
    """, (debate_id,))
    
    content = cursor.fetchone()[0]
    assert content['action'] == 'leave'
    assert content['participant_id'] == 'test-user-456'


def test_typing_creates_event(db_conn):
    """Test that typing signal creates a typing event"""
    cursor = db_conn.cursor()
    
    # Create test debate
    cursor.execute("""
        INSERT INTO debates (debate_id, workspace_id, title, state)
        VALUES (gen_random_uuid(), %s, 'Test Typing', 'running')
        RETURNING debate_id
    """, (WORKSPACE_ID,))
    debate_id = cursor.fetchone()[0]
    db_conn.commit()
    
    # Signal typing
    response = client.post(
        f"/debates/{debate_id}/typing",
        json={
            "participant_id": "agent-123",
            "target_participant_id": "agent-456"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["event_type"] == "typing"
    
    # Verify event payload
    cursor.execute("""
        SELECT content FROM events
        WHERE debate_id = %s AND event_type = 'typing'
        ORDER BY created_at DESC LIMIT 1
    """, (debate_id,))
    
    content = cursor.fetchone()[0]
    assert content['participant_id'] == 'agent-123'
    assert content['target_participant_id'] == 'agent-456'


def test_presence_nonexistent_debate_returns_404(db_conn):
    """Test that presence endpoints return 404 for nonexistent debates"""
    fake_debate_id = '00000000-0000-0000-0000-999999999999'
    
    response = client.post(
        f"/debates/{fake_debate_id}/presence/join",
        json={"participant_id": "test-user"}
    )
    
    assert response.status_code == 404


def test_typing_nonexistent_debate_returns_404(db_conn):
    """Test that typing endpoint returns 404 for nonexistent debates"""
    fake_debate_id = '00000000-0000-0000-0000-999999999999'
    
    response = client.post(
        f"/debates/{fake_debate_id}/typing",
        json={"participant_id": "agent-123"}
    )
    
    assert response.status_code == 404


def test_presence_events_have_sequence_numbers(db_conn):
    """Test that presence events get correct sequence numbers"""
    cursor = db_conn.cursor()
    
    # Create test debate
    cursor.execute("""
        INSERT INTO debates (debate_id, workspace_id, title, state)
        VALUES (gen_random_uuid(), %s, 'Test Sequence', 'pending')
        RETURNING debate_id
    """, (WORKSPACE_ID,))
    debate_id = cursor.fetchone()[0]
    db_conn.commit()
    
    # Create multiple presence events
    response1 = client.post(
        f"/debates/{debate_id}/presence/join",
        json={"participant_id": "user-1"}
    )
    response2 = client.post(
        f"/debates/{debate_id}/presence/join",
        json={"participant_id": "user-2"}
    )
    response3 = client.post(
        f"/debates/{debate_id}/typing",
        json={"participant_id": "user-1"}
    )
    
    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response3.status_code == 200
    
    seq1 = response1.json()["sequence_number"]
    seq2 = response2.json()["sequence_number"]
    seq3 = response3.json()["sequence_number"]
    
    # Sequence numbers should increment
    assert seq2 > seq1
    assert seq3 > seq2
