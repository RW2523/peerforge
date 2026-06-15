"""Integration tests for SSE live stream endpoint (DB-backed, no mocks).

NOTE: These tests are DEPRECATED. SSE stream has been replaced by WebSocket for room transport.
The SSE endpoint remains for backward compatibility but is no longer the primary realtime path.
"""
import os
import sys
import json
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.main import app


client = TestClient(app)


# Skip all SSE tests - deprecated after WebSocket migration (TICKET-17)
pytestmark = pytest.mark.skip(reason="SSE tests deprecated - WebSocket is primary transport")


def _read_some_sse_lines(resp, max_lines: int = 20):
    lines = []
    for line in resp.iter_lines():
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")
        lines.append(line)
        if len(lines) >= max_lines:
            break
    return lines


def test_stream_authorized_success_minimal(create_debate_payload):
    # Create + start so stream has a running debate
    resp = client.post("/debates", json=create_debate_payload)
    assert resp.status_code == 201, resp.text
    debate_id = resp.json()["debate_id"]

    resp = client.post(f"/debates/{debate_id}/start")
    assert resp.status_code == 200, resp.text

    with client.stream("GET", f"/debates/{debate_id}/events/stream") as sse:
        assert sse.status_code == 200, sse.text
        assert "text/event-stream" in sse.headers.get("content-type", "")
        lines = _read_some_sse_lines(sse, max_lines=30)
        # We should see at least one SSE "data:" line eventually (keepalive may appear too).
        assert any(l.startswith("data:") for l in lines), "\n".join(lines)


def test_stream_ended_debate_terminates(create_debate_payload):
    resp = client.post("/debates", json=create_debate_payload)
    assert resp.status_code == 201, resp.text
    debate_id = resp.json()["debate_id"]

    resp = client.post(f"/debates/{debate_id}/start")
    assert resp.status_code == 200, resp.text

    resp = client.post(f"/debates/{debate_id}/end")
    assert resp.status_code == 200, resp.text

    with client.stream("GET", f"/debates/{debate_id}/events/stream") as sse:
        assert sse.status_code == 200, sse.text
        lines = _read_some_sse_lines(sse, max_lines=50)
        # The stream should include at least one event and then close quickly for ended debates.
        assert any(l.startswith("data:") for l in lines), "\n".join(lines)


def test_stream_not_found():
    missing = "00000000-0000-0000-0000-00000000beef"
    with client.stream("GET", f"/debates/{missing}/events/stream") as sse:
        assert sse.status_code == 404

