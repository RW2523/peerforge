"""Tests for M3 summary generation endpoints"""
import pytest
import os
import sys
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_auth_for_summary_tests():
    """Disable auth requirement for summary tests"""
    from src.config import settings
    original = settings.require_auth
    settings.require_auth = False
    yield
    settings.require_auth = original


@pytest.fixture
def mock_openrouter_response():
    """Mock successful OpenRouter summary response"""
    return {
        'content': '''
{
  "summary": "Team discussed Q1 feature prioritization, focusing on user experience improvements over technical complexity.",
  "minutes": "The debate began with PM presenting three feature candidates for Q1 2026. Engineer raised concerns about technical debt but Designer emphasized user feedback indicating UX improvements as highest priority. After intervention suggesting focus on user experience, team aligned on prioritizing accessibility features and simplified onboarding flow. Technical refactoring was deferred to Q2.",
  "action_items": [
    {"description": "Draft accessibility audit plan", "owner": "Designer", "priority": "high"},
    {"description": "Prototype simplified onboarding flow", "owner": "Engineer", "priority": "high"},
    {"description": "Schedule user testing sessions", "owner": "PM", "priority": "medium"}
  ]
}
''',
        'usage': {'total_tokens': 450}
    }


@patch('src.summary_service.OpenRouterClient')
def test_generate_summary_happy_path(mock_openrouter_class, mock_openrouter_response):
    """Test successful summary generation for ended debate"""
    from src.debate_service import DebateService
    from src.state_machine import DebateState
    
    # Create real debate in DB
    service = DebateService()
    debate = service.create_debate(
        workspace_id='00000000-0000-0000-0000-000000000101',
        title='Test Debate for Summary'
    )
    debate_id = debate['debate_id']
    
    # Transition to ended state
    service.start_debate(debate_id)
    service.end_debate(debate_id)
    
    # Mock OpenRouter client
    mock_client = MagicMock()
    mock_client.chat_completion.return_value = mock_openrouter_response
    mock_openrouter_class.return_value = mock_client
    
    # Generate summary
    response = client.post(
        f"/debates/{debate_id}/summarize",
        json={
            "openrouter_api_key": "sk-or-v1-test-key-1234567890",
            "model_id": "anthropic/claude-3.5-sonnet"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert 'output_id' in data
    assert data['debate_id'] == debate_id
    assert 'Q1 feature prioritization' in data['summary']
    assert 'accessibility' in data['minutes'].lower()
    assert len(data['action_items']) == 3
    assert data['action_items'][0]['priority'] == 'high'
    assert data['model_used'] == 'anthropic/claude-3.5-sonnet'
    
    # Verify summary event created
    from src.database import get_db_connection, get_cursor
    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute("""
            SELECT event_type, content 
            FROM events 
            WHERE debate_id = %s AND event_type = 'debate_summary'
        """, (debate_id,))
        event = cursor.fetchone()
        
        assert event is not None
        assert event['event_type'] == 'debate_summary'
        assert 'summary' in event['content']


@patch('src.summary_service.OpenRouterClient')
def test_get_summary_after_generation(mock_openrouter_class, mock_openrouter_response):
    """Test GET /summary returns generated outputs"""
    from src.debate_service import DebateService
    
    # Create and end debate
    service = DebateService()
    debate = service.create_debate(
        workspace_id='00000000-0000-0000-0000-000000000101',
        title='Test Debate for GET Summary'
    )
    debate_id = debate['debate_id']
    service.start_debate(debate_id)
    service.end_debate(debate_id)
    
    # Mock OpenRouter and generate
    mock_client = MagicMock()
    mock_client.chat_completion.return_value = mock_openrouter_response
    mock_openrouter_class.return_value = mock_client
    
    client.post(
        f"/debates/{debate_id}/summarize",
        json={"openrouter_api_key": "sk-or-v1-test", "model_id": "anthropic/claude-3.5-sonnet"}
    )
    
    # Now GET summary
    response = client.get(f"/debates/{debate_id}/summary")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data['debate_id'] == debate_id
    assert 'Q1 feature prioritization' in data['summary']
    assert len(data['action_items']) == 3


def test_summarize_missing_openrouter_key():
    """Test summarize without OpenRouter key returns 422 (validation error)"""
    from src.debate_service import DebateService
    
    service = DebateService()
    debate = service.create_debate(
        workspace_id='00000000-0000-0000-0000-000000000101',
        title='Test Debate'
    )
    debate_id = debate['debate_id']
    service.start_debate(debate_id)
    service.end_debate(debate_id)
    
    response = client.post(
        f"/debates/{debate_id}/summarize",
        json={"model_id": "anthropic/claude-3.5-sonnet"}  # Missing openrouter_api_key
    )
    
    assert response.status_code == 422  # Pydantic validation error


def test_summarize_debate_not_ended():
    """Test summarize on running debate returns 400"""
    from src.debate_service import DebateService
    
    service = DebateService()
    debate = service.create_debate(
        workspace_id='00000000-0000-0000-0000-000000000101',
        title='Test Running Debate'
    )
    debate_id = debate['debate_id']
    service.start_debate(debate_id)  # Still running
    
    response = client.post(
        f"/debates/{debate_id}/summarize",
        json={
            "openrouter_api_key": "sk-or-v1-test-key",
            "model_id": "anthropic/claude-3.5-sonnet"
        }
    )
    
    assert response.status_code == 400
    assert "must be in 'ended' state" in response.json()['detail'].lower()


def test_get_summary_not_generated():
    """Test GET summary on debate without summary returns 404"""
    from src.debate_service import DebateService
    
    service = DebateService()
    debate = service.create_debate(
        workspace_id='00000000-0000-0000-0000-000000000101',
        title='Test Debate Without Summary'
    )
    debate_id = debate['debate_id']
    
    response = client.get(f"/debates/{debate_id}/summary")
    
    assert response.status_code == 404
    assert 'no summary found' in response.json()['detail'].lower()


def test_summarize_debate_not_found():
    """Test summarize on non-existent debate returns 404"""
    response = client.post(
        "/debates/00000000-0000-0000-0000-999999999999/summarize",
        json={
            "openrouter_api_key": "sk-or-v1-test-key",
            "model_id": "anthropic/claude-3.5-sonnet"
        }
    )
    
    assert response.status_code == 404
    assert 'not found' in response.json()['detail'].lower()
