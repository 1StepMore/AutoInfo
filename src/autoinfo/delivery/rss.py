"""RSS delivery channel for AutoInfo.

Generates an RSS 2.0 XML feed from product content and writes it to
a file (local path or served ``feed_url``).

Reuses the same ``xml.etree.ElementTree``-based RSS generation logic
as :func:`autoinfo.output._export_rss`.

The :class:`PodcastRSSDeliveryChannel` extends RSS generation with
Apple Podcasts-compatible ``<enclosure>`` elements and ``itunes:*``
namespace metadata for podcast directory submission.
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


# ---------------------------------------------------------------------------
# Podcast RSS — enclosure + itunes:* namespace
# ---------------------------------------------------------------------------

# iTunes namespace URI for Apple Podcasts-compatible RSS 2.0
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


class PodcastRSSDeliveryChannel(DeliveryChannel):
    """Generate an Apple Podcasts-compatible RSS 2.0 feed with enclosures.

    Builds a podcast RSS feed that can be submitted to Apple Podcasts
    Connect or Spotify for Podcasters.  Each item includes an
    ``<enclosure>`` pointing to an externally hosted MP3 audio file
    and ``itunes:*`` namespace metadata.

    Configuration
    -------------
    Required config keys (checked by :meth:`validate_config`):

    * ``feed_url`` — path or URL where the feed XML is written.
    * ``title`` — podcast ``<title>`` (mapped to ``<itunes:title>``).
    * ``description`` — podcast ``<description>``.
    * ``author`` — podcast author (mapped to ``<itunes:author>``).

    Optional config keys:

    * ``link`` — podcast website URL (defaults to ``feed_url``).
    * ``language`` — feed language (default ``"en"``).
    * ``image_url`` — podcast cover art URL (``<itunes:image>``).
    * ``explicit`` — ``"yes"``, ``"no"``, or ``"clean"`` (default ``"no"``).
    * ``category`` — primary iTunes category (e.g. ``"Technology"``).
    * ``subcategory`` — secondary iTunes subcategory (e.g. ``"Podcasts"``).
    * ``base_url`` — base URL for resolving enclosure paths (default
      ``"http://localhost:8741"`` — the AutoInfo REST API).

    Payload keys understood by ``send()``:

    * ``episodes`` — list of episode dicts.  Each dict may have:
      ``title``, ``description``, ``audio_url`` (absolute or relative
      path served by AutoInfo REST API), ``duration`` (HH:MM:SS),
      ``guid``, ``pub_date``, ``episode_type``, ``season``, ``episode``.
    * ``items`` — alias for ``episodes`` (backward-compatible with
      :class:`RSSDeliveryChannel`).
    * ``feed_url``, ``title``, ``description``, ``author``, ``link``,
      ``language``, ``image_url``, ``explicit``, ``category``,
      ``subcategory``, ``base_url`` — override config defaults.
    """

    @property
    def name(self) -> str:
        return "podcast-rss"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(
        self,
        product: Product,
        payload: dict[str, Any],
        recipients: list[str],
    ) -> DeliveryResult:
        """Generate a podcast RSS 2.0 XML feed and persist it.

        Parameters
        ----------
        product:
            Product being delivered.  ``product.config`` supplies
            default channel metadata.
        payload:
            Content dict with optional keys ``"episodes"`` (or
            ``"items"``), ``"feed_url"``, ``"title"``,
            ``"description"``, ``"author"``, ``"link"``, ``"language"``,
            ``"image_url"``, ``"explicit"``, ``"category"``,
            ``"subcategory"``, ``"base_url"``.
        recipients:
            Output file paths — first entry overrides ``feed_url``.

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

        # Resolve metadata ---------------------------------------------------
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
        feed_author = str(
            payload.get("author")
            or config.get("author")
            or "AutoInfo"
        )
        feed_link = str(
            payload.get("link")
            or config.get("link")
            or feed_path
        )
        feed_language = str(
            payload.get("language")
            or config.get("language")
            or _RSS_DEFAULT_LANGUAGE
        )
        feed_image_url = str(payload.get("image_url", "") or config.get("image_url", ""))
        feed_explicit = str(payload.get("explicit", "") or config.get("explicit", "no"))
        feed_category = str(payload.get("category", "") or config.get("category", "Technology"))
        feed_subcategory = str(payload.get("subcategory", "") or config.get("subcategory", ""))
        base_url = str(
            payload.get("base_url")
            or config.get("base_url")
            or "http://localhost:8741"
        ).rstrip("/")

        # Resolve episodes ---------------------------------------------------
        episodes: list[dict[str, Any]] = payload.get("episodes", [])
        if not episodes:
            episodes = payload.get("items", [])
        if not episodes:
            episodes = self._episodes_from_kb(product.domain)

        # Build podcast RSS XML ----------------------------------------------
        try:
            xml_bytes = _build_podcast_rss(
                title=feed_title,
                description=feed_description,
                link=feed_link,
                language=feed_language,
                author=feed_author,
                image_url=feed_image_url,
                explicit=feed_explicit,
                category=feed_category,
                subcategory=feed_subcategory,
                episodes=episodes,
                base_url=base_url,
            )
        except Exception as exc:
            logger.error("Podcast RSS XML generation failed: %s", exc)
            return DeliveryResult(
                product_id=product.id,
                channel=self.name,
                status="failed",
                timestamp=_now_utc(),
                recipient_count=0,
                error=f"Podcast RSS XML generation failed: {exc}",
            )

        # Persist ------------------------------------------------------------
        try:
            out_path = Path(feed_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(xml_bytes)
            logger.info(
                "Podcast RSS feed written to %s (%d episodes)",
                out_path, len(episodes),
            )
        except OSError as exc:
            logger.error(
                "Failed to write podcast RSS feed to %s: %s", feed_path, exc,
            )
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
        """Return ``True`` when *config* contains valid podcast RSS settings.

        Required keys: ``feed_url``, ``title``, ``description``,
        ``author``.  All four must be non-empty strings.
        """
        feed_url = config.get("feed_url", "")
        title = config.get("title", "")
        description = config.get("description", "")
        author = config.get("author", "")
        return (
            isinstance(feed_url, str)
            and len(feed_url.strip()) > 0
            and isinstance(title, str)
            and len(title.strip()) > 0
            and isinstance(description, str)
            and len(description.strip()) > 0
            and isinstance(author, str)
            and len(author.strip()) > 0
        )

    def health_check(self) -> dict[str, Any]:
        import os as _os
        import time as _time
        start = _time.time()
        try:
            out_dir = _os.environ.get("AUTOINFO_RSS_DIR", _os.getcwd())
            if not _os.access(out_dir, _os.W_OK):
                latency = (_time.time() - start) * 1000
                return {
                    "healthy": False,
                    "latency_ms": latency,
                    "error": f"directory not writable: {out_dir}",
                    "channel": "podcast-rss",
                }
            latency = (_time.time() - start) * 1000
            return {
                "healthy": True,
                "latency_ms": latency,
                "error": None,
                "channel": "podcast-rss",
            }
        except Exception as e:
            latency = (_time.time() - start) * 1000
            return {
                "healthy": False,
                "latency_ms": latency,
                "error": str(e),
                "channel": "podcast-rss",
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _episodes_from_kb(domain: str | None) -> list[dict[str, Any]]:
        """Fetch KB entries for podcast episode fallback.

        Returns an empty list — KB entries lack audio enclosures by
        default, so podcast feeds should always provide explicit
        episode payloads with ``audio_url``.
        """
        try:
            from autoinfo.config import get_config_path
            from autoinfo.output import export_kb

            config_path = get_config_path()
            if config_path is None or not config_path.is_file():
                logger.debug("Project not initialized — skipping KB export fallback")
                return []

            result = export_kb(domain=domain, format="rss")
            if not result.get("success"):
                return []

            return result.get("entries", [])
        except Exception as exc:
            logger.warning("KB fallback for podcast episodes failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# Standalone XML builder (reusable outside DeliveryChannel context)
# ---------------------------------------------------------------------------


def _build_podcast_rss(
    title: str,
    description: str,
    link: str,
    language: str,
    author: str,
    image_url: str,
    explicit: str,
    category: str,
    subcategory: str,
    episodes: list[dict[str, Any]],
    base_url: str,
) -> bytes:
    """Build a podcast RSS 2.0 XML document with enclosures and itunes namespaces.

    Returns ``bytes`` with XML declaration and UTF-8 encoding.
    Standalone function usable outside the :class:`PodcastRSSDeliveryChannel`
    context (e.g. from MCP tools or CLI commands).
    """
    # Register the itunes namespace
    ET.register_namespace("itunes", ITUNES_NS)

    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")

    # Required RSS elements
    ET.SubElement(channel, "title").text = title
    ET.SubElement(channel, "link").text = link
    ET.SubElement(channel, "language").text = language
    ET.SubElement(channel, "description").text = description
    ET.SubElement(channel, "lastBuildDate").text = _rfc822_datetime(
        datetime.now(timezone.utc)
    )
    ET.SubElement(channel, "generator").text = "AutoInfo"

    # itunes:* namespace elements
    _itunes(channel, "author", author)
    _itunes(channel, "title", title)
    _itunes(channel, "explicit", explicit)

    if image_url:
        _itunes(channel, "image", "", {"href": image_url})

    # iTunes category (with optional subcategory)
    cat_attrs: dict[str, str] = {"text": category}
    cat_elem = _itunes(channel, "category", "", cat_attrs)
    if subcategory:
        _itunes(cat_elem, "category", "", {"text": subcategory})

    # Episode items
    for ep in episodes:
        item = ET.SubElement(channel, "item")

        ep_title = ep.get("title", "Untitled Episode")
        ep_description = ep.get("description", "") or ep.get("summary", "")
        ep_guid = ep.get("guid", "") or ep.get("entry_id", "") or ep_title
        ep_pub_date = ep.get("pub_date", "") or ep.get("collected_at", "")
        ep_duration = ep.get("duration", "")
        ep_audio_url = ep.get("audio_url", "") or ep.get("enclosure_url", "")
        ep_link = ep.get("link", "") or ep.get("source_url", "")
        ep_type = ep.get("episode_type", "")  # "full", "trailer", "bonus"
        ep_season = ep.get("season", "")
        ep_episode = ep.get("episode", "")

        ET.SubElement(item, "title").text = ep_title

        if ep_link:
            ET.SubElement(item, "link").text = ep_link

        # GUID (required for podcast items)
        guid = ET.SubElement(item, "guid", isPermaLink="false")
        guid.text = str(ep_guid)

        if ep_description:
            ET.SubElement(item, "description").text = ep_description
            # iTunes summary mirrors description
            _itunes(item, "summary", ep_description)

        # Pub date
        if ep_pub_date:
            try:
                dt = datetime.fromisoformat(ep_pub_date)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                ET.SubElement(item, "pubDate").text = _rfc822_datetime(dt)
            except (ValueError, TypeError):
                pass

        # Enclosure — the audio file URL
        enclosure_url = ep_audio_url
        if enclosure_url and not enclosure_url.startswith(("http://", "https://")):
            enclosure_url = f"{base_url}/{enclosure_url.lstrip('/')}"

        if enclosure_url:
            ET.SubElement(item, "enclosure", {
                "url": enclosure_url,
                "length": str(len(ep.get("audio_data", b"")) or 0),
                "type": "audio/mpeg",
            })

        # itunes:* per-episode metadata
        _itunes(item, "title", ep_title)
        _itunes(item, "author", ep.get("author", author))

        if ep_duration:
            _itunes(item, "duration", str(ep_duration))

        if ep_type:
            _itunes(item, "episodeType", ep_type)

        if ep_season:
            _itunes(item, "season", str(ep_season))

        if ep_episode:
            _itunes(item, "episode", str(ep_episode))

        if ep_explicit := ep.get("explicit", ""):
            _itunes(item, "explicit", str(ep_explicit))

    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


def _itunes(
    parent: ET.Element,
    tag: str,
    text: str = "",
    attrib: dict[str, str] | None = None,
) -> ET.Element:
    """Create an ``<itunes:tag>`` sub-element under *parent*.

    Parameters
    ----------
    parent:
        Parent XML element.
    tag:
        Local name (e.g. ``"author"``, ``"title"``).
    text:
        Element text content.  When empty and *attrib* is provided,
        the element is self-closing (no text child).
    attrib:
        Optional attribute dict (e.g. ``{"href": "https://..."}``).

    Returns
    -------
    xml.etree.ElementTree.Element
        The newly created element.
    """
    elem = ET.SubElement(parent, f"{{{ITUNES_NS}}}{tag}", attrib=attrib or {})
    if text:
        elem.text = text
    return elem
