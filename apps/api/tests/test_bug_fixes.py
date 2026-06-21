"""
Regression tests for the PeerForge bug-report fixes.

Covers the high-value backend bugs:
  BUG-020/021/026 — inline TEXT/LINK materials must be chunked and retrievable
                    (previously stored but invisible → "0 materials analyzed").
  BUG-024         — placeholder citations must be stripped from responses.
  BUG-017/start   — a session cannot start without a panel.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from src.main import app
from src.database import get_db_connection, get_cursor

client = TestClient(app)
WORKSPACE = "00000000-0000-0000-0000-000000000101"


def _create_debate(title="Bugfix Test"):
    resp = client.post("/debates/setup", json={
        "workspace_id": WORKSPACE,
        "title": title,
        "problem_statement": "Regression test for material grounding and validation.",
        "participants": [],
        "materials": [],
        "reasoning_mode": "light",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["debate_id"]


def test_inline_text_material_is_chunked_and_retrievable():
    """BUG-020/021/026: inline text material → memory_chunks → retrievable."""
    debate_id = _create_debate("Grounding regression")

    resp = client.post(f"/debates/{debate_id}/materials", json={
        "materials": [{
            "kind": "text",
            "title": "Methodology",
            "body_text": (
                "We evaluate on the MIMIC-III dataset with 40000 ICU stays. "
                "Reported metrics: accuracy, precision, recall, F1-score and a "
                "confusion matrix, compared against FedAvg and FedProx baselines."
            ),
        }]
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["materials_added"] == 1
    assert body["chunks_created"] >= 1, "inline text must produce memory_chunks"

    # Chunks must exist in the DB for this debate.
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            "SELECT COUNT(*) AS n FROM memory_chunks WHERE source_debate_id = %s AND agent_id IS NULL",
            (debate_id,),
        )
        assert cur.fetchone()["n"] >= 1

    # Retrieval must surface them (keyword path works without embeddings).
    from src.services.memory_retrieval import retrieve_allowed_chunks
    res = retrieve_allowed_chunks(
        debate_id=debate_id,
        participant_id=None,
        query="what dataset and evaluation metrics were used",
        top_k=5,
        openrouter_key=None,
        use_semantic=False,
    )
    assert res.total_chunks >= 1
    assert "MIMIC-III" in res.chunks[0].chunk_text


def test_inline_materials_replace_is_idempotent():
    """Re-submitting inline materials replaces (not duplicates) prior ones."""
    debate_id = _create_debate("Idempotent materials")
    payload = {"materials": [{"kind": "text", "title": "T", "body_text": "X" * 60}]}

    client.post(f"/debates/{debate_id}/materials", json=payload)
    client.post(f"/debates/{debate_id}/materials", json=payload)

    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            "SELECT COUNT(*) AS n FROM meeting_materials WHERE debate_id = %s AND kind = 'text'",
            (debate_id,),
        )
        assert cur.fetchone()["n"] == 1, "re-submit must replace, not duplicate"


def test_placeholder_citations_are_stripped():
    """BUG-024: fabricated placeholder citations are removed from responses."""
    from src.agent_response_generator import _strip_placeholder_citations
    dirty = "The dataset (Kaggle, URL) shows strong recall (Author, URL) per [website]."
    clean = _strip_placeholder_citations(dirty)
    assert "URL" not in clean
    assert "[website]" not in clean
    assert "dataset" in clean and "recall" in clean


def test_start_requires_panel_members():
    """A session with no panel members cannot start."""
    debate_id = _create_debate("No panel")
    resp = client.post(f"/debates/{debate_id}/start")
    assert resp.status_code == 400
    assert "panel member" in resp.json()["detail"].lower()
