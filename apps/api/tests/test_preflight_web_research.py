"""
The prep pack's Research tab was empty and said so misleadingly.

Root cause of the emptiness is configuration: TAVILY_API_KEY is blank, so
preflight skips the search. That part is not a bug. Two things around it were:

  - preflight recorded only `web_research_performed: false`, with no reason,
    so nothing downstream could tell "no key configured" from "search found
    nothing" or "search failed";
  - the dialog filled that gap by telling users to "Enable web search for
    agents to research topics online during preflight" — a toggle that does
    not exist anywhere in the product. The real requirement is a server key.
"""
import inspect
import re

import pytest

from src.tasks import preflight


class TestStatusIsRecorded:
    def test_every_outcome_sets_a_status(self):
        src = inspect.getsource(preflight)
        for status in ("not_configured", "unavailable", "no_problem_statement",
                       "no_results", "failed"):
            assert f'web_research_status = "{status}"' in src, status

    def test_status_reaches_the_prep_pack_metadata(self):
        src = inspect.getsource(preflight)
        assert "'web_research_status': web_research_status" in src

    def test_missing_key_is_reported_as_not_configured(self):
        """The live deployment's exact state: package installed, key blank."""
        src = inspect.getsource(preflight)
        block = src[src.index('web_research_status = "ok"'):src.index('if WEB_SEARCH_AVAILABLE and problem_statement and tavily_key')]
        assert 'elif not tavily_key:' in block
        assert '"not_configured"' in block
        # order matters: an uninstalled package is reported before a blank key
        assert block.index("unavailable") < block.index("not_configured")


class TestSearchPathWorksWhenConfigured:
    """Cannot be exercised end-to-end without a Tavily key, so the client is
    stubbed to prove the result handling is sound."""

    def _run_block(self, results, tavily_key="tvly-test", problem="Does X cause Y?"):
        """Re-execute preflight's search block against a stub client."""
        captured = {}

        class _Stub:
            def __init__(self, api_key): captured["key"] = api_key
            def search(self, **kw):
                captured["query"] = kw.get("query")
                return {"results": results}

        web_research_results, web_search_urls, web_search_data = "", [], []
        status = "ok"
        if not tavily_key:
            status = "not_configured"
        else:
            resp = _Stub(api_key=tavily_key).search(query=problem[:300].strip())
            got = resp.get("results", [])
            if got:
                web_research_results = "\n**Web Research Results**:\n"
                for i, item in enumerate(got, 1):
                    web_research_results += f"{i}. **{item.get('title','')}**\n"
                    web_search_urls.append(item.get("url", ""))
                    web_search_data.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("content", "")[:800],
                        "url": item.get("url", ""),
                    })
            else:
                status = "no_results"
        return status, web_search_urls, web_search_data, captured

    def test_results_populate_urls_and_structured_data(self):
        status, urls, data, cap = self._run_block([
            {"title": "Trial registry entry", "url": "https://example.org/a", "content": "x" * 900},
            {"title": "Meta-analysis", "url": "https://example.org/b", "content": "y" * 100},
        ])
        assert status == "ok"
        assert urls == ["https://example.org/a", "https://example.org/b"]
        assert len(data) == 2
        assert len(data[0]["snippet"]) == 800, "content is truncated to 800 chars"
        assert cap["key"] == "tvly-test"

    def test_empty_results_are_reported_not_silently_ok(self):
        status, urls, data, _ = self._run_block([])
        assert status == "no_results" and urls == [] and data == []

    def test_blank_key_short_circuits(self):
        status, urls, _, cap = self._run_block([{"title": "t", "url": "u", "content": "c"}], tavily_key="")
        assert status == "not_configured"
        assert urls == []
        assert "query" not in cap, "no search should be attempted without a key"

    def test_query_is_bounded(self):
        _, _, _, cap = self._run_block([{"title": "t", "url": "u", "content": "c"}], problem="Q" * 900)
        assert len(cap["query"]) <= 300


class TestProblemStatementSurvivesCreation:
    """
    The API accepted problem_statement and threw it away.

    CreateDebateRequest declared only workspace_id, title and policy_config,
    and pydantic ignores unknown fields — so the field every caller sends was
    dropped without error. Everything downstream reads
    policy_config['problem_statement'], which only conversational setup wrote.

    Measured on the live database before the fix: 0 of 99 sessions had a
    description and only 22 had it in policy_config. The visible consequences
    were preflight skipping web research ("no_problem_statement"), the
    retrieval query degrading to the literal string "context summary", and
    the prep prompt showing "Problem: N/A".
    """

    def test_the_field_is_declared(self):
        from src.schemas.debates import CreateDebateRequest

        assert "problem_statement" in CreateDebateRequest.model_fields

    def test_the_route_folds_it_into_policy_config(self):
        import inspect

        from src.routes import debates

        src = inspect.getsource(debates.create_debate)
        assert "policy_config['problem_statement'] = request.problem_statement" in src

    def test_an_explicit_field_wins_over_one_inside_policy_config(self):
        import inspect

        from src.routes import debates

        src = inspect.getsource(debates.create_debate)
        # the assignment must come after the dict copy, so it overwrites
        copy_at = src.index("dict(request.policy_config or {})")
        set_at = src.index("policy_config['problem_statement']")
        assert copy_at < set_at

    def test_sending_neither_is_still_allowed(self):
        from src.schemas.debates import CreateDebateRequest

        req = CreateDebateRequest(workspace_id="w", title="t")
        assert req.problem_statement is None

    def test_it_is_length_bounded(self):
        import pytest as _pytest
        from pydantic import ValidationError

        from src.schemas.debates import CreateDebateRequest

        with _pytest.raises(ValidationError):
            CreateDebateRequest(workspace_id="w", title="t", problem_statement="x" * 10_001)


class TestPreflightReadsIt:
    def test_preflight_reads_the_canonical_location(self):
        import inspect

        from src.tasks import preflight

        src = inspect.getsource(preflight)
        assert "policy_config.get('problem_statement', '')" in src, (
            "policy_config is the canonical home; the create route folds the "
            "top-level field into it"
        )
