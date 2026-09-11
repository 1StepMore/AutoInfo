"""Knowledge-base export family (extracted from :mod:`autoinfo.output`, T7).

Pure relocation of the export implementation out of the 13K-line package
``__init__``: :func:`export_kb` plus the per-format ``_export_*`` dispatchers
and their bundle/sqlite/pdf helpers.  Every name is re-exported from
:mod:`autoinfo.output` (see the shim there), so no caller changes.

Import direction
----------------
This module is imported *by* :mod:`autoinfo.output`; importing the package back
at module scope would cycle.  Names that must stay resolvable through the
package namespace (either because they live in ``__init__`` or because the
module-boundary tests patch ``autoinfo.output.<name>``) are therefore imported
function-locally:

* ``_get_domain_source_configs`` / ``_domain_display_name`` /
  ``_JSONLD_BASE_EXPORT`` -- helpers that stay in ``__init__``.
* ``get_config_path`` / ``datetime`` / ``timezone`` / ``KBStore`` /
  ``_build_bundle_pdf`` -- call-time seams the characterization tests patch on
  ``autoinfo.output`` (``tests/output/test_export_boundary.py``,
  ``tests/kb/test_export.py``, ``tests/output/test_bundle_export.py``).

Everything else (``load_config``, ``SQLiteIndex``, stdlib, lazy
``ebook``/``seo`` renderers) stays a direct/lazy import exactly as before.
"""

from __future__ import annotations

import base64
import concurrent.futures
import html
import io
import json
import logging
import shutil
import sqlite3
import tarfile
import uuid
import xml.etree.ElementTree as ET
import zipfile
from email.utils import format_datetime
from pathlib import Path
from typing import Any, Callable, cast

import yaml

from autoinfo.config import load_config
from autoinfo.kb import SQLiteIndex

logger = logging.getLogger(__name__)


def export_kb(
    domain: str | None = None,
    format: str = "markdown",
    collection_id: str | None = None,  # reserved for future use
    base_url: str | None = None,
) -> dict[str, Any]:
    """Export knowledge base data to the requested format.

    Parameters
    ----------
    domain:
        Optional domain filter.  When ``None``, the entire KB is exported.
    format:
        Output format: ``"markdown"`` (default), ``"json"``, ``"sqlite"``,
        ``"pdf"``, ``"rss"``, ``"csv"``, ``"graphml"``, ``"agent"``,
        ``"bundle"``, ``"sitemap"``, ``"epub"``, or ``"mobi"``.
    collection_id:
        Reserved for future collection-scoped export (not yet implemented).
    base_url:
        Site base URL used for ``format="sitemap"`` (e.g.
        ``"https://your-site.example"``).  Required for sitemap export;
        ignored for other formats.

    Returns
    -------
    dict
        Keys: ``format``, ``path`` (absolute path to the exported file),
        ``entries_count``, ``domain`` (filter used or ``"*"`` for all),
        ``success`` (bool).

    Raises
    ------
    FileNotFoundError
        If no configuration file is found (project not initialized).
    ValueError
        If *format* is not one of the supported values, or if
        *format* is ``"sitemap"`` and *base_url* is not provided.
    """
    from autoinfo.output import (  # noqa: PLC0415 - package seam
        _get_domain_source_configs,
        datetime,
        get_config_path,
        timezone,
    )

    if format not in (
        "markdown", "json", "sqlite", "pdf", "rss",
        "csv", "graphml", "agent", "bundle", "sitemap",
        "epub", "mobi",
    ):
        raise ValueError(
            f"Unsupported export format: '{format}'. "
            f"Supported: markdown, json, sqlite, pdf, rss, csv, graphml, "
            f"agent, bundle, sitemap, epub, mobi"
        )

    # --- Locate project root & KB paths ------------------------------------
    config_path = get_config_path()
    if config_path is None or not config_path.is_file():
        raise FileNotFoundError(
            "No configuration found. Run 'autoinfo init' first."
        )

    # config_path is <project>/.autoinfo/config.yaml
    # project_root is <project>/
    autoinfo_dir = config_path.parent
    project_root = autoinfo_dir.parent
    knowledge_dir = project_root / "knowledge"
    db_path = project_root / "autoinfo.db"

    # Configurable weasyprint render timeout (output.pdf_timeout, default 120s)
    try:
        pdf_timeout: float = float(load_config(config_path).output.pdf_timeout)
    except Exception:
        pdf_timeout = 120.0

    # --- Resolve entries to export ----------------------------------------
    entries: list[dict[str, Any]] = []
    if db_path.exists():
        index = SQLiteIndex(db_path)
        if domain:
            entries = index.list_entries(domain, limit=99999)
        else:
            # Fetch all domains by iterating known ones
            known_domains = _list_domains_from_db(index)
            for d in known_domains:
                entries.extend(index.list_entries(d, limit=99999))

    domain_label = domain if domain else "*"

    # --- Source attribution enrichment for text formats (F46) --------------
    if entries and format in ("json", "csv"):
        if domain:
            srcs = _get_domain_source_configs(domain)
        else:
            srcs = []
            for d_name in {e.get("domain", "") for e in entries if e.get("domain")}:
                srcs.extend(_get_domain_source_configs(d_name))
        url_to_source: dict[str, Any] = {}
        for s in srcs:
            url_to_source[(s.url or "").strip().rstrip("/")] = s
        for entry in entries:
            url = (entry.get("source_url") or "").strip().rstrip("/")
            if url in url_to_source:
                s = url_to_source[url]
                entry["attribution"] = (
                    f"Source: {s.name} ({s.url}) — "
                    f"Tier {s.quality_tier}, {s.tos_classification}"
                )
            else:
                entry["attribution"] = ""

    # --- Prepare export directory -----------------------------------------
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    export_dir = project_root / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    # --- Format-specific export -------------------------------------------
    if format == "markdown":
        result = _export_markdown(
            knowledge_dir=knowledge_dir,
            export_dir=export_dir,
            domain=domain,
            entries=entries,
            timestamp=timestamp,
            domain_label=domain_label,
        )
    elif format == "json":
        result = _export_json(
            knowledge_dir=knowledge_dir,
            export_dir=export_dir,
            entries=entries,
            timestamp=timestamp,
            domain_label=domain_label,
        )
    elif format == "sqlite":
        result = _export_sqlite(
            db_path=db_path,
            export_dir=export_dir,
            entries=entries,
            timestamp=timestamp,
            domain_label=domain_label,
        )
    elif format == "pdf":
        result = _export_pdf(
            knowledge_dir=knowledge_dir,
            export_dir=export_dir,
            domain=domain,
            entries=entries,
            timestamp=timestamp,
            domain_label=domain_label,
            pdf_timeout=pdf_timeout,
        )
    elif format == "rss":
        result = _export_rss(
            export_dir=export_dir,
            domain=domain,
            entries=entries,
            timestamp=timestamp,
            domain_label=domain_label,
        )
    elif format == "csv":
        result = _export_csv(
            export_dir=export_dir,
            domain=domain,
            entries=entries,
            timestamp=timestamp,
            domain_label=domain_label,
        )
    elif format == "graphml":
        result = _export_graphml(
            export_dir=export_dir,
            domain=domain,
            timestamp=timestamp,
            domain_label=domain_label,
        )
    elif format == "agent":
        result = _export_agent_json(entries, domain, domain_label)
    elif format == "bundle":
        result = _export_bundle(
            knowledge_dir=knowledge_dir,
            export_dir=export_dir,
            domain=domain,
            entries=entries,
            timestamp=timestamp,
            domain_label=domain_label,
            pdf_timeout=pdf_timeout,
        )
    elif format == "sitemap":
        result = _export_sitemap(
            export_dir=export_dir,
            domain=domain,
            entries=entries,
            domain_label=domain_label,
            base_url=base_url,
        )
    elif format == "epub":
        result = _export_epub(
            export_dir=export_dir,
            entries=entries,
            timestamp=timestamp,
            domain_label=domain_label,
        )
    elif format == "mobi":
        result = _export_mobi(
            export_dir=export_dir,
            entries=entries,
            timestamp=timestamp,
            domain_label=domain_label,
        )
    else:
        raise ValueError(f"Unsupported export format: '{format}'")

    result["collection_id"] = collection_id
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _list_domains_from_db(index: SQLiteIndex) -> list[str]:
    """Return distinct domain names from the SQLite index."""
    try:
        conn = sqlite3.connect(str(index.db_path))
        rows = conn.execute("SELECT DISTINCT domain FROM entries").fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []


