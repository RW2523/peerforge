"""Integration tests for M2 debate control endpoints (DB-backed, no mocks)."""
import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.main import app


client = TestClient(app)


def _add_panelist(debate_id: str):
    """Sessions can only start with at least one panel member."""
    resp = client.post(f"/debates/{debate_id}/participants", json={
        "participants": [{
            "name": "Test Reviewer",
            "role_description": "Methodology reviewer",
            "system_prompt": "You are a methodology reviewer.",
            "model_id": "openai/gpt-4o-mini",
            "model_config": {"temperature": 0.5},
        }]
    })
    assert resp.status_code in (200, 201), resp.text


def test_create_debate(create_debate_payload):
    resp = client.post("/debates", json=create_debate_payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["workspace_id"] == create_debate_payload["workspace_id"]
    assert data["title"] == create_debate_payload["title"]
    assert data["state"] == "pending"
    assert "debate_id" in data


def test_start_pause_resume_end_flow(create_debate_payload):
    # Create
    resp = client.post("/debates", json=create_debate_payload)
    assert resp.status_code == 201, resp.text
    debate_id = resp.json()["debate_id"]
    _add_panelist(debate_id)

    # Start
    resp = client.post(f"/debates/{debate_id}/start")
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] == "running"

    # Pause
    resp = client.post(f"/debates/{debate_id}/pause")
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] == "paused"

    # Resume
    resp = client.post(f"/debates/{debate_id}/resume")
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] == "running"

    # End
    resp = client.post(f"/debates/{debate_id}/end")
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] == "ended"


def test_invalid_transitions(create_debate_payload):
    # Create in pending
    resp = client.post("/debates", json=create_debate_payload)
    assert resp.status_code == 201, resp.text
    debate_id = resp.json()["debate_id"]

    # Cannot pause pending
    resp = client.post(f"/debates/{debate_id}/pause")
    assert resp.status_code == 400, resp.text

    # Cannot resume pending
    resp = client.post(f"/debates/{debate_id}/resume")
    assert resp.status_code == 400, resp.text

    # Cannot end pending
    resp = client.post(f"/debates/{debate_id}/end")
    assert resp.status_code == 400, resp.text


def test_intervene_running_and_paused(create_debate_payload):
    resp = client.post("/debates", json=create_debate_payload)
    assert resp.status_code == 201, resp.text
    debate_id = resp.json()["debate_id"]
    _add_panelist(debate_id)

    # Must start first
    resp = client.post(f"/debates/{debate_id}/start")
    assert resp.status_code == 200, resp.text

    resp = client.post(f"/debates/{debate_id}/intervene", json={"message": "Focus on cost", "tagged_agents": ["Senior Engineer"]})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["debate_id"] == debate_id
    assert data["message"] == "Focus on cost"
    assert "event_id" in data

    # Pause then intervene again
    resp = client.post(f"/debates/{debate_id}/pause")
    assert resp.status_code == 200, resp.text

    resp = client.post(f"/debates/{debate_id}/intervene", json={"message": "Add timeline", "tagged_agents": []})
    assert resp.status_code == 200, resp.text


def test_debate_not_found():
    missing = "00000000-0000-0000-0000-00000000dead"
    resp = client.post(f"/debates/{missing}/start")
    assert resp.status_code == 404, resp.text

