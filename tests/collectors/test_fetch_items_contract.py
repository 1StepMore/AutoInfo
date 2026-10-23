"""Coverage lock for the #580 ``fetch_items(ctx)`` contract.

One file drives every collector's uniform entry point (including the
error/limit/fallback branches) so the extracted contract stays covered
without duplicating each handler's existing test module.  All network seams
are patched; nothing here performs I/O.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from autoinfo.collectors.base import CollectorContext
from autoinfo.collectors.bilibili import BilibiliHandler
from autoinfo.collectors.dblp import DBLPHandler
from autoinfo.collectors.email_imap import EmailHandler
from autoinfo.collectors.pdf import PDFHandler
from autoinfo.collectors.pubmed import PubMedHandler
from autoinfo.collectors.quandl import QuandlHandler
from autoinfo.collectors.rss import RSSHandler
from autoinfo.collectors.web import WebHandler
from autoinfo.collectors.web_playwright import PlaywrightWebHandler
from autoinfo.collectors.yahoo_finance import YahooFinanceHandler
from autoinfo.config import SourceConfig
from autoinfo.models import Item


def _item(source_name: str = "test") -> Item:
    return Item(
        id="i1",
        source_name=source_name,
        source_type="test",
        source_url="https://example.com/a",
        title="Title",
        content="Content",
    )


URL_HANDLERS = [
    (RSSHandler, "rss"),
    (WebHandler, "web"),
    (PDFHandler, "pdf"),
    (YahooFinanceHandler, "yahoo_finance"),
    (PlaywrightWebHandler, "web"),
]


class TestURLDrivenCollectors:
    """RSS/Web/PDF/Yahoo/Playwright share the url + limit contract shape."""

    @pytest.mark.parametrize(("handler_cls", "source_name"), URL_HANDLERS)
    def test_missing_url_returns_empty(self, handler_cls: type, source_name: str) -> None:
        handler = handler_cls()
        assert handler.fetch_items(CollectorContext()) == []

    @pytest.mark.parametrize(("handler_cls", "source_name"), URL_HANDLERS)
    def test_none_limit_returns_everything(self, handler_cls: type, source_name: str) -> None:
        handler = handler_cls()
        items = [_item(source_name), _item(source_name)]
        with patch.object(handler_cls, "fetch", return_value=items) as fetch:
            result = handler.fetch_items(CollectorContext(url="https://example.com/feed"))
        assert result == items
        fetch.assert_called_once_with("https://example.com/feed")

    @pytest.mark.parametrize(("handler_cls", "source_name"), URL_HANDLERS)
    def test_numeric_limit_slices_and_falls_back_to_source_config_url(
        self, handler_cls: type, source_name: str
    ) -> None:
        handler = handler_cls()
        source = SourceConfig(name=source_name, type="rss", url="https://example.com/from-config")
        items = [_item(source_name), _item(source_name)]
        with patch.object(handler_cls, "fetch", return_value=items) as fetch:
            result = handler.fetch_items(CollectorContext(source_config=source, limit=1))
        assert result == items[:1]
        fetch.assert_called_once_with("https://example.com/from-config")


class TestQuandlCollector:
    def _handler(self, **kwargs: Any) -> QuandlHandler:
        settings = kwargs.pop("settings", {})
        return QuandlHandler(
            SourceConfig(
                name="quandl-test",
                type="quandl",
                url=kwargs.pop("url", "https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json"),
                settings=settings,
            )
        )

    def test_missing_url_returns_empty(self) -> None:
        handler = self._handler(url="")
        assert handler.fetch_items(CollectorContext()) == []

    def test_missing_query_returns_empty(self) -> None:
        handler = self._handler(url="https://example.com/q.json")
        assert handler.fetch_items(CollectorContext(url="https://example.com/q.json")) == []

    def test_topic_query_and_limit(self) -> None:
        handler = self._handler()
        item = _item("quandl")
        with patch.object(QuandlHandler, "fetch", return_value=[item]) as fetch:
            result = handler.fetch_items(
                CollectorContext(url="https://example.com/q.json", topic="AAPL", limit=1)
            )
        assert result == [item]
        fetch.assert_called_once_with("https://example.com/q.json", query="AAPL", limit=1)

    def test_query_field_fallback(self) -> None:
        handler = self._handler()
        with patch.object(QuandlHandler, "fetch", return_value=[]) as fetch:
            handler.fetch_items(
                CollectorContext(url="https://example.com/q.json", query="from-ctx")
            )
        assert fetch.call_args.kwargs["query"] == "from-ctx"

    def test_settings_query_from_context(self) -> None:
        handler = self._handler()
        with patch.object(QuandlHandler, "fetch", return_value=[]) as fetch:
            handler.fetch_items(
                CollectorContext(
                    url="https://example.com/q.json",
                    settings={"query": "from-settings"},
                )
            )
        assert fetch.call_args.kwargs["query"] == "from-settings"

    def test_settings_query_from_source_config(self) -> None:
        handler = self._handler(settings={"query": "from-config"})
        with patch.object(QuandlHandler, "fetch", return_value=[]) as fetch:
            handler.fetch_items(CollectorContext(url="https://example.com/q.json"))
        assert fetch.call_args.kwargs["query"] == "from-config"


class TestBilibiliCollector:
    def test_topic_sets_unset_query(self) -> None:
        handler = BilibiliHandler({"query": ""})
        with (
            patch.object(BilibiliHandler, "fetch", return_value=[{"id": "1"}]) as fetch,
            patch.object(BilibiliHandler, "to_item", return_value=_item("bilibili")),
        ):
            result = handler.fetch_items(CollectorContext(topic="大模型", limit=1))
        assert len(result) == 1
        assert handler.query == "大模型"
        fetch.assert_called_once_with(limit=1)

    def test_existing_query_is_not_overwritten(self) -> None:
        handler = BilibiliHandler({"query": "configured"})
        with (
            patch.object(BilibiliHandler, "fetch", return_value=[]),
            patch.object(BilibiliHandler, "to_item", return_value=_item("bilibili")),
        ):
            handler.fetch_items(CollectorContext(topic="ignored"))
        assert handler.query == "configured"


class TestDBLPCollector:
    def test_topic_is_used_as_query(self) -> None:
        handler = DBLPHandler()
        with (
            patch.object(DBLPHandler, "fetch", return_value=[{"id": "1"}]) as fetch,
            patch.object(DBLPHandler, "to_item", return_value=_item("dblp")),
        ):
            result = handler.fetch_items(CollectorContext(topic="machine learning", limit=3))
        assert len(result) == 1
        fetch.assert_called_once_with("machine learning", limit=3)

    def test_empty_topic_still_calls_fetch(self) -> None:
        handler = DBLPHandler()
        with (
            patch.object(DBLPHandler, "fetch", return_value=[]) as fetch,
            patch.object(DBLPHandler, "to_item", return_value=_item("dblp")),
        ):
            assert handler.fetch_items(CollectorContext()) == []
        fetch.assert_called_once_with("", limit=10)


class TestEmailCollector:
    def test_settings_and_since_date(self) -> None:
        handler = EmailHandler()
        items = [_item("email"), _item("email")]
        ctx = CollectorContext(
            settings={
                "host": "imap.example.com",
                "username": "user",
                "password": "secret",
                "since_date": "2026-01-01",
            }
        )
        with patch.object(EmailHandler, "collect", return_value=items) as collect:
            result = handler.fetch_items(ctx)
        assert result == items
        config = collect.call_args.args[0]
        assert config["host"] == "imap.example.com"
        assert config["since_date"] == "2026-01-01"

    def test_url_host_and_numeric_limit(self) -> None:
        handler = EmailHandler()
        items = [_item("email"), _item("email")]
        with patch.object(EmailHandler, "collect", return_value=items) as collect:
            result = handler.fetch_items(CollectorContext(url="imap.example.com", limit=1))
        assert result == items[:1]
        assert collect.call_args.args[0]["host"] == "imap.example.com"

    def test_source_config_settings_fallback(self) -> None:
        handler = EmailHandler()
        source = SourceConfig(
            name="email",
            type="email_imap",
            settings={"host": "from-config", "username": "u", "password": "p"},
        )
        with patch.object(EmailHandler, "collect", return_value=[]) as collect:
            handler.fetch_items(CollectorContext(source_config=source))
        assert collect.call_args.args[0]["host"] == "from-config"


class TestPubMedCollector:
    def test_explicit_pmids_skip_search(self) -> None:
        handler = PubMedHandler()
        with (
            patch.object(PubMedHandler, "search") as search,
            patch.object(PubMedHandler, "fetch", return_value=[{"pmid": "1"}]) as fetch,
            patch.object(PubMedHandler, "to_item", return_value=_item("pubmed")),
        ):
            result = handler.fetch_items(CollectorContext(pmids=["1"], limit=5))
        assert len(result) == 1
        search.assert_not_called()
        fetch.assert_called_once_with(["1"])

    def test_topic_searches_then_fetches(self) -> None:
        handler = PubMedHandler()
        with (
            patch.object(PubMedHandler, "search", return_value=["42"]) as search,
            patch.object(PubMedHandler, "fetch", return_value=[{"pmid": "42"}]) as fetch,
            patch.object(PubMedHandler, "to_item", return_value=_item("pubmed")),
        ):
            handler.fetch_items(CollectorContext(topic="IVF", limit=5))
        search.assert_called_once_with("IVF", max_results=5)
        fetch.assert_called_once_with(["42"])

    def test_keyword_fallback(self) -> None:
        handler = PubMedHandler()
        with (
            patch.object(PubMedHandler, "search", return_value=[]) as search,
            patch.object(PubMedHandler, "fetch", return_value=[]),
            patch.object(PubMedHandler, "to_item", return_value=_item("pubmed")),
        ):
            assert handler.fetch_items(CollectorContext(keywords=["oncology"])) == []
        search.assert_called_once_with("oncology", max_results=10)

    def test_source_name_fallback_and_empty_result(self) -> None:
        handler = PubMedHandler()
        source = SourceConfig(name="my-pubmed", type="api")
        with patch.object(PubMedHandler, "search", return_value=[]) as search:
            assert handler.fetch_items(CollectorContext(source_config=source)) == []
        search.assert_called_once_with("my-pubmed", max_results=10)


class TestCollectorContext:
    def test_resolved_limit_preserves_zero_and_none(self) -> None:
        assert CollectorContext(limit=None).resolved_limit(7) == 7
        assert CollectorContext(limit=0).resolved_limit(7) == 0
        assert CollectorContext(limit=3).resolved_limit(7) == 3

    def test_source_name_and_type_without_config(self) -> None:
        ctx = CollectorContext()
        assert ctx.source_name == ""
        assert ctx.source_type == ""

    def test_source_name_and_type_with_config(self) -> None:
        ctx = CollectorContext(source_config=SourceConfig(name="src", type="rss", url="https://x"))
        assert ctx.source_name == "src"
        assert ctx.source_type == "rss"

    def test_keywords_and_settings_are_not_shared(self) -> None:
        first = CollectorContext()
        second = CollectorContext()
        first.keywords.append("x")
        first.settings["k"] = "v"
        assert second.keywords == []
        assert second.settings == {}
