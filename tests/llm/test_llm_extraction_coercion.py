"""Extraction-result shape coercion (issue #725).

The nightly run hit ``'str' object has no attribute 'get'`` on a
french-learning item: the model returned ``entities`` as a bare string /
list of strings, and downstream consumers (``process.py`` keyword discovery,
``KBStore.store_entities``) index entities as dicts.  These tests pin the
normalization contract applied when the ``ExtractionResult`` is built —
after it, ``entities`` is ALWAYS ``list[dict]`` and ``key_points`` is ALWAYS
``list[str]``, whatever shape the model returned.
"""

from __future__ import annotations

from autoinfo.llm import (
    _coerce_entities,
    _coerce_relevance_score,
    _coerce_str_list,
    _coerce_text,
)


class TestCoerceEntities:
    def test_dict_list_passthrough(self) -> None:
        value = [{"name": "Paris", "type": "location"}, {"name": "ENQ", "type": "org"}]
        assert _coerce_entities(value) == value

    def test_bare_string_split_on_delimiters(self) -> None:
        assert _coerce_entities("Fausses alertes, le parquet de Paris") == [
            {"name": "Fausses alertes"},
            {"name": "le parquet de Paris"},
        ]

    def test_bare_string_cjk_delimiters(self) -> None:
        assert _coerce_entities("巴黎检察院；假警报、爆炸") == [
            {"name": "巴黎检察院"},
            {"name": "假警报"},
            {"name": "爆炸"},
        ]

    def test_list_of_strings_become_name_dicts(self) -> None:
        assert _coerce_entities(["ENQ", " Paris "]) == [{"name": "ENQ"}, {"name": "Paris"}]

    def test_mixed_list_drops_non_name_entries(self) -> None:
        value = [{"name": "ENQ"}, {"type": "org"}, "Paris", 42, None, {"name": ""}]
        assert _coerce_entities(value) == [{"name": "ENQ"}, {"name": "Paris"}]

    def test_dict_name_coerced_to_str(self) -> None:
        assert _coerce_entities([{"name": 2026}]) == [{"name": "2026"}]

    def test_empty_and_none_shapes(self) -> None:
        assert _coerce_entities(None) == []
        assert _coerce_entities([]) == []
        assert _coerce_entities("") == []
        assert _coerce_entities(3.14) == []


class TestCoerceStrList:
    def test_list_passthrough(self) -> None:
        assert _coerce_str_list(["a", "b"]) == ["a", "b"]

    def test_bare_string_single_element(self) -> None:
        assert _coerce_str_list("one point") == ["one point"]

    def test_drops_non_strings(self) -> None:
        assert _coerce_str_list(["ok", 5, None, {"x": 1}, "  "]) == ["ok"]

    def test_empty_and_none(self) -> None:
        assert _coerce_str_list(None) == []
        assert _coerce_str_list([]) == []
        assert _coerce_str_list("") == []


class TestCoerceText:
    def test_str_passthrough_and_empty(self) -> None:
        assert _coerce_text("fine") == "fine"
        assert _coerce_text("") == ""
        assert _coerce_text(None) == ""

    def test_non_string_degrades_to_str(self) -> None:
        assert _coerce_text(42) == "42"
        assert _coerce_text({"a": 1}) == "{'a': 1}"


class TestCoerceRelevanceScore:
    def test_numeric_clamped(self) -> None:
        assert _coerce_relevance_score(120) == 100.0
        assert _coerce_relevance_score(-3) == 0.0
        assert _coerce_relevance_score("87.5") == 87.5

    def test_verbal_label_degrades_to_zero(self) -> None:
        # float("high") used to raise ValueError and fail the whole item.
        assert _coerce_relevance_score("high") == 0.0
        assert _coerce_relevance_score(None) == 0.0
        assert _coerce_relevance_score({"score": 90}) == 0.0
