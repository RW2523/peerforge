"""Tests for M4 meeting setup endpoints (TICKET-08B.1)"""
import pytest
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_auth_for_setup_tests():
    """Disable auth requirement for setup tests"""
    from src.config import settings
    original = settings.require_auth
    settings.require_auth = False
    yield
    settings.require_auth = original


def test_get_agent_templates():
    """Test GET /agent-templates returns expected structure and category coverage"""
    response = client.get("/agent-templates")
    
    assert response.status_code == 200
    templates = response.json()
    
    assert isinstance(templates, list)
    assert len(templates) >= 6  # At least 6 templates
    
    # Check that all templates have required structure
    for template in templates:
        assert 'template_id' in template
        assert 'label' in template
        assert 'role_title' in template
        assert 'system_prompt' in template
        assert 'model_id' in template
        assert 'model_config' in template
        assert 'category' in template  # New field
        # character is optional (some templates may not have it)
        
        # Validate structure types
        assert isinstance(template['template_id'], str)
        assert isinstance(template['label'], str)
        assert isinstance(template['system_prompt'], str)
        assert isinstance(template['model_id'], str)
        assert isinstance(template['model_config'], dict)
        assert isinstance(template['category'], str)
    
    # Verify category coverage (ensure diversity of academic reviewer templates)
    categories = {t['category'] for t in templates}
    assert 'Methods' in categories
    assert 'Domain' in categories
    assert 'Critics' in categories
    assert len(categories) >= 3  # At least 3 different categories


def test_create_and_list_agents():
    """Test POST /agents then GET /agents"""
    workspace_id = '00000000-0000-0000-0000-000000000101'
    
    # Create agent
    create_response = client.post("/agents", json={
        "workspace_id": workspace_id,
        "name": "Test PM Agent",
        "role_description": "Product Manager for testing",
        "system_prompt": "You are a test product manager.",
        "model_id": "anthropic/claude-3.5-sonnet",
        "agent_model_config": {"temperature": 0.7, "max_tokens": 2000}
    })
    
    assert create_response.status_code == 201
    agent = create_response.json()
    
    assert 'agent_id' in agent
    assert agent['workspace_id'] == workspace_id
    assert agent['name'] == "Test PM Agent"
    assert agent['system_prompt'] == "You are a test product manager."
    assert agent['model_id'] == "anthropic/claude-3.5-sonnet"
    assert agent['model_config']['temperature'] == 0.7
    
    # List agents
    list_response = client.get(f"/agents?workspace_id={workspace_id}")
    
    assert list_response.status_code == 200
    agents = list_response.json()
    
    assert isinstance(agents, list)
    assert len(agents) > 0
    
    # Find our created agent
    created_agent = next((a for a in agents if a['agent_id'] == agent['agent_id']), None)
    assert created_agent is not None
    assert created_agent['name'] == "Test PM Agent"


def test_debate_setup_with_inline_participants():
    """Test POST /debates/setup with inline participant configs"""
    workspace_id = '00000000-0000-0000-0000-000000000101'
    
    response = client.post("/debates/setup", json={
        "workspace_id": workspace_id,
        "title": "Q1 Feature Planning",
        "problem_statement": "What features should we prioritize in Q1?",
        "timebox_minutes": 30,
        "participants": [
            {
                "name": "Product Manager",
                "role_description": "PM",
                "system_prompt": "You are a product manager.",
                "model_id": "anthropic/claude-3.5-sonnet",
                "model_config": {"temperature": 0.7}
            },
            {
                "name": "Engineer",
                "system_prompt": "You are an engineer.",
                "model_id": "anthropic/claude-3.5-sonnet",
                "model_config": {"temperature": 0.6}
            }
        ],
        "materials": [
            {
                "kind": "text",
                "title": "Context",
                "body_text": "Our users want better collaboration features."
            },
            {
                "kind": "link",
                "title": "User Research",
                "url": "https://example.com/research"
            }
        ]
    })
    
    assert response.status_code == 201
    data = response.json()
    
    assert 'debate_id' in data
    assert 'participant_ids' in data
    assert 'material_ids' in data
    
    assert len(data['participant_ids']) == 2
    assert len(data['material_ids']) == 2
    
    # Verify debate was created
    debate_id = data['debate_id']
    from src.debate_service import DebateService
    service = DebateService()
    debate = service.get_debate(debate_id)
    
    assert debate is not None
    assert debate['title'] == "Q1 Feature Planning"
    assert debate['state'] == 'pending'
    assert 'problem_statement' in debate['policy_config']
    assert debate['policy_config']['problem_statement'] == "What features should we prioritize in Q1?"
    assert debate['policy_config']['timebox_minutes'] == 30


def test_debate_setup_with_agent_references():
    """Test POST /debates/setup with references to existing agents"""
    from src.debate_service import DebateService
    workspace_id = '00000000-0000-0000-0000-000000000101'
    
    # Create a persistent agent first
    agent_response = client.post("/agents", json={
        "workspace_id": workspace_id,
        "name": "Persistent PM",
        "system_prompt": "You are a persistent product manager.",
        "model_id": "anthropic/claude-3.5-sonnet",
        "agent_model_config": {}
    })
    agent_id = agent_response.json()['agent_id']
    
    # Create debate referencing this agent
    response = client.post("/debates/setup", json={
        "workspace_id": workspace_id,
        "title": "Strategy Session",
        "problem_statement": "Should we pivot our product strategy?",
        "participants": [
            {"agent_id": agent_id}
        ],
        "materials": []
    })
    
    assert response.status_code == 201
    data = response.json()
    
    assert len(data['participant_ids']) == 1
    assert len(data['material_ids']) == 0


def test_debate_setup_participant_limit():
    """Test that debate setup enforces participant limits"""
    workspace_id = '00000000-0000-0000-0000-000000000101'
    
    # Try to create with 9 participants (max is 8)
    participants = [
        {
            "name": f"Agent {i}",
            "system_prompt": "Test",
            "model_id": "anthropic/claude-3.5-sonnet"
        }
        for i in range(9)
    ]
    
    response = client.post("/debates/setup", json={
        "workspace_id": workspace_id,
        "title": "Too Many Participants",
        "problem_statement": "Test",
        "participants": participants,
        "materials": []
    })
    
    assert response.status_code == 400
    assert 'maximum' in response.json()['detail'].lower()


def test_debate_setup_allows_deferred_staffing_but_start_requires_panel():
    """Setup may create a session with an empty panel (deferred staffing —
    the wizard uploads materials before panel selection), but the session
    cannot START until at least one panel member exists."""
    workspace_id = '00000000-0000-0000-0000-000000000101'

    response = client.post("/debates/setup", json={
        "workspace_id": workspace_id,
        "title": "No Participants Yet",
        "problem_statement": "Test deferred staffing",
        "participants": [],
        "materials": []
    })
    assert response.status_code == 201
    debate_id = response.json()['debate_id']

    start = client.post(f"/debates/{debate_id}/start")
    assert start.status_code == 400
    assert 'panel member' in start.json()['detail'].lower()


def test_debate_setup_inline_participant_validation():
    """Test that inline participants require name, system_prompt, model_id"""
    workspace_id = '00000000-0000-0000-0000-000000000101'
    
    response = client.post("/debates/setup", json={
        "workspace_id": workspace_id,
        "title": "Invalid Participant",
        "problem_statement": "Test",
        "participants": [
            {
                "name": "Agent",
                # Missing system_prompt and model_id
            }
        ],
        "materials": []
    })
    
    assert response.status_code == 400
    assert 'require' in response.json()['detail'].lower()
