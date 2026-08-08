"""Tests for the AKShare handler (A股/港股/基金 free data).

The handler lazy-imports ``akshare`` inside ``fetch`` so the module stays
importable without the library installed.  All tests mock ``akshare``
via ``sys.modules`` — no real network access.
"""

from __future__ import annotations

import json
import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

from autoinfo.collectors.akshare import AKShareHandler
from autoinfo.config import SourceConfig

HIST_ROWS: list[dict[str, Any]] = [
    {
        "日期": "2026-08-01",
        "开盘": 10.0,
        "收盘": 10.5,
        "code": "000001",
        "name": "平安银行",
    },
    {
        "日期": "2026-08-02",
        "开盘": 10.5,
        "收盘": 10.8,
        "code": "000001",
        "name": "平安银行",
    },
]

SPOT_ROWS: list[dict[str, Any]] = [
    {"代码": "000001", "名称": "平安银行", "最新价": 10.8},
    {"代码": "600000", "名称": "浦发银行", "最新价": 8.2},
]


class _FakeDF:
    """Minimal pandas-DataFrame stand-in (akshare returns DataFrames)."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def to_dict(self, orient: str = "records") -> list[dict[str, Any]]:
        return self._rows


@pytest.fixture
def ak_config() -> SourceConfig:
    """Config matching how ``_build_handler`` constructs the handler."""
    return SourceConfig(
        name="AKShare A股",
        type="akshare",
        url="",
        settings={"symbols": "000001"},
    )


def _install_fake_akshare(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Install a fake ``akshare`` module into ``sys.modules``."""
    fake_ak = MagicMock()
    monkeypatch.setitem(sys.modules, "akshare", fake_ak)
    return fake_ak


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAKShareHandler:
    def test_handler_attributes(self, ak_config: SourceConfig) -> None:
        handler = AKShareHandler(
            config={**ak_config.settings, "name": "AKShare A股"}
        )
        assert handler.source_type == "akshare"
        assert handler.source_name == "AKShare A股"
        assert handler.symbols == ["000001"]

    def test_default_symbols(self) -> None:
        handler = AKShareHandler(config={})
        assert handler.symbols == ["000001"]
        assert handler.source_name == "akshare"

    def test_symbols_string_parsing(self) -> None:
        handler = AKShareHandler(config={"symbols": "000001,600000 601318"})
        assert handler.symbols == ["000001", "600000", "601318"]

    def test_fetch_hist_returns_rows(
        self, ak_config: SourceConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_ak = _install_fake_akshare(monkeypatch)
        fake_ak.stock_zh_a_hist.return_value = _FakeDF(HIST_ROWS)

        handler = AKShareHandler(config=ak_config.settings)
        rows = handler.fetch(limit=5)

        assert len(rows) == 2
        assert rows[0]["code"] == "000001"
        assert rows[0]["name"] == "平安银行"
        assert rows[0]["收盘"] == 10.5
        fake_ak.stock_zh_a_hist.assert_called_once_with(symbol="000001")

    def test_fetch_hist_limits_rows(
        self, ak_config: SourceConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_ak = _install_fake_akshare(monkeypatch)
        fake_ak.stock_zh_a_hist.return_value = _FakeDF(HIST_ROWS)

        handler = AKShareHandler(config=ak_config.settings)
        rows = handler.fetch(limit=1)

        assert len(rows) == 1

    def test_fetch_spot_em_returns_rows(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No symbols configured → spot snapshot endpoint
        fake_ak = _install_fake_akshare(monkeypatch)
        fake_ak.stock_zh_a_spot_em.return_value = _FakeDF(SPOT_ROWS)

        handler = AKShareHandler(config={"symbols": ""})
        rows = handler.fetch(limit=10)

        assert len(rows) == 2
        # 代码/名称 columns normalised to code/name
        assert rows[0]["code"] == "000001"
        assert rows[0]["name"] == "平安银行"
        fake_ak.stock_zh_a_spot_em.assert_called_once()

    def test_fetch_calls_hist_per_symbol(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_ak = _install_fake_akshare(monkeypatch)
        fake_ak.stock_zh_a_hist.side_effect = [_FakeDF(HIST_ROWS), _FakeDF(SPOT_ROWS)]

        handler = AKShareHandler(config={"symbols": "000001,600000"})
        handler.fetch(limit=5)

        assert fake_ak.stock_zh_a_hist.call_count == 2
        assert fake_ak.stock_zh_a_hist.call_args_list[0].kwargs["symbol"] == "000001"
        assert fake_ak.stock_zh_a_hist.call_args_list[1].kwargs["symbol"] == "600000"

    def test_fetch_network_error_returns_empty(
        self, ak_config: SourceConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_ak = _install_fake_akshare(monkeypatch)
        fake_ak.stock_zh_a_hist.side_effect = RuntimeError("connection refused")

        handler = AKShareHandler(config=ak_config.settings)
        rows = handler.fetch(limit=5)

        assert rows == []

    def test_fetch_import_error_returns_empty(
        self, ak_config: SourceConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # akshare NOT in sys.modules and NOT installed → lazy import fails
        monkeypatch.delitem(sys.modules, "akshare", raising=False)

        handler = AKShareHandler(config=ak_config.settings)
        rows = handler.fetch(limit=5)

        assert rows == []

    def test_fetch_limit_zero_returns_empty(
        self, ak_config: SourceConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_akshare(monkeypatch)
        handler = AKShareHandler(config=ak_config.settings)
        assert handler.fetch(limit=0) == []

    def test_to_item_fields(self, ak_config: SourceConfig) -> None:
        handler = AKShareHandler(
            config={**ak_config.settings, "name": "AKShare A股"}
        )
        payload = {"code": "000001", "name": "平安银行", "最新价": 10.8}
        item = handler.to_item(payload)

        assert item.id == "000001"
        assert item.title == "000001 平安银行"
        assert item.source_url == "https://finance.sina.com.cn/realstock/company/000001/nc.shtml"
        assert item.source_type == "akshare"
        assert item.source_platform == "akshare"
        assert item.source_name == "AKShare A股"
        assert json.loads(item.content)["最新价"] == 10.8
        assert item.raw_data == payload

    def test_to_item_accepts_chinese_columns(self, ak_config: SourceConfig) -> None:
        handler = AKShareHandler(config=ak_config.settings)
        payload = {"代码": "600000", "名称": "浦发银行"}
        item = handler.to_item(payload)

        assert item.id == "600000"
        assert item.title == "600000 浦发银行"
        assert item.source_url == "https://finance.sina.com.cn/realstock/company/600000/nc.shtml"