def _parse_tags_list(raw: Any) -> list[str]:
    """Coerce a ``tags`` value into a real list of strings.

    Entries read from the SQLite index carry ``tags`` as a JSON-encoded
    TEXT string (e.g. ``'["ivf", "embryo"]'``), but callers may also pass
    an already-parsed list.  This mirrors the defensive parse used in the
    digest and report renderers so every export format emits real JSON
    arrays instead of JSON-encoded strings.
    """
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else [raw] if raw else []
        except (json.JSONDecodeError, TypeError):
            return [raw] if raw else []
    return []


def _export_markdown(
    knowledge_dir: Path,
    export_dir: Path,
    domain: str | None,
    entries: list[dict[str, Any]],
    timestamp: str,
    domain_label: str,
) -> dict[str, Any]:
    """Create a tar.gz archive of knowledge base Markdown files."""
    if domain:
        source_dir = knowledge_dir / domain
    else:
        source_dir = knowledge_dir

    out_name = f"autoinfo-export-{domain_label}-{timestamp}.tar.gz"
    out_path = export_dir / out_name

    count = 0
    with tarfile.open(str(out_path), "w:gz") as tar:
        if source_dir.is_dir():
            for md_file in sorted(source_dir.rglob("*.md")):
                arcname = str(md_file.relative_to(knowledge_dir))
                tar.add(str(md_file), arcname=arcname)
                count += 1

    return {
        "format": "markdown",
        "path": str(out_path),
        "entries_count": count,
        "domain": domain_label,
        "success": True,
    }


