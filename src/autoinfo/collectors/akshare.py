"""AKShare handler — free A股/港股/基金 market data (A7).

Fetches Chinese A-share market data via the `akshare` library
(https://akshare.akfamily.xyz/).  ``akshare`` is an optional dependency
declared only in the ``[akshare]`` extra — this module lazy-imports it
inside :meth:`AKShareHandler.fetch` so the rest of AutoInfo stays
importable (and collectable) without it installed.

Two fetch modes, driven by ``settings.symbols``:

* ``symbols`` configured (default ``"000001"``) → per-symbol historical
  quotes via ``ak.stock_zh_a_hist(symbol=...)``
* ``symbols`` empty → whole-market spot snapshot via
  ``ak.stock_zh_a_spot_em()``

The handler never raises: network errors, import errors, and empty
results all collapse to ``[]`` (handler convention).

Usage::

    handler = AKShareHandler({"symbols": "000001,600000"})
    rows = handler.fetch(limit=10)
    items = [handler.to_item(row) for row in rows]
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from autoinfo.collectors.base import BaseHandler
from autoinfo.models import Item

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_LIMIT: int = 20
DEFAULT_RATE_LIMIT: float = 10.0  # requests per minute (akshare is scraped data)
DEFAULT_TIMEOUT: int = 30  # seconds
DEFAULT_SYMBOLS: str = "000001"  # Ping An Bank — a stable, always-listed A-share
SINA_STOCK_URL: str = "https://finance.sina.com.cn/realstock/company/{code}/nc.shtml"


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class AKShareHandler(BaseHandler):
    """Fetch Chinese market data via the AKShare library.

    Usage::

        handler = AKShareHandler({"symbols": "000001"})
        rows = handler.fetch(limit=5)
    """

    source_type: str = "akshare"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialise handler from a settings dict.

        Args:
            config: Dictionary with optional keys:
                - ``symbols``: comma/space separated stock codes
                  (default ``"000001"``).  Empty string selects the
                  whole-market spot snapshot endpoint instead.
                - ``limit``: default row limit for :meth:`fetch`
                  (default 20).
                - ``rate_limit``: requests per minute (default 10).
                - ``timeout``: seconds per request (default 30).
                - ``name``: source name used in produced :class:`Item`
                  (default ``"akshare"``).
        """
        if config is None:
            config = {}
        self.config: dict[str, Any] = config
        self.source_name: str = str(config.get("name", "akshare"))
        if "symbols" in config and str(config.get("symbols", "") or "").strip() == "":
            # Explicitly empty → whole-market spot snapshot mode
            self.symbols: list[str] = []
        else:
            symbols_raw: str = str(config.get("symbols", DEFAULT_SYMBOLS) or "").strip()
            self.symbols = [
                s.strip()
                for s in symbols_raw.replace(",", " ").split()
                if s.strip()
            ]
            if not self.symbols:
                self.symbols = [DEFAULT_SYMBOLS]
        self.default_limit: int = int(config.get("limit", DEFAULT_LIMIT))
        self.rate_limit: float = float(config.get("rate_limit", DEFAULT_RATE_LIMIT))
        self.timeout: int = int(config.get("timeout", DEFAULT_TIMEOUT))
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        """Block until the next request is allowed under the rate limit."""
        if self._last_request_time == 0.0:
            self._last_request_time = time.time()
            return

        min_interval = 60.0 / self.rate_limit if self.rate_limit > 0 else 0.0
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    # ------------------------------------------------------------------
    # Field normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_row(row: dict[str, Any]) -> dict[str, Any]:
        """Map common Chinese akshare column names to ``code``/``name``.

        Both endpoints are pandas DataFrames; the spot endpoint
        (``stock_zh_a_spot_em``) uses ``代码``/``名称`` while historical
        rows carry their own columns.  ``to_item`` reads the normalised
        keys (falling back to the Chinese names defensively).
        """
        return {
            "code": str(row.get("code") or row.get("代码") or ""),
            "name": str(row.get("name") or row.get("名称") or ""),
            **row,
        }

    @staticmethod
    def _rows_from_result(result: Any) -> list[dict[str, Any]]:
        """Convert an akshare result (DataFrame or list) to row dicts."""
        if result is None:
            return []
        if hasattr(result, "to_dict"):
            return list(result.to_dict("records"))
        if isinstance(result, list):
            return list(result)
        return []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:  # type: ignore[override]
        """Fetch market data rows from AKShare.

        Args:
            limit: Maximum number of rows to return (default 20).

        Returns:
            List of raw row dicts (with ``code``/``name`` keys
            normalised).  Returns an empty list on any failure —
            including when ``akshare`` is not installed.
        """
        if limit <= 0:
            return []

        try:
            # Lazy import: module stays importable without akshare
            # installed; the ImportError is caught below.
            import akshare as ak  # noqa: PLC0415
        except ImportError:
            logger.warning(
                "akshare is not installed; install with 'pip install autoinfo[akshare]'"
            )
            return []

        rows: list[dict[str, Any]] = []

        try:
            if self.symbols:
                # Per-symbol historical quotes
                for symbol in self.symbols[:limit]:
                    self._wait_for_rate_limit()
                    df = ak.stock_zh_a_hist(symbol=symbol)
                    for row in self._rows_from_result(df):
                        rows.append(self._normalise_row(row))
            else:
                # Whole-market spot snapshot
                self._wait_for_rate_limit()
                df = ak.stock_zh_a_spot_em()
                for row in self._rows_from_result(df):
                    rows.append(self._normalise_row(row))
        except Exception as exc:
            logger.warning("AKShare fetch failed: %s", exc)
            return []

        return rows[:limit]

    # ------------------------------------------------------------------
    # Conversion to Item
    # ------------------------------------------------------------------

    def to_item(self, payload: dict[str, Any]) -> Item:
        """Convert a raw AKShare row dict to an :class:`Item`.

        Args:
            payload: Raw row dict as returned by :meth:`fetch`.

        Returns:
            An :class:`Item` instance.
        """
        code: str = str(payload.get("code") or payload.get("代码") or "")
        name: str = str(payload.get("name") or payload.get("名称") or "")
        title: str = f"{code} {name}".strip()
        source_url: str = SINA_STOCK_URL.format(code=code) if code else ""
        content: str = json.dumps(payload, ensure_ascii=False, default=str)

        return Item(
            id=code,
            source_name=self.source_name,
            source_type="akshare",
            source_url=source_url,
            title=title,
            content=content,
            content_type="json",
            source_platform="akshare",
            collected_at=datetime.now(timezone.utc).isoformat(),
            raw_data=payload,
        )
