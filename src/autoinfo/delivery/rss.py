"""RSS delivery channel for AutoInfo.

Generates an RSS 2.0 XML feed from product content and writes it to
a file (local path or served ``feed_url``).

Reuses the same ``xml.etree.ElementTree``-based RSS generation logic
as :func:`autoinfo.output._export_rss`.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autoinfo.delivery import DeliveryChannel, _now_utc
from autoinfo.models import DeliveryResult, Product

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RSS_DEFAULT_TITLE = "AutoInfo Feed"
"""Default channel title when none is provided in config or payload."""

_RSS_DEFAULT_DESCRIPTION = "Auto-generated knowledge base feed from AutoInfo"
"""Default channel description when none is provided in config or payload."""

_RSS_DEFAULT_LANGUAGE = "en"
"""Default feed language."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rfc822_datetime(dt: datetime) -> str:
    """Format a :class:`datetime` as an RFC-822 / RFC-2822 date string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # %a, %d %b %Y %H:%M:%S %z
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


# ---------------------------------------------------------------------------
# RSS delivery
# ---------------------------------------------------------------------------


class RSSDeliveryChannel(DeliveryChannel):
    """Generate and persist an RSS 2.0 XML feed from product / payload content.

    Configuration
    -------------
    Required config keys (checked by :meth:`validate_config`):

    * ``feed_url`` — path or URL where the feed should be written / served.
    * ``title`` — RSS channel ``<title>``.
    * ``description`` — RSS channel ``<description>``.

    Feed content is drawn from *payload* keys (preferred) or from the
    product's associated knowledge base entries via
    :func:`~autoinfo.output.export_kb`.

    Payload keys understood by ``send()``:

    * ``entries`` — list of entry dicts.  Each dict may have ``title``,
      ``source_url``, ``summary`` (mapped to ``<description>``),
      ``entry_id`` (mapped to ``<guid>``), and ``collected_at``
      (mapped to ``<pubDate>``).
    * ``feed_url`` — overrides config's ``feed_url``.
    * ``title`` — overrides config's ``title``.
    * ``description`` — overrides config's ``description``.
    * ``language`` — feed language (default ``"en"``).

    .. note::

       When *payload* contains ``"entries"`` those entries are used
       directly.  When absent the channel falls back to calling
       :func:`autoinfo.output.export_kb` with ``format="rss"``, which
       reads from the domain's knowledge base database.
    """

    @property
    def name(self) -> str:
        return "rss"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(
        self,
        product: Product,
        payload: dict[str, Any],
        recipients: list[str],
    ) -> DeliveryResult:
        """Generate an RSS 2.0 XML feed and persist it.

        Parameters
        ----------
        product:
            Product being delivered.  ``product.config`` supplies
            default ``feed_url``, ``title``, and ``description``.
            ``product.domain`` is used as a fallback title and for
            ``export_kb`` look-up.
        payload:
            Content dict.  Keys ``"entries"``, ``"feed_url"``,
            ``"title"``, ``"description"``, ``"language"`` override
            config defaults.
        recipients:
            Optional file paths — when provided, the first entry is
            used as the output path (overrides ``feed_url`` in config
            and payload).

        Returns
        -------
        DeliveryResult
        """
        config = product.config or {}

        # Resolve feed output path -------------------------------------------
        feed_path: str | None = None
        if recipients:
            feed_path = recipients[0]
        elif payload.get("feed_url"):
            feed_path = str(payload["feed_url"])
        elif config.get("feed_url"):
            feed_path = str(config["feed_url"])

        if not feed_path:
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error=(
                    "No feed output path provided.  Pass via recipients, "
                    'payload["feed_url"], or config["feed_url"].'
                ),
            )

        # Resolve feed metadata ----------------------------------------------
        feed_title = (
            payload.get("title")
            or config.get("title")
            or _RSS_DEFAULT_TITLE
        )
        feed_description = (
            payload.get("description")
            or config.get("description")
            or _RSS_DEFAULT_DESCRIPTION
        )
        feed_language = (
            payload.get("language")
            or config.get("language")
            or _RSS_DEFAULT_LANGUAGE
        )
        # link for the channel — prefer config "link" or resort to feed_url
        feed_link = (
            config.get("link")
            or payload.get("link")
            or feed_path
        )

        # Resolve entries ----------------------------------------------------
        entries: list[dict[str, Any]] = payload.get("entries", [])
        if not entries:
            # Fall back to export_kb for auto-generated feed content
            entries = self._entries_from_kb(product.domain)

        # Build RSS XML ------------------------------------------------------
        try:
            xml_bytes = self._build_rss(
                title=feed_title,
                description=feed_description,
                link=feed_link,
                language=feed_language,
                entries=entries,
            )
        except Exception as exc:
            logger.error("RSS XML generation failed: %s", exc)
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error=f"RSS XML generation failed: {exc}",
            )

        # Persist ------------------------------------------------------------
        try:
            out_path = Path(feed_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(xml_bytes)
            logger.info("RSS feed written to %s (%d entries)", out_path, len(entries))
        except OSError as exc:
            logger.error("Failed to write RSS feed to %s: %s", feed_path, exc)
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error=str(exc),
            )

        return DeliveryResult(
            product_id=product.id,
            channel=self.name,
            status="success",
            timestamp=_now_utc(),
            recipient_count=1,
            error=None,
        )

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Return ``True`` when *config* contains valid RSS settings.

        Required keys: ``feed_url``, ``title``, ``description``.
        All three must be non-empty strings.
        """
        feed_url = config.get("feed_url", "")
        title = config.get("title", "")
        description = config.get("description", "")
        return (
            isinstance(feed_url, str)
            and len(feed_url.strip()) > 0
            and isinstance(title, str)
            and len(title.strip()) > 0
            and isinstance(description, str)
            and len(description.strip()) > 0
        )

    def health_check(self) -> dict[str, Any]:
        import os as _os
        import time as _time
        start = _time.time()
        try:
            out_dir = _os.environ.get("AUTOINFO_RSS_DIR", _os.getcwd())
            if not _os.access(out_dir, _os.W_OK):
                latency = (_time.time() - start) * 1000
                return {"healthy": False, "latency_ms": latency, "error": f"directory not writable: {out_dir}", "channel": "rss"}
            latency = (_time.time() - start) * 1000
            return {"healthy": True, "latency_ms": latency, "error": None, "channel": "rss"}
        except Exception as e:
            latency = (_time.time() - start) * 1000
            return {"healthy": False, "latency_ms": latency, "error": str(e), "channel": "rss"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_rss(
        title: str,
        description: str,
        link: str,
        language: str,
        entries: list[dict[str, Any]],
    ) -> bytes:
        """Build an RSS 2.0 XML document and return it as ``bytes``.

        Mirrors the logic in :func:`autoinfo.output._export_rss`
        (lines 672–717) but returns in-memory bytes instead of
        writing directly to disk.
        """
        rss = ET.Element("rss", version="2.0")
        channel = ET.SubElement(rss, "channel")

        ET.SubElement(channel, "title").text = title
        ET.SubElement(channel, "link").text = link
        ET.SubElement(channel, "description").text = description
        ET.SubElement(channel, "language").text = language
        ET.SubElement(channel, "lastBuildDate").text = _rfc822_datetime(
            datetime.now(timezone.utc)
        )
        ET.SubElement(channel, "generator").text = "AutoInfo"

        for e in entries:
            item = ET.SubElement(channel, "item")

            item_title = e.get("title") or "Untitled"
            source_url = e.get("source_url") or ""
            item_description = e.get("summary") or ""
            entry_id = e.get("entry_id") or ""
            collected_at = e.get("collected_at") or ""

            ET.SubElement(item, "title").text = item_title
            if source_url:
                ET.SubElement(item, "link").text = source_url
            if item_description:
                ET.SubElement(item, "description").text = item_description

            guid = ET.SubElement(item, "guid", isPermaLink="false")
            guid.text = entry_id or source_url or item_title

            if collected_at:
                try:
                    dt = datetime.fromisoformat(collected_at)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    ET.SubElement(item, "pubDate").text = _rfc822_datetime(dt)
                except (ValueError, TypeError):
                    pass

        return ET.tostring(rss, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _entries_from_kb(domain: str | None) -> list[dict[str, Any]]:
        """Fetch KB entries via :func:`export_kb` as an RSS fallback.

        Returns a (possibly empty) list of entry dicts extracted from
        the export result.  Logs a warning and returns an empty list
        when the export fails.
        """
        try:
            from autoinfo.config import get_config_path
            from autoinfo.output import export_kb

            # Only attempt KB export when project is initialized
            config_path = get_config_path()
            if config_path is None or not config_path.is_file():
                logger.debug("Project not initialized — skipping KB export fallback")
                return []

            result = export_kb(domain=domain, format="rss")
            if not result.get("success"):
                logger.warning("export_kb RSS fallback failed: %s", result)
                return []

            # export_kb writes to disk; parse the file to retrieve entries.
            # For simplicity we return a note that the file was generated.
            path = result.get("path", "")
            if path:
                logger.info(
                    "RSS feed content sourced from export_kb at %s", path
                )
            return result.get("entries", [])
        except Exception as exc:
            logger.warning("export_kb RSS fallback failed: %s", exc)
            return []