def _export_json(
    knowledge_dir: Path,
    export_dir: Path,
    entries: list[dict[str, Any]],
    timestamp: str,
    domain_label: str,
) -> dict[str, Any]:
    """Export all entries as a JSON array, including file content."""
    out_name = f"autoinfo-export-{domain_label}-{timestamp}.json"
    out_path = export_dir / out_name

    export_data: list[dict[str, Any]] = []
    for e in entries:
        file_path = e.get("file_path") or ""
        content = ""
        if file_path and Path(file_path).is_file():
            content = Path(file_path).read_text(encoding="utf-8")

        export_data.append({
            "entry_id": e.get("entry_id"),
            "title": e.get("title"),
            "domain": e.get("domain"),
            "tier": e.get("tier"),
            "source_url": e.get("source_url"),
            "source_type": e.get("source_type"),
            "source_platform": e.get("source_platform"),
            "attribution": e.get("attribution", ""),
            "collected_at": e.get("collected_at"),
            "summary": e.get("summary"),
            "tags": _parse_tags_list(e.get("tags")),
            "relevance_score": e.get("relevance_score"),
            "dedup_status": e.get("dedup_status"),
            "file_path": file_path,
            "content": content,
        })

    out_path.write_text(
        json.dumps(export_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "format": "json",
        "path": str(out_path),
        "entries_count": len(entries),
        "domain": domain_label,
        "success": True,
    }


def _export_sqlite(
    db_path: Path,
    export_dir: Path,
    entries: list[dict[str, Any]],
    timestamp: str,
    domain_label: str,
) -> dict[str, Any]:
    """Copy the SQLite database, optionally filtering by domain.

    When *domain* is specified, creates a filtered copy with only the
    matching entries.  When *domain* is ``None``, copies the entire DB.
    """
    out_name = f"autoinfo-export-{domain_label}-{timestamp}.db"
    out_path = export_dir / out_name

    if domain_label == "*" and db_path.is_file():
        # Full DB copy — simple file copy is fast and preserves indexes.
        # First checkpoint WAL to ensure the file is fully synced.
        _wal_checkpoint(db_path)
        shutil.copy2(str(db_path), str(out_path))
        count = len(entries)
    else:
        # Filtered or missing-source copy — create a new DB with schema + filtered entries
        count = _create_filtered_sqlite_copy(db_path, out_path, entries)

    return {
        "format": "sqlite",
        "path": str(out_path),
        "entries_count": count,
        "domain": domain_label,
        "success": True,
    }


# ---------------------------------------------------------------------------
# PDF export
# ---------------------------------------------------------------------------


def _run_pdf_with_timeout(fn: Callable[[], Any], timeout: float, desc: str) -> Any:
    """Run a weasyprint render callable, aborting after *timeout* seconds.

    WeasyPrint's ``write_pdf`` is synchronous and cannot be interrupted in
    process, so the render runs in a worker thread and the caller observes a
    timeout as a raised ``ValueError``.  ``timeout <= 0`` disables the limit.
    """
    if timeout <= 0:
        return fn()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(fn)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        pool.shutdown(wait=False)
        raise ValueError(
            f"{desc} timed out after {timeout:.0f}s. "
            "Increase output.pdf_timeout in .autoinfo/config.yaml "
            "(default 120s) for large knowledge bases."
        ) from None
    except BaseException:
        pool.shutdown(wait=False)
        raise


def _export_pdf(
    knowledge_dir: Path,
    export_dir: Path,
    domain: str | None,
    entries: list[dict[str, Any]],
    timestamp: str,
    domain_label: str,
    pdf_timeout: float = 120.0,
) -> dict[str, Any]:
    """Export all entries as a PDF file.

    Converts each entry's Markdown content to HTML, combines them into
    a single styled HTML document, and renders via weasyprint.

    Returns
    -------
    dict
        Standard export result dict with keys: ``format``, ``path``,
        ``entries_count``, ``domain``, ``success``.

    Raises
    ------
    ValueError
        If weasyprint is not installed or PDF generation fails.
    """
    try:
        import weasyprint  # noqa: PLC0415
    except (ImportError, ModuleNotFoundError) as exc:
        raise ValueError(
            "weasyprint is not installed. PDF export requires weasyprint.\n"
            "Install it with: pip install weasyprint\n"
            "On Ubuntu/Debian: sudo apt install libpango-1.0-0 libpangocairo-1.0-0 "
            "libgdk-pixbuf2.0-dev libffi-dev\n"
            "On macOS: brew install pango\n"
            f"Original error: {exc}"
        ) from exc

    try:
        import markdown as md_lib  # noqa: PLC0415
    except (ImportError, ModuleNotFoundError) as exc:
        raise ValueError(
            "markdown library is not installed.\n"
            f"Original error: {exc}"
        ) from exc

    out_name = f"autoinfo-export-{domain_label}-{timestamp}.pdf"
    out_path = export_dir / out_name

    # --- Build HTML document ------------------------------------------------
    html_parts: list[str] = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><style>",
        "body{font-family:sans-serif;margin:2em;line-height:1.6;color:#333;}",
        "h1{color:#222;border-bottom:2px solid #ddd;padding-bottom:0.3em;}",
        "h2{color:#444;margin-top:1.5em;}",
        "h3{color:#555;}",
        ".meta{color:#777;font-size:0.9em;margin-bottom:1em;}",
        ".entry{page-break-inside:avoid;margin-bottom:2em;}",
        ".entry-content{margin-top:0.5em;}",
        "pre{background:#f5f5f5;padding:1em;border-radius:4px;",
        "overflow-x:auto;border:1px solid #e0e0e0;}",
        "code{background:#f0f0f0;padding:0.2em 0.4em;border-radius:3px;font-size:0.9em;}",
        "pre code{background:none;padding:0;}",
        "table{border-collapse:collapse;width:100%;margin:1em 0;}",
        "th,td{border:1px solid #ddd;padding:0.5em;text-align:left;}",
        "th{background:#f5f5f5;}",
        "blockquote{border-left:4px solid #ddd;margin:1em 0;padding:0.5em 1em;color:#666;}",
        "img{max-width:100%;height:auto;}",
        "</style></head><body>",
    ]

    if domain:
        html_parts.append(f"<h1>{html.escape(domain)}</h1>")
    else:
        html_parts.append("<h1>AutoInfo Knowledge Base Export</h1>")

    html_parts.append(
        f"<p class='meta'>Exported: {html.escape(timestamp)}  |  "
        f"Entries: {len(entries)}</p>"
    )

    for e in entries:
        title = e.get("title", "Untitled")
        file_path = e.get("file_path") or ""

        content = ""
        if file_path and Path(file_path).is_file():
            raw = Path(file_path).read_text(encoding="utf-8")
            if raw.startswith("---"):
                end_idx = raw.find("---", 3)
                if end_idx != -1:
                    content = raw[end_idx + 3 :].strip()
                else:
                    content = raw
            else:
                content = raw

        html_parts.append("<div class='entry'>")
        html_parts.append(f"<h2>{html.escape(title)}</h2>")

        meta_bits: list[str] = []
        if e.get("source_url"):
            url = html.escape(e["source_url"])
            meta_bits.append(f'Source: <a href="{url}">{url}</a>')
        if e.get("source_type"):
            meta_bits.append(f"Type: {html.escape(e['source_type'])}")
        if e.get("tier"):
            meta_bits.append(f"Tier: {html.escape(e['tier'])}")
        if e.get("relevance_score") is not None:
            meta_bits.append(f"Relevance: {e['relevance_score']}")
        if meta_bits:
            html_parts.append(f"<p class='meta'>{' | '.join(meta_bits)}</p>")

        summary = e.get("summary", "")
        if summary:
            html_parts.append(
                f"<p><strong>Summary:</strong> {html.escape(summary[:1000])}</p>"
            )

        if content:
            content_html = md_lib.markdown(
                content, extensions=["fenced_code", "tables"]
            )
            html_parts.append(f"<div class='entry-content'>{content_html}</div>")

        html_parts.append("</div>")

    html_parts.append("</body></html>")

    full_html = "\n".join(html_parts)

    # --- Render PDF ---------------------------------------------------------
    try:
        _run_pdf_with_timeout(
            lambda: weasyprint.HTML(string=full_html).write_pdf(str(out_path)),
            timeout=pdf_timeout,
            desc="PDF rendering",
        )
    except Exception as exc:
        logger.error("PDF generation failed: %s", exc)
        raise ValueError(
            f"PDF generation failed: {exc}\n"
            "Ensure weasyprint system dependencies are installed.\n"
            "See: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
        ) from exc

    return {
        "format": "pdf",
        "path": str(out_path),
        "entries_count": len(entries),
        "domain": domain_label,
        "success": True,
    }


