"""Tests for POST /debates/run endpoint (DB-backed, OpenRouter mocked)."""
import pytest
import os
import sys
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from src.main import app
from src.openrouter_client import OpenRouterAuthError
from src.database import get_db_connection, get_cursor


client = TestClient(app)


# Mock OpenRouter responses
MOCK_AGENT_RESPONSE_1 = {
    "content": "As a Product Manager, I think we should focus on user research first. Understanding our users' needs is critical.",
    "usage": {"total_tokens": 50},
    "model": "anthropic/claude-3.5-sonnet"
}

MOCK_AGENT_RESPONSE_2 = {
    "content": "From an engineering perspective, we need to consider technical feasibility and scalability.",
    "usage": {"total_tokens": 45},
    "model": "openai/gpt-4-turbo"
}

MOCK_AGENT_RESPONSE_3 = {
    "content": "As a UX Designer, I want to ensure the interface is intuitive and accessible to all users.",
    "usage": {"total_tokens": 48},
    "model": "anthropic/claude-3.5-sonnet"
}

MOCK_SUMMARY_RESPONSE = {
    "content": '{"summary": "The team discussed prioritizing user research and technical feasibility.", "minutes_of_meeting": "Product Manager emphasized user needs, Senior Engineer highlighted scalability concerns, and UX Designer focused on accessibility. Team agreed to conduct user research before technical implementation.", "action_items": ["Conduct user research survey", "Assess technical feasibility", "Create accessible design mockups"]}',
    "usage": {"total_tokens": 100},
    "model": "anthropic/claude-3.5-sonnet"
}


@pytest.fixture
def valid_request_payload():
    """Valid debate run request"""
    return {
        "problem_statement": "Should we prioritize mobile-first or desktop-first design?",
        "agents": [
            {
                "name": "Product Manager",
                "role": "Strategic product leader",
                "model_id": "anthropic/claude-3.5-sonnet"
            },
            {
                "name": "Senior Engineer",
                "role": "Technical lead",
                "model_id": "openai/gpt-4-turbo"
            },
            {
                "name": "UX Designer",
                "role": "User experience expert",
                "model_id": "anthropic/claude-3.5-sonnet"
            }
        ],
        "openrouter_api_key": "sk-or-test-key-123456",
        "debate_title": "Design Priority Discussion"
    }


