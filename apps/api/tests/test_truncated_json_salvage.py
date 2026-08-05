"""
A 65-second call threw away fourteen good questions because the fifteenth
was cut off.

Question generation asks the model for 15 detailed questions. At
max_tokens=4000 the response sometimes stopped mid-object, _repair appended
closing brackets to output that was malformed deeper in, and the route
returned 400 Bad Request — telling the caller to fix a request that was
perfectly valid.

Three fixes, in order of how much they matter:
  1. salvage the complete items from a truncated array;
  2. raise the ceiling so truncation is rare rather than routine;
  3. report a bad model response as 502, not 400.
"""
import json

import pytest

from src.utils.json_repair import _salvage_truncated_array, parse_llm_json


def _array(n):
    return "[" + ",".join(
        '{"question_text": "Q%d about the design", "category": "methodology"}' % i
        for i in range(1, n + 1)
    ) + "]"


class TestSalvage:
    def test_recovers_complete_items_from_a_truncated_array(self):
        full = _array(14)
        truncated = full[:full.rindex("}") - 30]
        out = parse_llm_json(truncated, stage="question_generation")
        assert len(out) == 13
        assert out[0]["question_text"] == "Q1 about the design"
        assert all("question_text" in q for q in out)

    def test_a_well_formed_array_is_untouched(self):
        assert len(parse_llm_json(_array(14), stage="x")) == 14

    def test_truncation_inside_a_string_still_salvages_earlier_items(self):
        """The commonest shape: the cut lands mid-value."""
        full = _array(6)
        truncated = full[:full.index('"Q5') + 2]
        out = parse_llm_json(truncated, stage="x")
        assert len(out) == 4

    @pytest.mark.parametrize("garbage", [
        "not json at all",
        "",
        "Here is my answer: I could not comply.",
    ])
    def test_garbage_still_raises(self, garbage):
        with pytest.raises(ValueError):
            parse_llm_json(garbage, stage="x")

    def test_a_truncated_object_is_not_treated_as_an_array(self):
        with pytest.raises(ValueError):
            parse_llm_json('{"a": 1, "b": ', stage="x")

    def test_escaped_quotes_do_not_confuse_the_scanner(self):
        raw = '[{"t": "he said \\"no\\" firmly"},{"t": "second"},{"t": "thi'
        out = _salvage_truncated_array(raw)
        assert len(out) == 2
        assert out[0]["t"] == 'he said "no" firmly'

    def test_nested_objects_close_at_the_right_depth(self):
        raw = '[{"a": {"b": 1}},{"a": {"b": 2}},{"a": {"b'
        out = _salvage_truncated_array(raw)
        assert out == [{"a": {"b": 1}}, {"a": {"b": 2}}]

    def test_returns_none_when_nothing_complete_yet(self):
        assert _salvage_truncated_array('[{"a": 1') is None

    def test_non_array_input_is_declined(self):
        assert _salvage_truncated_array('{"a": 1}') is None


class TestRoomToGenerate:
    def test_token_ceiling_fits_fifteen_detailed_questions(self):
        import inspect
        from src.services import question_generator

        src = inspect.getsource(question_generator)
        assert "max_tokens=4000" not in src
        assert "max_tokens=8000" in src


class TestStatusCode:
    def test_bad_model_output_is_not_a_client_error(self):
        import inspect
        from src.routes import defense

        src = inspect.getsource(defense)
        assert "status_code=502" in src, (
            "a malformed model response must not be reported as 400"
        )
