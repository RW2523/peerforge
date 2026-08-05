"""
Grounding was silently dead for any session whose chunks carried a
non-uuid material_id.

_fetch_material_chunks joined with

    ON (mc.chunk_metadata->>'material_id')::uuid = mm.material_id

but that field is not reliably a uuid. Across the live table it was NULL for
350 chunks and the literal string 'mat1' for 70 more, and the cast raised
InvalidTextRepresentation. The only caller wraps grounding in a bare except
and logs a warning, so affected sessions produced ZERO citations and the
Glass-Box lineage looked empty rather than broken.
"""
import re

import pytest


def test_join_compares_material_id_as_text():
    import inspect

    from src.services import provenance

    src = inspect.getsource(provenance)
    assert "::uuid = mm.material_id" not in src, (
        "casting chunk_metadata->>'material_id' to uuid raises on non-uuid values"
    )
    assert src.count("mc.chunk_metadata->>'material_id' = mm.material_id::text") == 3, (
        "every material join must compare as text"
    )


def test_non_uuid_material_id_does_not_raise(monkeypatch):
    """The exact shape that broke it: a chunk tagged 'mat1'."""
    from src.services import provenance

    captured = {}

    class _Cur:
        def execute(self, sql, params=None):
            captured["sql"] = sql
            # Postgres would raise here if the SQL cast the text to uuid.
            assert "::uuid = mm.material_id" not in sql

        def fetchall(self):
            return [{
                "chunk_id": "00000000-0000-0000-0000-000000000001",
                "chunk_text": "Section 2.1 Participant Selection. Forty undergraduates.",
                "chunk_metadata": {"material_id": "mat1", "sha256": None, "page_num": None},
                "doc_title": "uploaded document",
            }]

    class _Conn:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(provenance, "get_db_connection", lambda: _Conn())
    monkeypatch.setattr(provenance, "get_cursor", lambda conn: _Cur())

    chunks = provenance._fetch_material_chunks("11111111-1111-1111-1111-111111111111")
    assert len(chunks) == 1
    assert chunks[0]["material_id"] == "mat1"