def _derive_export_lang(entries: list[dict[str, Any]]) -> str:
    """Derive the ebook language code from *entries*.

    Uses the first entry that declares a ``language`` field, normalized to
    its primary RFC 5646 subtag (``zh-CN`` → ``zh``); otherwise runs
    ``langdetect`` over the concatenated titles/summaries; falls back to
    ``"en"`` when no signal is available.
    """
    for e in entries:
        lang = (e.get("language") or "").strip()
        if lang:
            return lang.split("-")[0].lower()
    sample = " ".join(
        f"{e.get('title', '')} {e.get('summary', '')}".strip()
        for e in entries
        if (e.get("title") or e.get("summary"))
    ).strip()
    if sample:
        try:
            from langdetect import detect  # noqa: PLC0415 — deferred import

            detected = detect(sample)
            if detected:
                return str(detected)
        except Exception:
            logger.debug("langdetect failed on export sample", exc_info=True)
    return "en"


def _export_epub(
    export_dir: Path,
    entries: list[dict[str, Any]],
    timestamp: str,
    domain_label: str,
) -> dict[str, Any]:
    """Export all entries as an EPUB3 ebook.

    Builds a Markdown book from the entries (one chapter per entry) and
    renders it via :func:`autoinfo.output.ebook.render_epub`.  The file is
    written to ``exports/autoinfo-export-<domain>-<timestamp>.epub``.

    Returns
    -------
    dict
        Standard export result dict with keys: ``format``, ``path``,
        ``entries_count``, ``domain``, ``success``, plus ``data_b64``
        (base64-encoded EPUB bytes).
    """
    from autoinfo.output import _domain_display_name  # noqa: PLC0415 - stays in autoinfo.output
    from autoinfo.output.ebook import render_epub  # noqa: PLC0415

    chapters: list[tuple[str, str]] = []
    for e in entries:
        title = e.get("title", "Untitled")
        file_path = e.get("file_path") or ""
        content = ""
        if file_path and Path(file_path).is_file():
            raw = Path(file_path).read_text(encoding="utf-8")
            if raw.startswith("---"):
                end_idx = raw.find("---", 3)
                content = raw[end_idx + 3 :].strip() if end_idx != -1 else raw
            else:
                content = raw
        summary = e.get("summary", "") or ""
        body = f"{summary}\n\n{content}".strip() if summary else content
        chapters.append((title, body))

    result = render_epub(
        title=f"{_domain_display_name(domain_label)} \u2014 Export",
        author="AutoInfo",
        lang=_derive_export_lang(entries),
        chapters=chapters,
    )

    out_name = f"autoinfo-export-{domain_label}-{timestamp}.epub"
    out_path = export_dir / out_name
    out_path.write_bytes(base64.b64decode(result["data_b64"]))

    return {
        "format": "epub",
        "path": str(out_path),
        "entries_count": len(entries),
        "domain": domain_label,
        "success": True,
        "data_b64": result["data_b64"],
    }


def _export_mobi(
    export_dir: Path,
    entries: list[dict[str, Any]],
    timestamp: str,
    domain_label: str,
) -> dict[str, Any]:
    """Export all entries as a Kindle MOBI file.

    Renders an EPUB in memory (same book as :func:`_export_epub`) and
    converts it via calibre's ``ebook-convert``
    (:func:`autoinfo.output.ebook.render_mobi`).  The file is written to
    ``exports/autoinfo-export-<domain>-<timestamp>.mobi``.

    Returns
    -------
    dict
        Standard export result dict with keys: ``format``, ``path``,
        ``entries_count``, ``domain``, ``success``, plus ``data_b64``
        (base64-encoded MOBI bytes).
    """
    from autoinfo.output import _domain_display_name  # noqa: PLC0415 - stays in autoinfo.output
    from autoinfo.output.ebook import render_epub, render_mobi  # noqa: PLC0415

    chapters: list[tuple[str, str]] = []
    for e in entries:
        title = e.get("title", "Untitled")
        file_path = e.get("file_path") or ""
        content = ""
        if file_path and Path(file_path).is_file():
            raw = Path(file_path).read_text(encoding="utf-8")
            if raw.startswith("---"):
                end_idx = raw.find("---", 3)
                content = raw[end_idx + 3 :].strip() if end_idx != -1 else raw
            else:
                content = raw
        summary = e.get("summary", "") or ""
        body = f"{summary}\n\n{content}".strip() if summary else content
        chapters.append((title, body))

    epub_result = render_epub(
        title=f"{_domain_display_name(domain_label)} \u2014 Export",
        author="AutoInfo",
        lang=_derive_export_lang(entries),
        chapters=chapters,
    )
    result = render_mobi(epub_result["data_b64"])

    out_name = f"autoinfo-export-{domain_label}-{timestamp}.mobi"
    out_path = export_dir / out_name
    out_path.write_bytes(base64.b64decode(result["data_b64"]))

    return {
        "format": "mobi",
        "path": str(out_path),
        "entries_count": len(entries),
        "domain": domain_label,
        "success": True,
        "data_b64": result["data_b64"],
    }


# ---------------------------------------------------------------------------
# RSS export
# ---------------------------------------------------------------------------


