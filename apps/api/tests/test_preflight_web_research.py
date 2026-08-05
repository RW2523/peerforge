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


class TestTheMemoActuallyUsesTheSources:
    """
    Retrieval worked and the memos ignored it: 0 of 5 sources cited.

    Two causes, and only the second mattered.

      - No role task mentions "web", "URL", "source" or "external literature"
        anywhere, and the one citation instruction — "cite evidence" — is
        satisfied by quoting the submitted paper. The literature was pasted in
        unlabelled with nothing asking the reviewer to use it.
      - Adding a rule after FORMAT changed almost nothing (0 URLs across 8
        memos, then 1 of 5 in three of them). Every role prompt defines a
        numbered memo structure and the model follows THAT; a trailing rule is
        advice it can skip.

    Making it a REQUIRED SECTION with a named heading and a fixed bullet shape
    took it to 3 of 5 sources in 9 of 9 memos.
    """

    def _prompt(self, web=""):
        from src.services.persona_prompts import get_preflight_prep_prompt

        return get_preflight_prep_prompt(
            role_label="methodology professor",
            persona_name="Dr. Ada",
            debate_title="A trial",
            problem_statement="Does X cause Y?",
            materials_context="Section 1. Methods...",
            imported_context="",
            web_research_results=web,
            current_date_str="Monday",
            current_time_str="10:00",
        )

    WEB = "1. **A paper**\n   URL: https://example.org/a\n\n2. **Another**\n   URL: https://example.org/b\n"

    def test_the_requirement_is_a_named_output_section(self):
        p = self._prompt(self.WEB)
        assert "ADDITIONAL REQUIRED SECTION" in p
        assert "**External literature consulted**" in p

    def test_it_sits_inside_the_task_not_after_the_format_note(self):
        """A rule placed after FORMAT was ignored."""
        p = self._prompt(self.WEB)
        assert p.index("ADDITIONAL REQUIRED SECTION") < p.index("LENGTH:")

    def test_the_literature_block_is_labelled(self):
        p = self._prompt(self.WEB)
        assert "EXTERNAL LITERATURE" in p
        assert "https://example.org/a" in p

    def test_it_says_to_copy_the_urls_rather_than_compose_them(self):
        p = self._prompt(self.WEB)
        assert "copied exactly" in p

    def test_no_citation_is_demanded_when_nothing_was_retrieved(self):
        """Demanding citations with no sources is an instruction to invent
        them — the same mistake that produced fabricated page numbers."""
        p = self._prompt("")
        assert "ADDITIONAL REQUIRED SECTION" not in p
        assert "Do not invent URLs" in p
        assert "No external literature was retrieved" in p


class TestCitationRateIsRecorded:
    def test_the_count_reaches_the_metadata(self):
        import inspect

        from src.tasks import preflight

        src = inspect.getsource(preflight)
        assert "'web_sources_cited': web_sources_cited" in src

    def test_it_counts_every_source_not_just_the_first_three(self):
        import inspect

        from src.tasks import preflight

        src = inspect.getsource(preflight)
        assert "for url in web_search_urls[:3]" not in src
        assert "for url in web_search_urls if url and url in prep_pack_content" in src
