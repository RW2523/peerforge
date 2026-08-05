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


class TestKnowledgeUnitAuthorization:
    """
    Prep packs outlived their sessions and became readable by everyone.

    routes/knowledge.py resolved a unit's workspace THROUGH its debate with a
    LEFT JOIN and "OR d.workspace_id IS NULL", so a unit whose link was NULL
    matched for every caller. The FK was ON DELETE SET NULL, so deleting a
    session silently detached its prep packs rather than removing them —
    measured on the live database, all 16 units were in that state.
    """

    def test_query_requires_the_debate_to_resolve(self):
        import inspect

        from src.routes import knowledge

        import ast
        import textwrap

        # Read the SQL literals, not the comments — the comment explaining the
        # fix quotes the very clause it removed.
        tree = ast.parse(inspect.getsource(knowledge))
        import re

        def _strip_sql_comments(text):
            # The explanation lives inside the query as -- comments and quotes
            # the clause it removed; judge the executable SQL only.
            return " ".join(
                " ".join(re.sub(r"--.*$", "", line).split())
                for line in text.splitlines()
            )

        sql = " ".join(
            _strip_sql_comments(n.value)
            for n in ast.walk(tree)
            if isinstance(n, ast.Constant)
            and isinstance(n.value, str)
            and "agent_knowledge_units" in n.value
        )
        assert sql, "could not find the knowledge query"
        assert "OR d.workspace_id IS NULL" not in sql, (
            "a unit with no resolvable workspace must not match every caller"
        )
        assert "LEFT JOIN debates" not in sql
        assert "JOIN debates d ON aku.source_debate_id = d.debate_id" in sql

    def test_the_dependency_is_not_called_as_a_plain_function(self):
        """get_current_user(authorization) binds x_workspace_id to a
        fastapi Header object, which is truthy — every call 403'd."""
        import inspect

        from src.routes import knowledge

        src = inspect.getsource(knowledge)
        assert "get_current_user(authorization)" not in src
        assert "Depends(get_current_user)" in src

    def test_migration_cascades_instead_of_orphaning(self):
        import pathlib

        sql = pathlib.Path("migrations/014_knowledge_units_cascade.sql").read_text()
        assert "ON DELETE CASCADE" in sql
        assert "DELETE FROM agent_knowledge_units WHERE source_debate_id IS NULL" in sql