def _export_rss(
    export_dir: Path,
    domain: str | None,
    entries: list[dict[str, Any]],
    timestamp: str,
    domain_label: str,
) -> dict[str, Any]:
    """Export all entries as an RSS 2.0 XML feed (stdlib only).

    Builds a valid RSS 2.0 feed with channel metadata and one ``<item>``
    per entry.  Written to ``exports/<domain>/autoinfo-rss-*.xml``.

    Returns
    -------
    dict
        Standard export result dict with keys: ``format``, ``path``,
        ``entries_count``, ``domain``, ``success``.
    """
    from autoinfo.output import datetime, timezone  # noqa: PLC0415 - package seam

    # Create domain subdirectory under exports/
    domain_dir = export_dir / (domain if domain else "all")
    domain_dir.mkdir(parents=True, exist_ok=True)

    out_name = f"autoinfo-rss-{domain_label}-{timestamp}.xml"
    out_path = domain_dir / out_name

    # --- Build RSS 2.0 XML --------------------------------------------------
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    title_text = domain_label if domain_label != "*" else "AutoInfo Knowledge Base"
    ET.SubElement(channel, "title").text = f"AutoInfo - {title_text}"
    ET.SubElement(channel, "link").text = "https://autoinfo.ai"
    ET.SubElement(channel, "description").text = (
        f"Knowledge base feed for {title_text}"
    )
    ET.SubElement(channel, "language").text = "en"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(
        datetime.now(timezone.utc)
    )
    ET.SubElement(channel, "generator").text = "AutoInfo v1.5"

    for e in entries:
        item = ET.SubElement(channel, "item")

        title = e.get("title") or "Untitled"
        source_url = e.get("source_url") or ""
        description = e.get("summary") or ""
        entry_id = e.get("entry_id") or ""
        collected_at = e.get("collected_at") or ""

        ET.SubElement(item, "title").text = title
        if source_url:
            ET.SubElement(item, "link").text = source_url
        if description:
            ET.SubElement(item, "description").text = description

        guid = ET.SubElement(item, "guid", isPermaLink="false")
        guid.text = entry_id or source_url or title

        if collected_at:
            try:
                dt = datetime.fromisoformat(collected_at)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                ET.SubElement(item, "pubDate").text = format_datetime(dt)
            except (ValueError, TypeError):
                pass

    # --- Serialize -----------------------------------------------------------
    tree = ET.ElementTree(rss)
    tree.write(str(out_path), encoding="utf-8", xml_declaration=True)

    return {
        "format": "rss",
        "path": str(out_path),
        "entries_count": len(entries),
        "domain": domain_label,
        "success": True,
    }