def test_health_check():
    """Test health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@patch('src.debate_engine.OpenRouterClient')
def test_debate_run_happy_path(mock_openrouter, valid_request_payload):
    """Test successful 5-turn debate execution"""
    # Mock OpenRouter client
    mock_client_instance = MagicMock()
    mock_openrouter.return_value = mock_client_instance
    
    # Mock 5 agent responses + 1 summary response
    mock_client_instance.chat_completion.side_effect = [
        MOCK_AGENT_RESPONSE_1,  # Turn 1: Agent 0
        MOCK_AGENT_RESPONSE_2,  # Turn 2: Agent 1
        MOCK_AGENT_RESPONSE_3,  # Turn 3: Agent 2
        MOCK_AGENT_RESPONSE_1,  # Turn 4: Agent 0
        MOCK_AGENT_RESPONSE_2,  # Turn 5: Agent 1
        MOCK_SUMMARY_RESPONSE   # Final summary
    ]
    
    # Execute request
    response = client.post("/debates/run", json=valid_request_payload)
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    
    # Check structure
    assert "debate_id" in data
    assert "status" in data
    assert "outputs" in data
    assert "event_history" in data
    
    # Check outputs
    assert "summary" in data["outputs"]
    assert "minutes_of_meeting" in data["outputs"]
    assert "action_items" in data["outputs"]
    assert isinstance(data["outputs"]["action_items"], list)
    
    # Check event history
    assert len(data["event_history"]) == 5
    for i, event in enumerate(data["event_history"]):
        assert "event_id" in event
        assert "turn" in event
        assert event["turn"] == i + 1
        assert "agent" in event
        assert "message" in event

    # Verify DB has the debate row
    debate_id = data["debate_id"]
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("SELECT debate_id, state FROM debates WHERE debate_id=%s", (debate_id,))
        row = cur.fetchone()
        assert row is not None
        assert row["state"] == "ended"


@patch('src.debate_engine.OpenRouterClient')
def test_debate_run_turn_order(mock_openrouter, valid_request_payload):
    """Test deterministic round-robin turn order"""
    mock_client_instance = MagicMock()
    mock_openrouter.return_value = mock_client_instance
    
    mock_client_instance.chat_completion.side_effect = [
        MOCK_AGENT_RESPONSE_1,  # Turn 1: Agent 0 (PM)
        MOCK_AGENT_RESPONSE_2,  # Turn 2: Agent 1 (Engineer)
        MOCK_AGENT_RESPONSE_3,  # Turn 3: Agent 2 (Designer)
        MOCK_AGENT_RESPONSE_1,  # Turn 4: Agent 0 (PM)
        MOCK_AGENT_RESPONSE_2,  # Turn 5: Agent 1 (Engineer)
        MOCK_SUMMARY_RESPONSE
    ]
    
    response = client.post("/debates/run", json=valid_request_payload)
    assert response.status_code == 200
    data = response.json()

    # Verify turn order: 0, 1, 2, 0, 1
    events = data["event_history"]
    expected_agents = ["Product Manager", "Senior Engineer", "UX Designer", "Product Manager", "Senior Engineer"]

    for i, expected_agent in enumerate(expected_agents):
        assert events[i]["agent"] == expected_agent


def test_debate_run_invalid_agent_count(valid_request_payload):
    """Test request with wrong number of agents"""
    payload = valid_request_payload.copy()
    payload["agents"] = payload["agents"][:2]  # Only 2 agents
    
    response = client.post("/debates/run", json=payload)
    
    assert response.status_code == 400
    assert "3 agents required" in response.json()["detail"]


@patch('src.debate_engine.OpenRouterClient')
def test_debate_run_invalid_openrouter_key(mock_openrouter, valid_request_payload):
    """Test request with invalid OpenRouter API key"""
    mock_openrouter.side_effect = OpenRouterAuthError("Invalid OpenRouter API key")
    
    response = client.post("/debates/run", json=valid_request_payload)
    
    assert response.status_code == 401
    assert "OpenRouter authentication failed" in response.json()["detail"]


def test_debate_run_missing_api_key(valid_request_payload):
    """Test request with missing API key"""
    payload = valid_request_payload.copy()
    del payload["openrouter_api_key"]
    
    response = client.post("/debates/run", json=payload)
    
    assert response.status_code == 422  # FastAPI validation error


@patch('src.debate_engine.OpenRouterClient')
def test_debate_run_db_persistence(mock_openrouter, valid_request_payload):
    """Test that debate and events are persisted to database"""
    mock_client_instance = MagicMock()
    mock_openrouter.return_value = mock_client_instance
    
    mock_client_instance.chat_completion.side_effect = [
        MOCK_AGENT_RESPONSE_1,
        MOCK_AGENT_RESPONSE_2,
        MOCK_AGENT_RESPONSE_3,
        MOCK_AGENT_RESPONSE_1,
        MOCK_AGENT_RESPONSE_2,
        MOCK_SUMMARY_RESPONSE
    ]
    
    response = client.post("/debates/run", json=valid_request_payload)
    
    assert response.status_code == 200

    data = response.json()
    debate_id = data["debate_id"]

    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("SELECT COUNT(*)::int AS c FROM participants WHERE debate_id=%s", (debate_id,))
        participants = cur.fetchone()["c"]
        assert participants == 3

        cur.execute("SELECT COUNT(*)::int AS c FROM events WHERE debate_id=%s", (debate_id,))
        events = cur.fetchone()["c"]
        # 1 system event + 5 agent messages + 1+ system messages possible
        assert events >= 6
