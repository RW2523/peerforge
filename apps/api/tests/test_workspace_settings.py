"""
Tests for workspace settings endpoints (TICKET-12.3)
DB-backed tests, no mocks for core flow
"""

import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

# Demo workspace ID (matches seed data)
WORKSPACE_ID = "00000000-0000-0000-0000-000000000101"


def test_get_workspace_models_returns_defaults():
    """
    GET /workspaces/{workspace_id}/settings/models returns system defaults
    when workspace has not set custom values.
    """
    response = client.get(
        f"/workspaces/{WORKSPACE_ID}/settings/models",
        headers={"Authorization": "Bearer test-jwt-token"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["workspace_id"] == WORKSPACE_ID
    assert "embeddings_model_id" in data
    assert "ocr_model_id" in data
    assert "updated_at" in data
    
    # Should return system defaults (Kimi 2.5 + Qwen 2.5)
    assert data["embeddings_model_id"] == "moonshot/kimi-embeddings-v1"
    assert data["ocr_model_id"] == "qwen/qwen-2.5-72b-instruct"


def test_put_workspace_models_updates_settings():
    """
    PUT /workspaces/{workspace_id}/settings/models updates workspace settings
    and GET returns the updated values.
    """
    # Update settings
    update_response = client.put(
        f"/workspaces/{WORKSPACE_ID}/settings/models",
        headers={"Authorization": "Bearer test-jwt-token"},
        json={
            "embeddings_model_id": "openai/text-embedding-3-small",
            "ocr_model_id": "anthropic/claude-3-haiku"
        }
    )
    
    assert update_response.status_code == 200
    update_data = update_response.json()
    
    assert update_data["workspace_id"] == WORKSPACE_ID
    assert update_data["embeddings_model_id"] == "openai/text-embedding-3-small"
    assert update_data["ocr_model_id"] == "anthropic/claude-3-haiku"
    assert "updated_at" in update_data
    
    # Verify GET returns updated values
    get_response = client.get(
        f"/workspaces/{WORKSPACE_ID}/settings/models",
        headers={"Authorization": "Bearer test-jwt-token"}
    )
    
    assert get_response.status_code == 200
    get_data = get_response.json()
    
    assert get_data["embeddings_model_id"] == "openai/text-embedding-3-small"
    assert get_data["ocr_model_id"] == "anthropic/claude-3-haiku"
    
    # Reset to defaults for other tests
    client.put(
        f"/workspaces/{WORKSPACE_ID}/settings/models",
        headers={"Authorization": "Bearer test-jwt-token"},
        json={
            "embeddings_model_id": "moonshot/kimi-embeddings-v1",
            "ocr_model_id": "qwen/qwen-2.5-72b-instruct"
        }
    )


def test_put_workspace_models_missing_fields():
    """
    PUT with missing fields returns 422 validation error.
    """
    response = client.put(
        f"/workspaces/{WORKSPACE_ID}/settings/models",
        headers={"Authorization": "Bearer test-jwt-token"},
        json={
            "embeddings_model_id": "openai/text-embedding-3-small"
            # Missing ocr_model_id
        }
    )
    
    assert response.status_code == 422  # FastAPI validation error


def test_put_workspace_models_empty_string():
    """
    PUT with empty string model ID returns 422 validation error.
    """
    response = client.put(
        f"/workspaces/{WORKSPACE_ID}/settings/models",
        headers={"Authorization": "Bearer test-jwt-token"},
        json={
            "embeddings_model_id": "",
            "ocr_model_id": "qwen/qwen-2.5-72b-instruct"
        }
    )
    
    assert response.status_code == 422  # FastAPI validation error (minLength: 1)


def test_get_workspace_models_nonexistent_workspace():
    """
    GET for nonexistent workspace returns 404.
    """
    response = client.get(
        "/workspaces/00000000-0000-0000-0000-000000009999/settings/models",
        headers={"Authorization": "Bearer test-jwt-token"}
    )
    
    assert response.status_code == 404


def test_put_workspace_models_nonexistent_workspace():
    """
    PUT for nonexistent workspace returns 404.
    """
    response = client.put(
        "/workspaces/00000000-0000-0000-0000-000000009999/settings/models",
        headers={"Authorization": "Bearer test-jwt-token"},
        json={
            "embeddings_model_id": "openai/text-embedding-3-small",
            "ocr_model_id": "qwen/qwen-2.5-72b-instruct"
        }
    )
    
    assert response.status_code == 404