def _export_sitemap(
    export_dir: Path,
    domain: str | None,
    entries: list[dict[str, Any]],
    domain_label: str,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Export all entries as an XML sitemap (sitemaps.org protocol).

    Builds one ``<url>`` element per KB entry using the entry's source
    URL as ``<loc>`` and a ``<lastmod>`` derived from ``collected_at``.
    An index page is always included via :func:`generate_sitemap`.
    Written to ``exports/<domain>/sitemap.xml``.

    Parameters
    ----------
    export_dir:
        Directory under which the ``<domain>/sitemap.xml`` file is written.
    domain:
        Domain filter; ``None`` means all domains.
    entries:
        KB entries to include in the sitemap.
    domain_label:
        Domain label used in the result dict (``"*"`` when no domain).
    base_url:
        Site base URL for the sitemap index page (e.g.
        ``"https://your-site.example"``).  Required.

    Returns
    -------
    dict
        Standard export result dict with keys: ``format``, ``path``,
        ``entries_count``, ``domain``, ``success``.

    Raises
    ------
    ValueError
        If *base_url* is not provided.
    """
    from autoinfo.output import datetime, timezone  # noqa: PLC0415 - package seam
    from autoinfo.output.seo import generate_sitemap

    if not base_url:
        raise ValueError(
            "Sitemap export requires an explicit base_url (no default is "
            "assumed). Pass base_url='https://your-site.example' to "
            "export_kb(format='sitemap', base_url='https://your-site.example'), "
            "or use the CLI: autoinfo output sitemap --base-url https://your-site.example"
        )

    # Create domain subdirectory under exports/
    domain_dir = export_dir / (domain if domain else "all")
    domain_dir.mkdir(parents=True, exist_ok=True)

    out_path = domain_dir / "sitemap.xml"

    sitemap_entries: list[dict[str, Any]] = []
    for e in entries:
        url = e.get("source_url") or ""
        if not url:
            continue

        lastmod = ""
        collected_at = e.get("collected_at") or ""
        if collected_at:
            try:
                dt = datetime.fromisoformat(collected_at)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                lastmod = dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                pass

        sitemap_entries.append({
            "url": url,
            "lastmod": lastmod,
            "changefreq": "weekly",
            "priority": 0.8,
        })

    xml = generate_sitemap(
        domain=domain or "",
        base_url=base_url,
        entries=sitemap_entries,
    )
    out_path.write_text(xml, encoding="utf-8")

    return {
        "format": "sitemap",
        "path": str(out_path),
        "entries_count": len(entries),
        "domain": domain_label,
        "success": True,
    }


def _export_csv(
    export_dir: Path,
    domain: str | None,
    entries: list[dict[str, Any]],
    timestamp: str,
    domain_label: str,
) -> dict[str, Any]:
    """Export all entries as a CSV file (stdlib csv module).

    Writes one row per entry with headers matching KBEntry field names.
    Complex fields (lists, dicts) are serialised as JSON strings.
    Written to ``exports/<domain>/autoinfo-csv-<timestamp>.csv``.

    Returns
    -------
    dict
        Standard export result dict with keys: ``format``, ``path``,
        ``entries_count``, ``domain``, ``success``.
    """
    import csv as _csv
    import json as _json

    domain_dir = export_dir / (domain if domain else "all")
    domain_dir.mkdir(parents=True, exist_ok=True)

    out_name = f"autoinfo-csv-{domain_label}-{timestamp}.csv"
    out_path = domain_dir / out_name

    field_names: list[str] = []
    field_set: set[str] = set()
    for e in entries:
        for k in e:
            if k not in field_set:
                field_set.add(k)
                field_names.append(k)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = _csv.DictWriter(f, fieldnames=field_names, extrasaction="ignore")
        writer.writeheader()
        for e in entries:
            row: dict[str, str] = {}
            for k in field_names:
                val = e.get(k)
                if isinstance(val, (list, dict)):
                    row[k] = _json.dumps(val, ensure_ascii=False)
                elif val is None:
                    row[k] = ""
                else:
                    row[k] = str(val)
            writer.writerow(row)

    return {
        "format": "csv",
        "path": str(out_path),
        "entries_count": len(entries),
        "domain": domain_label,
        "success": True,
    }


def _export_graphml(
    export_dir: Path,
    domain: str | None,
    timestamp: str,
    domain_label: str,
) -> dict[str, Any]:
    """Export the knowledge graph as GraphML.

    Uses :meth:`KBStore.export_knowledge_graph` to retrieve entities
    and relations, then builds a GraphML XML document.

    Written to ``exports/<domain>/autoinfo-graphml-<timestamp>.graphml``.

    Returns
    -------
    dict
        Standard export result dict with keys: ``format``, ``path``,
        ``entries_count``, ``domain``, ``success``.
    """
    from xml.etree import ElementTree as _ET  # noqa: N814

    from autoinfo.output import KBStore  # noqa: PLC0415 - package seam

    store = KBStore()
    data = store.export_knowledge_graph(domain=domain or "")

    root = _ET.Element("graphml", xmlns="http://graphml.graphdrawing.org/xmlns")

    key_id = _ET.SubElement(root, "key")
    key_id.set("id", "k0")
    key_id.set("for", "node")
    key_id.set("attr.name", "entity_type")
    key_id.set("attr.type", "string")

    key_name = _ET.SubElement(root, "key")
    key_name.set("id", "k1")
    key_name.set("for", "node")
    key_name.set("attr.name", "entity_name")
    key_name.set("attr.type", "string")

    key_rel = _ET.SubElement(root, "key")
    key_rel.set("id", "k2")
    key_rel.set("for", "edge")
    key_rel.set("attr.name", "relation_type")
    key_rel.set("attr.type", "string")

    key_str = _ET.SubElement(root, "key")
    key_str.set("id", "k3")
    key_str.set("for", "edge")
    key_str.set("attr.name", "strength")
    key_str.set("attr.type", "double")

    graph = _ET.SubElement(root, "graph")
    graph.set("id", "G")
    graph.set("edgedefault", "undirected")

    for ent in data.get("entities", []):
        eid = str(ent.get("id", ""))
        if not eid:
            continue
        node = _ET.SubElement(graph, "node")
        node.set("id", eid)
        d0 = _ET.SubElement(node, "data")
        d0.set("key", "k0")
        d0.text = str(ent.get("entity_type", ent.get("type", "entity")))
        d1 = _ET.SubElement(node, "data")
        d1.set("key", "k1")
        d1.text = str(ent.get("name", ent.get("label", eid)))

    for rel in data.get("relations", []):
        src = str(rel.get("source_id", ""))
        tgt = str(rel.get("target_id", ""))
        if not src or not tgt:
            continue
        edge = _ET.SubElement(graph, "edge")
        edge.set("id", f"e{rel.get('id', '')}")
        edge.set("source", src)
        edge.set("target", tgt)
        d2 = _ET.SubElement(edge, "data")
        d2.set("key", "k2")
        d2.text = str(rel.get("relation_type", rel.get("type", "related_to")))
        d3 = _ET.SubElement(edge, "data")
        d3.set("key", "k3")
        d3.text = str(rel.get("strength", rel.get("weight", "1.0")))

    xml_bytes = _ET.tostring(root, encoding="unicode", xml_declaration=True)

    domain_dir = export_dir / (domain if domain else "all")
    domain_dir.mkdir(parents=True, exist_ok=True)

    out_name = f"autoinfo-graphml-{domain_label}-{timestamp}.graphml"
    out_path = domain_dir / out_name
    out_path.write_text(xml_bytes, encoding="utf-8")

    return {
        "format": "graphml",
        "path": str(out_path),
        "entries_count": len(data.get("entities", [])),
        "domain": domain_label,
        "success": True,
    }


def _export_agent_json(
    entries: list[dict[str, Any]],
    domain: str | None,
    domain_label: str,
) -> dict[str, Any]:
    """Export KB entries as agent-native JSON-LD (``@type: KnowledgeBaseExport``)."""
    from autoinfo.output import (  # noqa: PLC0415 - package seam
        _JSONLD_BASE_EXPORT,
        datetime,
        timezone,
    )

    agent_entries: list[dict[str, Any]] = []
    for e in entries[:200]:
        agent_entries.append({
            "entry_id": e.get("entry_id", ""),
            "title": e.get("title", ""),
            "summary": e.get("summary", ""),
            "source_url": e.get("source_url", ""),
            "source_platform": e.get("source_platform", ""),
            "tier": e.get("tier", ""),
            "tags": _parse_tags_list(e.get("tags")),
            "relevance_score": e.get("relevance_score"),
            "collected_at": e.get("collected_at", ""),
        })

    output: dict[str, Any] = {
        **_JSONLD_BASE_EXPORT,
        "uuid": str(uuid.uuid4()),
        "domain": domain_label,
        "entries": agent_entries,
        "schema_summary": {
            "fields": [
                "entry_id", "title", "summary", "source_url",
                "source_platform", "tier", "tags", "relevance_score",
                "collected_at",
            ],
            "entry_schema_version": "1.0",
        },
        "stats": {
            "total_entries": len(entries),
            "exported_entries": len(agent_entries),
            "domain": domain or "*",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "success": True,
    }
    return output


# ---------------------------------------------------------------------------
# Bundle export
# ---------------------------------------------------------------------------


def _export_bundle(
    knowledge_dir: Path,
    export_dir: Path,
    domain: str | None,
    entries: list[dict[str, Any]],
    timestamp: str,
    domain_label: str,
    pdf_timeout: float = 120.0,
) -> dict[str, Any]:
    """Export a multi-format ZIP bundle containing PDF + JSON + Markdown + YAML.

    Generates four files inside a ZIP archive:

    - ``report.pdf`` — PDF report (skipped gracefully if weasyprint unavailable)
    - ``data.json`` — JSON data with full entry details
    - ``summary.md`` — Markdown summary listing all entries
    - ``metadata.yaml`` — Export metadata (domain, timestamp, entry count, etc.)

    Returns
    -------
    dict
        Standard export result dict with additional key ``formats`` listing
        the formats actually included in the bundle.
    """
    from autoinfo.output import _build_bundle_pdf  # noqa: PLC0415 - package seam

    out_name = f"bundle-{domain_label}-{timestamp}.zip"
    out_path = export_dir / out_name

    # Buffer for in-memory ZIP
    buf = io.BytesIO()
    included_formats: list[str] = []
    pdf_skipped = False

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:

        # --- 1. JSON data ----------------------------------------------------
        json_content = _build_bundle_json(entries)
        zf.writestr("data.json", json_content)
        included_formats.append("json")

        # --- 2. Markdown summary ---------------------------------------------
        md_content = _build_bundle_markdown(entries, domain, domain_label, timestamp)
        zf.writestr("summary.md", md_content)
        included_formats.append("md")

        # --- 3. Metadata YAML ------------------------------------------------
        yaml_content = _build_bundle_metadata(
            domain_label, timestamp, entries, included_formats
        )
        zf.writestr("metadata.yaml", yaml_content)
        included_formats.append("yaml")

        # --- 4. PDF report (graceful fallback) --------------------------------
        try:
            pdf_bytes = _build_bundle_pdf(
                entries, domain, domain_label, timestamp, pdf_timeout=pdf_timeout
            )
            zf.writestr("report.pdf", pdf_bytes)
            included_formats.append("pdf")
        except Exception as exc:
            logger.warning(
                "Bundle PDF generation skipped: %s. "
                "Bundle will contain JSON, Markdown, and YAML only.",
                exc,
            )
            pdf_skipped = True

    # Write ZIP to disk
    out_path.write_bytes(buf.getvalue())

    result: dict[str, Any] = {
        "format": "bundle",
        "path": str(out_path),
        "entries_count": len(entries),
        "domain": domain_label,
        "success": True,
        "formats": included_formats,
    }
    if pdf_skipped:
        result["warning"] = (
            "PDF was skipped — weasyprint not available. "
            "Install with: pip install weasyprint"
        )
    # Empty-state guard (issue #301): signal when the bundle has no entries
    # so callers never silently ship an empty deliverable.
    if not entries:
        result.setdefault("warnings", []).append(
            "Bundle contains no entries — the export is an empty shell."
        )
    return result


def _build_bundle_json(entries: list[dict[str, Any]]) -> str:
    """Build JSON content for the bundle."""
    export_data: list[dict[str, Any]] = []
    for e in entries:
        file_path = e.get("file_path") or ""
        content = ""
        if file_path and Path(file_path).is_file():
            content = Path(file_path).read_text(encoding="utf-8")

        export_data.append({
            "entry_id": e.get("entry_id"),
            "title": e.get("title"),
            "domain": e.get("domain"),
            "tier": e.get("tier"),
            "source_url": e.get("source_url"),
            "source_type": e.get("source_type"),
            "source_platform": e.get("source_platform"),
            "attribution": e.get("attribution", ""),
            "collected_at": e.get("collected_at"),
            "summary": e.get("summary"),
            "tags": json.loads(e.get("tags", "[]")) if e.get("tags") else [],
            "relevance_score": e.get("relevance_score"),
            "dedup_status": e.get("dedup_status"),
            "file_path": file_path,
            "content": content,
        })

    return json.dumps(export_data, ensure_ascii=False, indent=2)


def _build_bundle_markdown(
    entries: list[dict[str, Any]],
    domain: str | None,
    domain_label: str,
    timestamp: str,
) -> str:
    """Build a Markdown summary of all entries for the bundle."""
    lines: list[str] = []
    if domain:
        lines.append(f"# {domain} — Knowledge Base Export")
    else:
        lines.append("# AutoInfo Knowledge Base Export")

    lines.append("")
    lines.append(f"**Exported:** {timestamp}  ")
    lines.append(f"**Entries:** {len(entries)}  ")
    lines.append(f"**Domain:** {domain_label}  ")
    lines.append("")

    for i, e in enumerate(entries, 1):
        title = e.get("title", "Untitled")
        summary = e.get("summary", "")
        source_url = e.get("source_url", "")
        tier = e.get("tier", "")
        relevance = e.get("relevance_score")

        lines.append(f"## {i}. {title}")
        lines.append("")

        if summary:
            lines.append(summary)
            lines.append("")

        meta: list[str] = []
        if source_url:
            meta.append(f"Source: {source_url}")
        if tier:
            meta.append(f"Tier: {tier}")
        if relevance is not None:
            meta.append(f"Relevance: {relevance}")
        if meta:
            lines.append(" | ".join(meta))
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def _build_bundle_metadata(
    domain_label: str,
    timestamp: str,
    entries: list[dict[str, Any]],
    included_formats: list[str],
) -> str:
    """Build YAML metadata for the bundle."""
    metadata: dict[str, Any] = {
        "domain": domain_label,
        "generated_at": timestamp,
        "entry_count": len(entries),
        "export_version": "1.0",
        "formats_included": included_formats,
        "generator": "AutoInfo",
    }
    return str(yaml.dump(metadata, default_flow_style=False, allow_unicode=True))


def _build_bundle_pdf(
    entries: list[dict[str, Any]],
    domain: str | None,
    domain_label: str,
    timestamp: str,
    pdf_timeout: float = 120.0,
) -> bytes:
    """Build a PDF report in memory using weasyprint.

    Raises ``ValueError`` if weasyprint or markdown are not installed.
    Returns the raw PDF bytes.
    """
    try:
        import weasyprint  # noqa: PLC0415
    except (ImportError, ModuleNotFoundError) as exc:
        raise ValueError(
            "weasyprint is not installed. PDF export requires weasyprint."
        ) from exc

    try:
        import markdown as md_lib  # noqa: PLC0415
    except (ImportError, ModuleNotFoundError) as exc:
        raise ValueError(
            "markdown library is not installed."
        ) from exc

    # Build HTML document
    html_parts: list[str] = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><style>",
        "body{font-family:sans-serif;margin:2em;line-height:1.6;color:#333;}",
        "h1{color:#222;border-bottom:2px solid #ddd;padding-bottom:0.3em;}",
        "h2{color:#444;margin-top:1.5em;}",
        "h3{color:#555;}",
        ".meta{color:#777;font-size:0.9em;margin-bottom:1em;}",
        ".entry{page-break-inside:avoid;margin-bottom:2em;}",
        ".entry-content{margin-top:0.5em;}",
        "pre{background:#f5f5f5;padding:1em;border-radius:4px;",
        "overflow-x:auto;border:1px solid #e0e0e0;}",
        "code{background:#f0f0f0;padding:0.2em 0.4em;border-radius:3px;font-size:0.9em;}",
        "pre code{background:none;padding:0;}",
        "table{border-collapse:collapse;width:100%;margin:1em 0;}",
        "th,td{border:1px solid #ddd;padding:0.5em;text-align:left;}",
        "th{background:#f5f5f5;}",
        "blockquote{border-left:4px solid #ddd;margin:1em 0;padding:0.5em 1em;color:#666;}",
        "img{max-width:100%;height:auto;}",
        "</style></head><body>",
    ]

    if domain:
        html_parts.append(f"<h1>{html.escape(domain)}</h1>")
    else:
        html_parts.append("<h1>AutoInfo Knowledge Base Export</h1>")

    html_parts.append(
        f"<p class='meta'>Exported: {html.escape(timestamp)}  |  "
        f"Entries: {len(entries)}</p>"
    )

    for e in entries:
        title = e.get("title", "Untitled")
        file_path = e.get("file_path") or ""

        content = ""
        if file_path and Path(file_path).is_file():
            raw = Path(file_path).read_text(encoding="utf-8")
            if raw.startswith("---"):
                end_idx = raw.find("---", 3)
                if end_idx != -1:
                    content = raw[end_idx + 3:].strip()
                else:
                    content = raw
            else:
                content = raw

        html_parts.append("<div class='entry'>")
        html_parts.append(f"<h2>{html.escape(title)}</h2>")

        meta_bits: list[str] = []
        if e.get("source_url"):
            url = html.escape(e["source_url"])
            meta_bits.append(f'Source: <a href="{url}">{url}</a>')
        if e.get("source_type"):
            meta_bits.append(f"Type: {html.escape(e['source_type'])}")
        if e.get("tier"):
            meta_bits.append(f"Tier: {html.escape(e['tier'])}")
        if e.get("relevance_score") is not None:
            meta_bits.append(f"Relevance: {e['relevance_score']}")
        if meta_bits:
            html_parts.append(f"<p class='meta'>{' | '.join(meta_bits)}</p>")

        summary = e.get("summary", "")
        if summary:
            html_parts.append(
                f"<p><strong>Summary:</strong> {html.escape(summary[:1000])}</p>"
            )

        if content:
            content_html = md_lib.markdown(
                content, extensions=["fenced_code", "tables"]
            )
            html_parts.append(f"<div class='entry-content'>{content_html}</div>")

        html_parts.append("</div>")

    html_parts.append("</body></html>")

    full_html = "\n".join(html_parts)

    # Render to PDF bytes
    try:
        return cast(
            bytes,
            _run_pdf_with_timeout(
                lambda: weasyprint.HTML(string=full_html).write_pdf(),
                timeout=pdf_timeout,
                desc="Bundle PDF rendering",
            ),
        )
    except Exception as exc:
        logger.error("Bundle PDF generation failed: %s", exc)
        raise ValueError(
            f"PDF generation failed: {exc}"
        ) from exc


# DDL for the entries table — used as fallback when no source DB exists
_ENTRIES_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS entries (
    entry_id        TEXT PRIMARY KEY,
    title           TEXT,
    domain          TEXT,
    tier            TEXT DEFAULT '01-Raw',
    source_url      TEXT,
    source_type     TEXT,
    source_platform TEXT,
    collected_at    TEXT,
    summary         TEXT,
    quality_tier    INTEGER,
    relevance_score REAL,
    dedup_status    TEXT,
    file_path       TEXT,
    tags            TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
)
"""


def _wal_checkpoint(db_path: Path) -> None:
    """Force a WAL checkpoint so the main DB file is fully synced.

    SQLite's WAL journal can leave committed transactions in a
    separate ``-wal`` file.  This function checkpoints them back
    into the main database file so file-level operations (copy,
    backup) see a consistent snapshot.
    """
    if not db_path.is_file():
        return
    try:
        conn = sqlite3.connect(f"file:{db_path.resolve()}?checkpoint=truncate", uri=True)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    except Exception:
        pass


def _create_filtered_sqlite_copy(
    src_path: Path,
    dst_path: Path,
    entries: list[dict[str, Any]],
) -> int:
    """Create a new SQLite DB at *dst_path* with only *entries*.

    Reads the table schema from *src_path* (if it exists) or creates it
    from scratch.  Returns the number of entries copied.
    """
    dst_conn = sqlite3.connect(str(dst_path))
    dst_conn.row_factory = sqlite3.Row
    dst_conn.execute("PRAGMA journal_mode=WAL")
    dst_conn.execute("PRAGMA synchronous=NORMAL")

    schema_sql: list[str] = []
    index_sql: list[str] = []
    fts5_sql: list[str] = []

    if src_path.is_file():
        # Open source to read schema
        src_conn = sqlite3.connect(str(src_path))
        src_conn.row_factory = sqlite3.Row

        # Get table DDL
        for row in src_conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='entries'"
        ).fetchall():
            if row["sql"]:
                schema_sql.append(row["sql"])

        for row in src_conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name NOT LIKE 'idx_%_tier'"
        ).fetchall():
            if row["sql"] and row["sql"].strip():
                index_sql.append(row["sql"])

        for row in src_conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='entries_fts5'"
        ).fetchall():
            if row["sql"]:
                fts5_sql.append(row["sql"])

        src_conn.close()

    # Fallback: create schema from scratch if source has none
    if not schema_sql:
        schema_sql = [_ENTRIES_TABLE_DDL]

    # Create tables
    for sql_str in schema_sql:
        dst_conn.execute(sql_str)
    for sql_str in index_sql:
        try:
            dst_conn.execute(sql_str)
        except Exception:
            pass
    for sql_str in fts5_sql:
        try:
            dst_conn.execute(sql_str)
        except Exception:
            pass

    # Insert entries
    count = 0
    for e in entries:
        dst_conn.execute(
            """
            INSERT OR REPLACE INTO entries
                (entry_id, title, domain, tier, source_url, source_type,
                 source_platform, collected_at, summary, quality_tier,
                 relevance_score, dedup_status, file_path, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                e.get("entry_id"),
                e.get("title"),
                e.get("domain"),
                e.get("tier", "01-Raw"),
                e.get("source_url"),
                e.get("source_type"),
                e.get("source_platform"),
                e.get("collected_at"),
                e.get("summary"),
                e.get("quality_tier", 1),
                e.get("relevance_score", 0.0),
                e.get("dedup_status", "unique"),
                e.get("file_path"),
                e.get("tags", "[]"),
            ),
        )
        count += 1

    dst_conn.commit()
    dst_conn.close()

    return count
