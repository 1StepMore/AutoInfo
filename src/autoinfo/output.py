"""Output generation — digests, reports, and KB export.

Provides the ``export_kb`` function for exporting knowledge base data
in Markdown (tar.gz), JSON, or SQLite format.

Usage::

    from autoinfo.output import export_kb

    # Export a single domain as JSON
    result = export_kb(domain="medical-research", format="json")

    # Export the entire KB as Markdown tar.gz
    result = export_kb(format="markdown")
"""

from __future__ import annotations

import html
import json
import logging
import shutil
import sqlite3
import tarfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, Template, select_autoescape

from autoinfo.config import Config, get_config_path, load_config
from autoinfo.kb import KBStore, SQLiteIndex

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def export_kb(
    domain: str | None = None,
    format: str = "markdown",
    collection_id: str | None = None,  # reserved for future use
) -> dict[str, Any]:
    """Export knowledge base data to the requested format.

    Parameters
    ----------
    domain:
        Optional domain filter.  When ``None``, the entire KB is exported.
    format:
        Output format: ``"markdown"`` (default), ``"json"``, ``"sqlite"``, or
        ``"pdf"``.
    collection_id:
        Reserved for future collection-scoped export (not yet implemented).

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
        If *format* is not one of the supported values.
    """
    if format not in ("markdown", "json", "sqlite", "pdf"):
        raise ValueError(
            f"Unsupported export format: '{format}'. "
            f"Supported: markdown, json, sqlite, pdf"
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
            "collected_at": e.get("collected_at"),
            "summary": e.get("summary"),
            "tags": json.loads(e.get("tags", "[]")) if e.get("tags") else [],
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


def _export_pdf(
    knowledge_dir: Path,
    export_dir: Path,
    domain: str | None,
    entries: list[dict[str, Any]],
    timestamp: str,
    domain_label: str,
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
        weasyprint.HTML(string=full_html).write_pdf(str(out_path))
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


# ---------------------------------------------------------------------------
# Digest generation
# ---------------------------------------------------------------------------

PERIOD_DAYS: dict[str, int] = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
}

PERIOD_LABELS: dict[str, str] = {
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
}


def _compute_date_range(period: str) -> tuple[str, str]:
    """Return (date_from, date_to) ISO strings for the given period.

    Parameters
    ----------
    period:
        One of ``"daily"``, ``"weekly"``, ``"monthly"``.

    Returns
    -------
    tuple[str, str]
        ``(date_from, date_to)`` — ``date_from`` is *period* days ago,
        ``date_to`` is today (both as ``YYYY-MM-DD``).
    """
    days = PERIOD_DAYS.get(period, 7)
    today = date.today()
    date_from = (today - timedelta(days=days)).isoformat()
    date_to = today.isoformat()
    return date_from, date_to


# ---------------------------------------------------------------------------
# Template loader
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = Path(__file__).resolve().parent / "data" / "templates"

_jinja_env: Environment | None = None


def _get_jinja_env() -> Environment:
    """Return a cached Jinja2 environment for the ``data/templates/`` directory."""
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape(default=False),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _jinja_env


# ---------------------------------------------------------------------------
# LLM synthesis for digests
# ---------------------------------------------------------------------------

_DIGEST_SYSTEM_PROMPT = (
    "You are a research digest assistant. Given a list of knowledge base "
    "entries from the past period, synthesize them into a concise digest. "
    "Respond with valid JSON only, no markdown formatting."
)

_DIGEST_FIELD_DESCRIPTIONS = [
    '"executive_summary": "2-3 sentence overview of the period\'s key developments"',
    '"key_findings": [{"topic": "Topic name", "detail": "Key finding sentence"}], '
    "list 3-5 most important findings",
    '"trends": ["Trend or pattern observed across multiple entries"], '
    "list relevant cross-cutting trends",
    '"recommendations": ["Actionable recommendation based on the data"], '
    "list actionable recommendations if any",
]


def _build_digest_llm_prompt(entries: list[dict[str, Any]]) -> str:
    """Build the user prompt for LLM digest synthesis."""
    lines: list[str] = [
        "Synthesize the following knowledge base entries into a digest.",
        "",
    ]

    for i, entry in enumerate(entries, 1):
        title = entry.get("title", "(no title)")
        summary = entry.get("summary", "")
        tags_raw = entry.get("tags", "")
        if isinstance(tags_raw, str):
            try:
                tags_list = json.loads(tags_raw)
            except (json.JSONDecodeError, TypeError):
                tags_list = [tags_raw] if tags_raw else []
        elif isinstance(tags_raw, list):
            tags_list = tags_raw
        else:
            tags_list = []
        tags_str = ", ".join(tags_list) if tags_list else "\u2014"

        lines.append(f"Entry {i}:")
        lines.append(f"  Title: {title}")
        lines.append(f"  Summary: {summary[:500] if summary else '\u2014'}")
        lines.append(f"  Tags: {tags_str}")
        lines.append("")

    lines.append("Now generate a JSON digest with the following fields:")
    for desc in _DIGEST_FIELD_DESCRIPTIONS:
        lines.append(f"  - {desc}")
    lines.append("")
    lines.append("Return all fields in a single JSON object.")

    return "\n".join(lines)


def _call_llm_for_digest(
    prompt: str,
    config: Config | None = None,
) -> dict[str, Any]:
    """Call LiteLLM to synthesize a digest from entries.

    Uses the same LiteLLM pattern as :class:`LLMExtractor` but with
    a custom summarization prompt.
    """
    try:
        import litellm  # noqa: PLC0415
    except (ImportError, ModuleNotFoundError):
        logger.error("litellm is not installed \u2014 run 'pip install litellm'")
        return {}

    if config is None:
        config_path = get_config_path()
        if config_path is not None:
            try:
                config = load_config(config_path)
            except Exception:
                config = Config()
        else:
            config = Config()

    provider = config.llm.provider or "openrouter"
    model = config.llm.model or "deepseek/deepseek-chat"
    full_model = f"{provider}/{model}"

    try:
        response = litellm.completion(
            model=full_model,
            messages=[
                {"role": "system", "content": _DIGEST_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=2000,
            temperature=0.1,
        )
    except Exception as exc:
        logger.error("LLM digest synthesis failed: %s", exc)
        return {}

    content: str = response.choices[0].message.content  # type: ignore[union-attr]
    return _parse_json_response(content)


def _parse_json_response(content: str) -> dict[str, Any]:
    """Parse a JSON string with fallback strategies.

    1. Direct :func:`json.loads`.
    2. Extract JSON from markdown code blocks.
    3. Find the first ``{…}`` brace-delimited block.
    """
    import re  # noqa: PLC0415

    # Strategy 1 — direct
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Strategy 2 — fenced code block
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3 — bare JSON object
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse LLM digest response as JSON: %.200s", content)
    return {}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_digest(
    domain: str,
    period: str = "weekly",
    format: str = "markdown",
    llm_config: Config | None = None,
) -> str:
    """Generate a digest of KB entries for *domain* over the given *period*.

    Parameters
    ----------
    domain:
        Domain to generate the digest for (e.g. ``"medical-research"``).
    period:
        Digest period.  One of ``"daily"``, ``"weekly"``, ``"monthly"``.
        Defaults to ``"weekly"``.
    format:
        Output format.  One of ``"markdown"``, ``"html"``, ``"json"``.
        Defaults to ``"markdown"``.
    llm_config:
        Optional :class:`Config` override for LLM settings.  When omitted,
        the config is auto-detected from the project directory.

    Returns
    -------
    str
        The generated digest in the requested format.

    Raises
    ------
    ValueError
        If *period* is not one of ``"daily"``, ``"weekly"``, ``"monthly"``,
        or if *format* is not one of ``"markdown"``, ``"html"``, ``"json"``.
    """
    # --- Validate parameters ------------------------------------------------
    if period not in PERIOD_DAYS:
        raise ValueError(
            f"Invalid period '{period}'. Must be one of: {', '.join(sorted(PERIOD_DAYS))}"
        )
    valid_formats = {"markdown", "html", "json"}
    if format not in valid_formats:
        raise ValueError(
            f"Invalid format '{format}'. Must be one of: {', '.join(sorted(valid_formats))}"
        )

    # --- Compute date range --------------------------------------------------
    date_from, date_to = _compute_date_range(period)
    period_label = PERIOD_LABELS.get(period, period.capitalize())

    # --- Query KB entries ----------------------------------------------------
    from autoinfo.kb import KBStore  # noqa: PLC0415

    store = KBStore()
    entries = store.list_entries(
        domain=domain,
        date_from=date_from,
        limit=200,
    )

    # --- Parse tags for each entry (they come as JSON strings from SQLite) ----
    for entry in entries:
        tags_raw = entry.get("tags", "")
        if isinstance(tags_raw, str):
            try:
                entry["tags"] = json.loads(tags_raw)
            except (json.JSONDecodeError, TypeError):
                entry["tags"] = [tags_raw] if tags_raw else []
        elif not isinstance(tags_raw, list):
            entry["tags"] = []

    # --- LLM synthesis -------------------------------------------------------
    llm_synthesis: dict[str, Any] = {}
    if entries:
        prompt = _build_digest_llm_prompt(entries)
        llm_synthesis = _call_llm_for_digest(prompt, config=llm_config)
    else:
        llm_synthesis = {}

    # --- Build template context ----------------------------------------------
    generated_at = datetime.now(timezone.utc).isoformat()
    context = {
        "title": f"{period_label} Digest \u2014 {domain}",
        "domain": domain,
        "period": period,
        "period_label": period_label,
        "date_from": date_from,
        "date_to": date_to,
        "generated_at": generated_at,
        "entries": entries,
        "llm_synthesis": llm_synthesis,
    }

    # --- Render --------------------------------------------------------------
    if format == "json":
        return _render_json(context)

    raw_md = _render_markdown(context)

    if format == "html":
        return _render_html(raw_md)

    return raw_md


# ---------------------------------------------------------------------------
# Report generation — structured Jinja2 + LLM reports from KB entries
# ---------------------------------------------------------------------------

TEMPLATE_PATH = Path(__file__).resolve().parent / "data" / "templates" / "report.md.j2"


@dataclass
class ReportSection:
    """A single themed section within a report."""

    title: str
    content: str
    items: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ReportData:
    """Full report data passed to the Jinja2 template."""

    title: str
    generated_at: str
    domain: str
    collection_id: str = ""
    executive_summary: str = ""
    sections: list[ReportSection] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    appendices: list[dict[str, Any]] = field(default_factory=list)


def generate_report(
    domain: str,
    collection_id: str | None = None,
    format: str = "markdown",
    period: str = "month",
) -> str:
    """Generate a structured report for the given *domain*.

    Groups KB entries by theme using an LLM, produces an executive
    summary, and renders the result through the Jinja2 report template.

    Parameters
    ----------
    domain : str
        Domain to generate the report for (e.g. ``"medical-research"``).
    collection_id : str, optional
        Optional collection ID to scope the report to a specific
        collection run.  When omitted, all KB entries for the domain
        are included.
    format : str, optional
        Output format (default ``"markdown"``).  Supports ``"markdown"``
        and ``"json"``.
    period : str, optional
        Report period label (default ``"month"``).  Used for metadata
        in JSON output.

    Returns
    -------
    str
        Rendered report string.

    Raises
    ------
    ValueError
        If *format* is unsupported.
    FileNotFoundError
        If the Jinja2 template file is not found.
    """
    if format not in ("markdown", "json"):
        raise ValueError(
            f"Unsupported output format: {format!r}. "
            f"Supported: markdown, json"
        )

    # -- Load KB entries --------------------------------------------------
    from autoinfo.llm import LLMExtractor  # noqa: PLC0415

    kb_store = KBStore()
    entries = kb_store.list_entries(domain, limit=5000)

    if not entries:
        if format == "json":
            empty_data = {
                "title": f"{domain} \u2014 Report",
                "summary": "",
                "entries": [],
                "metadata": {
                    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                    "domain": domain,
                    "period": period,
                    "format": "json",
                    "entry_count": 0,
                },
            }
            return json.dumps(empty_data, indent=2, ensure_ascii=False)
        return _render_empty_report(domain)

    # -- Build reference list from entries --------------------------------
    references = [
        {
            "title": e.get("title", ""),
            "source_url": e.get("source_url", ""),
            "source_type": e.get("source_type", ""),
            "source_platform": e.get("source_platform", ""),
        }
        for e in entries
    ]

    # -- Thematic grouping via LLM ----------------------------------------
    extractor = LLMExtractor()
    groupings = _group_by_theme(extractor, entries)

    # -- Generate executive summary via LLM --------------------------------
    executive_summary = _generate_executive_summary(extractor, entries, groupings)

    # -- Build report data -------------------------------------------------
    sections = [
        ReportSection(
            title=g["theme"],
            content=g.get("description", ""),
            items=[
                {
                    "title": e.get("title", ""),
                    "summary": e.get("summary", ""),
                    "source_url": e.get("source_url", ""),
                    "relevance_score": e.get("relevance_score", 0),
                }
                for e in g["entries"]
            ],
        )
        for g in groupings
    ]

    report_data = ReportData(
        title=f"{domain} \u2014 Report",
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        domain=domain,
        collection_id=collection_id or "",
        executive_summary=executive_summary,
        sections=sections,
        references=references,
    )

    # -- Render -------------------------------------------------------------
    if format == "json":
        return _render_report_json(report_data, period=period)

    # -- Render via Jinja2 template ----------------------------------------
    return _render_report_template(report_data)


# ---------------------------------------------------------------------------
# Report internal helpers
# ---------------------------------------------------------------------------


def _group_by_theme(
    extractor: LLMExtractor,
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group KB entries by theme using the LLM.

    Returns a list of dicts::

        [
            {
                "theme": "IVF Treatment Outcomes",
                "description": "...",
                "entries": [...],
            },
        ]

    Falls back to a single "General" group when the LLM call fails.
    """
    # Build a compact representation of entries for the LLM prompt
    entry_summaries = "\n".join(
        f"- [{e.get('entry_id', '?')}] {e.get('title', '?')}: "
        f"{e.get('summary', '(no summary)')}"
        for e in entries
    )

    prompt = (
        "Group the following knowledge base entries into 3\u20135 coherent "
        "themes. Each theme must represent a distinct topic area. "
        "Return a JSON object with a single key 'groups' whose value is "
        "an array of objects. Each object must have:\n"
        "  - 'theme': short theme name (2\u20135 words)\n"
        "  - 'description': 2\u20133 sentence description of this theme\n"
        "  - 'entry_ids': array of entry IDs belonging to this theme\n\n"
        f"Entries:\n{entry_summaries}"
    )

    try:
        groups_raw = _llm_json_extract(extractor, prompt, "groups")
    except Exception as exc:
        logger.warning("Thematic grouping via LLM failed: %s", exc)
        groups_raw = None

    if not groups_raw:
        # Fallback: single group with all entries
        return [
            {
                "theme": "General",
                "description": (
                    f"All {len(entries)} entries included in this report."
                ),
                "entries": entries,
            }
        ]

    # Map entry IDs back to actual entry objects
    entry_map: dict[str, dict[str, Any]] = {}
    for e in entries:
        eid = e.get("entry_id", "")
        if eid:
            entry_map[eid] = e

    result: list[dict[str, Any]] = []
    for g in groups_raw:
        group_entries = [
            entry_map[eid]
            for eid in g.get("entry_ids", [])
            if eid in entry_map
        ]
        if group_entries:
            result.append({
                "theme": g.get("theme", "Untitled"),
                "description": g.get("description", ""),
                "entries": group_entries,
            })

    # Ensure no entry is left out (ungrouped entries go into a catch-all)
    grouped_ids: set[str] = set()
    for g in result:
        for e in g["entries"]:
            eid = e.get("entry_id", "")
            if eid:
                grouped_ids.add(eid)

    ungrouped = [e for e in entries if e.get("entry_id", "") not in grouped_ids]
    if ungrouped:
        result.append({
            "theme": "Additional Topics",
            "description": (
                f"{len(ungrouped)} entry(ies) not covered by other themes."
            ),
            "entries": ungrouped,
        })

    return result


def _generate_executive_summary(
    extractor: LLMExtractor,
    entries: list[dict[str, Any]],
    groupings: list[dict[str, Any]],
) -> str:
    """Generate an executive summary via LLM.

    Falls back to a simple bullet-list summary when the LLM call fails.
    """
    themes_summary = "\n".join(
        f"- {g['theme']}: {len(g['entries'])} entries"
        for g in groupings
    )

    prompt = (
        "Write a concise executive summary (3\u20135 paragraphs) for a "
        f"report covering {len(entries)} knowledge base entries across "
        f"the following themes:\n\n{themes_summary}\n\n"
        "Focus on the key findings and overall significance. "
        "Return a JSON object with a single key 'executive_summary' "
        "whose value is the summary text."
    )

    try:
        raw = _llm_json_extract(extractor, prompt, "executive_summary")
        if raw and isinstance(raw, str) and raw.strip():
            return raw.strip()
    except Exception as exc:
        logger.warning("Executive summary via LLM failed: %s", exc)

    # Fallback
    theme_bullets = "\n".join(
        f"- **{g['theme']}**: {len(g['entries'])} entry(ies)"
        for g in groupings
    )
    return (
        f"This report covers {len(entries)} knowledge base entries "
        f"grouped into {len(groupings)} themes:\n\n{theme_bullets}"
    )


def _llm_json_extract(
    extractor: LLMExtractor,
    prompt: str,
    field: str,
) -> Any:
    """Call the LLM and extract a top-level JSON field.

    Uses :class:`LLMExtractor` under the hood by wrapping the prompt in
    a minimal ``Item``.  Returns the value of *field* from the parsed
    JSON response, or ``None`` on failure.
    """
    from autoinfo.models import Item  # noqa: PLC0415

    dummy = Item(
        id="_report_llm_call",
        source_name="report",
        source_type="internal",
        source_url="",
        title=field.replace("_", " ").title(),
        content=prompt,
    )
    result = extractor.extract(dummy, schema=[field])
    return result.custom_fields.get(field)


def _render_report_json(report_data: ReportData, period: str = "month") -> str:
    """Render the report data as a JSON string.

    The JSON structure includes ``title``, ``summary``, a flat ``entries``
    list (with ``title``, ``summary``, ``url``, ``date`` per entry), and
    ``metadata`` with generation context.
    """
    entries_list: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for section in report_data.sections:
        for item in section.items:
            url = item.get("source_url", "") or ""
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            entries_list.append({
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "url": url,
                "date": item.get("collected_at", ""),
            })

    # Also include any references not already covered
    for ref in report_data.references:
        url = ref.get("source_url", "") or ""
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        entries_list.append({
            "title": ref.get("title", ""),
            "summary": "",
            "url": url,
            "date": "",
        })

    output = {
        "title": report_data.title,
        "summary": report_data.executive_summary,
        "entries": entries_list,
        "metadata": {
            "generated_at": report_data.generated_at,
            "domain": report_data.domain,
            "period": period,
            "format": "json",
            "entry_count": len(entries_list),
        },
    }
    return json.dumps(output, indent=2, ensure_ascii=False, default=str)


def _render_report_template(report_data: ReportData) -> str:
    """Render the report data through the Jinja2 template."""
    if not TEMPLATE_PATH.is_file():
        raise FileNotFoundError(
            f"Report template not found at {TEMPLATE_PATH}"
        )

    template_source = TEMPLATE_PATH.read_text(encoding="utf-8")
    template = Template(template_source)

    return template.render(
        title=report_data.title,
        generated_at=report_data.generated_at,
        domain=report_data.domain,
        collection_id=report_data.collection_id,
        executive_summary=report_data.executive_summary,
        sections=[
            {
                "title": s.title,
                "content": s.content,
                "entries": s.items,
            }
            for s in report_data.sections
        ],
        references=report_data.references,
        appendices=report_data.appendices,
    )


def _render_empty_report(domain: str) -> str:
    """Return a brief message when there are no entries for *domain*."""
    return (
        f"# {domain} \u2014 Report\n\n"
        f"_No knowledge base entries found for domain '{domain}'._"
    )


# ---------------------------------------------------------------------------
# LLM-based translation (F10)
# ---------------------------------------------------------------------------

_TRANSLATION_SYSTEM_PROMPT = (
    "You are a professional medical translator. Translate the following "
    "knowledge base entry into the target language. "
    "CRITICAL: Preserve all medical terminology, drug names, procedures, "
    "and technical terms in their original form — do NOT translate terms "
    "like IVF, RCT, embryo, blastocyst, gonadotropin, etc. "
    "Keep numbers, statistics, and citations exactly as-is. "
    "Respond with valid JSON only: "
    '{"translated_title": "...", "translated_body": "..."}'
)


def _call_llm_for_translation(
    title: str,
    body: str,
    target_lang: str,
    config: Config | None = None,
) -> dict[str, str]:
    """Translate *title* and *body* into *target_lang* via LiteLLM.

    Returns a dict with ``translated_title`` and ``translated_body``.
    Returns empty strings on failure.
    """
    try:
        import litellm  # noqa: PLC0415
    except (ImportError, ModuleNotFoundError):
        logger.error("litellm is not installed — run 'pip install litellm'")
        return {"translated_title": "", "translated_body": ""}

    if config is None:
        config_path = get_config_path()
        if config_path is not None:
            try:
                config = load_config(config_path)
            except Exception:
                config = Config()
        else:
            config = Config()

    provider = config.llm.provider or "openrouter"
    model = config.llm.model or "deepseek/deepseek-chat"
    full_model = f"{provider}/{model}"

    user_prompt = (
        f"Target language: {target_lang}\n\n"
        f"Title: {title}\n\n"
        f"Body:\n{body}\n\n"
        "Translate the title and body above into the target language. "
        "Preserve all medical terminology, drug names, procedures, "
        "statistics, and citations exactly. Return valid JSON."
    )

    try:
        response = litellm.completion(
            model=full_model,
            messages=[
                {"role": "system", "content": _TRANSLATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=4000,
            temperature=0.1,
        )
    except Exception as exc:
        logger.error("LLM translation failed: %s", exc)
        return {"translated_title": "", "translated_body": ""}

    content: str = response.choices[0].message.content  # type: ignore[union-attr]
    parsed = _parse_json_response(content)
    return {
        "translated_title": parsed.get("translated_title", ""),
        "translated_body": parsed.get("translated_body", ""),
    }


def localize_content(
    content_id: str | None = None,
    content: str | None = None,
    source_lang: str = "",
    target_lang: str = "",
) -> dict[str, Any]:
    """Translate a KB entry or raw text into *target_lang*.

    Two modes:

    **Content-ID mode** (reads from KB, stores translation)::

        result = localize_content(
            content_id="kb-entry-001",
            target_lang="zh",
        )

    **Direct content mode** (no storage, returns translation)::

        result = localize_content(
            content="Hello world",
            source_lang="en",
            target_lang="fr",
        )

    Parameters
    ----------
    content_id:
        KB entry ID to translate.  The entry must exist in the KB store.
    content:
        Raw text to translate directly (no KB lookup).
    source_lang:
        Source language code (e.g. ``"en"``, ``"zh"``).  Required for
        direct-content mode; optional for content-ID mode (auto-detected
        from the KB entry's ``language`` field).
    target_lang:
        Target language code (e.g. ``"zh"``, ``"fr"``, ``"ja"``).
        **Required**.

    Returns
    -------
    dict
        Keys:
        - ``translated_title`` — translated title (empty if direct content)
        - ``translated_body`` — translated text
        - ``target_lang`` — language code used
        - ``source_lang`` — detected or provided source language
        - ``file_path`` — path to stored translation file (content-ID mode only)
        - ``success`` — whether translation succeeded

    Raises
    ------
    ValueError
        If the required parameters are missing or *target_lang* is empty.
    """
    if not target_lang:
        raise ValueError("target_lang is required")

    if content_id:
        from autoinfo.kb import KBStore  # noqa: PLC0415

        store = KBStore()
        entry = store.get_entry(content_id)
        if entry is None:
            raise ValueError(f"KB entry '{content_id}' not found")

        src_lang = source_lang or entry.get("language", "en")

        file_path_str = entry.get("file_path", "")
        body = ""
        if file_path_str:
            fp = Path(file_path_str)
            if fp.is_file():
                raw = fp.read_text(encoding="utf-8")
                if raw.startswith("---"):
                    end_idx = raw.find("---", 3)
                    if end_idx != -1:
                        body = raw[end_idx + 3:].strip()
                    else:
                        body = raw
                else:
                    body = raw

        result = _call_llm_for_translation(
            title=entry.get("title", ""),
            body=body,
            target_lang=target_lang,
        )

        if not result.get("translated_title") and not result.get("translated_body"):
            return {
                "success": False,
                "error": "LLM translation returned empty result",
                "content_id": content_id,
                "target_lang": target_lang,
                "source_lang": src_lang,
            }

        translated_file_path = _write_translated_file(entry, result, src_lang, target_lang)

        return {
            "success": True,
            "translated_title": result.get("translated_title", ""),
            "translated_body": result.get("translated_body", ""),
            "target_lang": target_lang,
            "source_lang": src_lang,
            "file_path": str(translated_file_path) if translated_file_path else "",
            "content_id": content_id,
        }

    if content is not None:
        if not source_lang:
            raise ValueError("source_lang is required for direct content translation")
        result = _call_llm_for_translation(
            title="",
            body=content,
            target_lang=target_lang,
        )

        if not result.get("translated_body"):
            return {
                "success": False,
                "error": "LLM translation returned empty result",
                "target_lang": target_lang,
                "source_lang": source_lang,
            }

        return {
            "success": True,
            "translated_title": result.get("translated_title", ""),
            "translated_body": result.get("translated_body", ""),
            "target_lang": target_lang,
            "source_lang": source_lang,
        }

    raise ValueError("Either content_id or content must be provided")


def _write_translated_file(
    entry: dict[str, Any],
    translation: dict[str, str],
    source_lang: str,
    target_lang: str,
) -> Path | None:
    """Write the translated Markdown file alongside the original KB entry.

    Creates: ``knowledge/<domain>/<tier>/<topic>/<date>-<slug>.<lang>.md``

    Returns the path to the written file, or ``None`` on failure.
    """
    from datetime import datetime, timezone  # noqa: PLC0415

    original_path = entry.get("file_path", "")
    if not original_path:
        return None

    orig = Path(original_path)
    if not orig.is_file():
        return None

    translated_path = orig.with_name(
        f"{orig.stem}.{target_lang}{orig.suffix}"
    )

    raw = orig.read_text(encoding="utf-8")
    frontmatter: dict[str, Any] = {}
    body = raw
    if raw.startswith("---"):
        end_idx = raw.find("---", 3)
        if end_idx != -1:
            fm_raw = raw[3:end_idx]
            import yaml  # noqa: PLC0415
            frontmatter = yaml.safe_load(fm_raw) or {}
            body = raw[end_idx + 3:].strip()

    frontmatter["translated_from"] = source_lang
    frontmatter["translated_to"] = target_lang
    frontmatter["translated_at"] = datetime.now(timezone.utc).isoformat()
    frontmatter["original_entry_id"] = entry.get("entry_id", "")
    frontmatter["original_file"] = str(orig)

    translated_title = translation.get("translated_title", "")
    if translated_title:
        frontmatter["title"] = translated_title

    translated_body = translation.get("translated_body", body)

    full_content = (
        "---\n"
        f"{yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)}"
        "---\n\n"
        f"{translated_body}"
    )
    translated_path.write_text(full_content, encoding="utf-8")
    return translated_path


# ---------------------------------------------------------------------------
# Tutorial generation
# ---------------------------------------------------------------------------

_VALID_AUDIENCES = frozenset({"researcher", "clinician", "executive", "student"})

_AUDIENCE_DESCRIPTIONS: dict[str, str] = {
    "researcher": "technical depth, citations, methodology focus, statistical rigor",
    "clinician": "practical application, clinical guidelines, patient outcomes, treatment protocols",
    "executive": "strategic overview, ROI, competitive landscape, high-level implications",
    "student": "foundational concepts, simplified explanations, step-by-step learning, study aids",
}


def generate_tutorial(
    domain: str,
    collection_id: str | None = None,
    target_audience: str = "student",
    format: str = "markdown",
) -> str:
    """Generate a structured tutorial for *domain*, adapted to *target_audience*.

    Fetches KB entries, asks the LLM to structure a learning path with
    objectives, content sections, and exercises, then renders the result
    through ``tutorial.md.j2``.

    Parameters
    ----------
    domain : str
        Domain to generate the tutorial for (e.g. ``"medical-research"``).
    collection_id : str, optional
        Optional collection ID to scope the tutorial to a specific
        collection run.  When omitted, all KB entries for the domain
        are included.
    target_audience : str
        Intended audience for the tutorial.  One of ``"researcher"``,
        ``"clinician"``, ``"executive"``, ``"student"`` (default).
    format : str, optional
        Output format (default ``"markdown"``).  Only ``"markdown"``
        is currently supported.

    Returns
    -------
    str
        Rendered tutorial string.

    Raises
    ------
    ValueError
        If *format* or *target_audience* is unsupported.
    """
    if format != "markdown":
        raise ValueError(f"Unsupported output format: {format!r}")

    if target_audience not in _VALID_AUDIENCES:
        raise ValueError(
            f"Invalid target_audience '{target_audience}'. "
            f"Must be one of: {', '.join(sorted(_VALID_AUDIENCES))}"
        )

    # -- Load KB entries --------------------------------------------------
    kb_store = KBStore()
    entries = kb_store.list_entries(domain, limit=5000)

    if not entries:
        return (
            f"# {domain} — Tutorial\n\n"
            f"_No knowledge base entries found for domain '{domain}'._"
        )

    # -- Build LLM prompt with audience adaptation ------------------------
    audience_desc = _AUDIENCE_DESCRIPTIONS.get(target_audience, "general audience")
    entry_summaries = "\n".join(
        f"- [{e.get('entry_id', '?')}] {e.get('title', '?')}: "
        f"{e.get('summary', '(no summary)')}"
        for e in entries
    )

    prompt = (
        f"You are a tutorial designer creating content for a {target_audience} "
        f"audience ({audience_desc}). "
        "Given the following knowledge base entries, structure them into a "
        "coherent learning path. "
        "Return a JSON object with the following fields:\n"
        '  - "title": tutorial title (string)\n'
        '  - "duration": estimated reading/completion time (string, e.g. "45 minutes")\n'
        '  - "prerequisites": comma-separated prerequisites (string)\n'
        '  - "objectives": array of 3-5 learning objective strings\n'
        '  - "content": array of section objects, each with:\n'
        '      - "heading": section heading\n'
        '      - "body": 2-4 paragraph section content\n'
        '      - "code_example": optional code/example snippet (string or null)\n'
        '      - "code_language": language for the code snippet (string or null)\n'
        '      - "key_takeaway": one-line takeaway (string or null)\n'
        '  - "exercises": array of exercise objects, each with:\n'
        '      - "title": exercise title\n'
        '      - "description": exercise description\n'
        '      - "hint": optional hint (string or null)\n'
        '      - "solution": optional solution (string or null)\n'
        '  - "summary": 2-3 sentence summary of the tutorial\n'
        '  - "further_reading": array of reference strings\n\n'
        f"KB Entries:\n{entry_summaries}\n\n"
        "Return all fields in a single JSON object. Adapt depth, terminology, "
        f"and examples specifically for a {target_audience} audience."
    )

    llm_result = _call_llm_for_tutorial(prompt)

    # -- Build template context -------------------------------------------
    generated_at = datetime.now(timezone.utc).isoformat()
    context = {
        "title": llm_result.get("title", f"{domain} — Tutorial"),
        "domain": domain,
        "target_audience": target_audience,
        "collection_id": collection_id or "",
        "duration": llm_result.get("duration", "TBD"),
        "prerequisites": llm_result.get("prerequisites", "None"),
        "objectives": llm_result.get("objectives", []),
        "content": llm_result.get("content", []),
        "exercises": llm_result.get("exercises", []),
        "summary": llm_result.get("summary", ""),
        "further_reading": llm_result.get("further_reading", []),
        "generated_at": generated_at,
    }

    # -- Render via Jinja2 template ---------------------------------------
    return _render_tutorial_template(context)


def _call_llm_for_tutorial(prompt: str) -> dict[str, Any]:
    """Call LiteLLM to generate structured tutorial content.

    Uses the same pattern as ``_call_llm_for_digest``.
    """
    try:
        import litellm  # noqa: PLC0415
    except (ImportError, ModuleNotFoundError):
        logger.error("litellm is not installed — run 'pip install litellm'")
        return {}

    config_path = get_config_path()
    if config_path and config_path.is_file():
        try:
            config = load_config(config_path)
        except Exception:
            config = Config()
    else:
        config = Config()

    provider = config.llm.provider or "openrouter"
    model = config.llm.model or "deepseek/deepseek-chat"
    full_model = f"{provider}/{model}"

    try:
        response = litellm.completion(
            model=full_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a tutorial designer. Given knowledge base "
                    "entries, structure them into a coherent learning path. "
                    "Respond with valid JSON only, no markdown formatting.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=4000,
            temperature=0.3,
        )
    except Exception as exc:
        logger.error("LLM tutorial synthesis failed: %s", exc)
        return {}

    content: str = response.choices[0].message.content  # type: ignore[union-attr]
    return _parse_json_response(content)


def _render_tutorial_template(context: dict[str, Any]) -> str:
    """Render the tutorial data through ``tutorial.md.j2``."""
    env = _get_jinja_env()
    template = env.get_template("tutorial.md.j2")
    return template.render(**context)


# ---------------------------------------------------------------------------
# Presentation generation
# ---------------------------------------------------------------------------


def generate_presentation(
    domain: str,
    topic: str,
    slide_count: int = 10,
    target_audience: str = "executive",
    format: str = "markdown",
) -> str:
    """Generate a slide-based presentation for *topic* within *domain*.

    Searches the KB for entries related to *topic*, asks the LLM to
    produce structured slide content, and renders through ``presentation.md.j2``.

    Parameters
    ----------
    domain : str
        Domain to scope the presentation to (e.g. ``"medical-research"``).
    topic : str
        Presentation topic — used to filter relevant KB entries.
    slide_count : int, optional
        Desired number of slides (default 10, range 3–30).
    target_audience : str, optional
        Intended audience.  One of ``"researcher"``, ``"clinician"``,
        ``"executive"`` (default), ``"student"``.
    format : str, optional
        Output format (default ``"markdown"``).  Only ``"markdown"``
        is currently supported.

    Returns
    -------
    str
        Rendered presentation string.

    Raises
    ------
    ValueError
        If *format*, *target_audience*, or *slide_count* is invalid.
    """
    if format != "markdown":
        raise ValueError(f"Unsupported output format: {format!r}")

    if target_audience not in _VALID_AUDIENCES:
        raise ValueError(
            f"Invalid target_audience '{target_audience}'. "
            f"Must be one of: {', '.join(sorted(_VALID_AUDIENCES))}"
        )

    slide_count = max(3, min(30, slide_count))

    # -- Load KB entries related to topic --------------------------------
    kb_store = KBStore()
    entries = kb_store.list_entries(domain, limit=5000)

    # Filter entries by topic relevance (title/summary contains topic terms)
    topic_terms = topic.lower().split()
    topic_entries = [
        e
        for e in entries
        if any(
            term in (e.get("title", "") + " " + e.get("summary", "")).lower()
            for term in topic_terms
        )
    ]

    if not topic_entries:
        # Fall back to all entries for the domain
        topic_entries = entries[:50]

    # -- Build LLM prompt -------------------------------------------------
    audience_desc = _AUDIENCE_DESCRIPTIONS.get(target_audience, "general audience")
    entry_summaries = "\n".join(
        f"- [{e.get('entry_id', '?')}] {e.get('title', '?')}: "
        f"{e.get('summary', '(no summary)')}"
        for e in topic_entries[:100]  # cap entries sent to LLM
    )

    prompt = (
        f"You are a presentation designer creating a slide deck for a "
        f"{target_audience} audience ({audience_desc}). "
        f"Topic: {topic}\n\n"
        "Given the following knowledge base entries, generate slide content. "
        f"Aim for approximately {slide_count} slides.\n"
        "Return a JSON object with the following fields:\n"
        '  - "title": presentation title (string)\n'
        '  - "description": one-sentence description (string)\n'
        '  - "slides": array of slide objects, each with:\n'
        '      - "title": slide heading\n'
        '      - "content": 2-4 sentence slide body\n'
        '      - "bullets": array of 2-5 bullet points (strings)\n'
        '      - "notes": speaker notes (string, optional — may be null)\n\n'
        f"KB Entries:\n{entry_summaries}\n\n"
        "Return all fields in a single JSON object. Adapt depth and terminology "
        f"specifically for a {target_audience} audience."
    )

    llm_result = _call_llm_for_presentation(prompt, slide_count)

    # -- Build template context -------------------------------------------
    generated_at = datetime.now(timezone.utc).isoformat()
    context = {
        "title": llm_result.get("title", f"{topic} — Presentation"),
        "topic": topic,
        "domain": domain,
        "target_audience": target_audience,
        "description": llm_result.get("description", ""),
        "slides": llm_result.get("slides", []),
        "generated_at": generated_at,
    }

    # -- Render via Jinja2 template ---------------------------------------
    return _render_presentation_template(context)


def _call_llm_for_presentation(prompt: str, slide_count: int) -> dict[str, Any]:
    """Call LiteLLM to generate structured presentation content."""
    try:
        import litellm  # noqa: PLC0415
    except (ImportError, ModuleNotFoundError):
        logger.error("litellm is not installed — run 'pip install litellm'")
        return {}

    config_path = get_config_path()
    if config_path and config_path.is_file():
        try:
            config = load_config(config_path)
        except Exception:
            config = Config()
    else:
        config = Config()

    provider = config.llm.provider or "openrouter"
    model = config.llm.model or "deepseek/deepseek-chat"
    full_model = f"{provider}/{model}"

    try:
        response = litellm.completion(
            model=full_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a presentation designer. Given knowledge base "
                    "entries, generate structured slide content. "
                    "Respond with valid JSON only, no markdown formatting.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=4000,
            temperature=0.3,
        )
    except Exception as exc:
        logger.error("LLM presentation synthesis failed: %s", exc)
        return {}

    content: str = response.choices[0].message.content  # type: ignore[union-attr]
    return _parse_json_response(content)


def _render_presentation_template(context: dict[str, Any]) -> str:
    """Render the presentation data through ``presentation.md.j2``."""
    env = _get_jinja_env()
    template = env.get_template("presentation.md.j2")
    return template.render(**context)


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def _render_markdown(context: dict[str, Any]) -> str:
    """Render the Jinja2 digest template to Markdown."""
    env = _get_jinja_env()
    template = env.get_template("digest.md.j2")
    return template.render(**context)


def _render_html(markdown_text: str) -> str:
    """Convert Markdown to plain HTML (no CSS styling).

    Uses the ``markdown`` library (already a project dependency) to
    produce bare HTML without any stylesheets or CSS classes.
    """
    try:
        import markdown as md_lib  # noqa: PLC0415

        return md_lib.markdown(markdown_text, extensions=["fenced_code", "tables"])
    except (ImportError, ModuleNotFoundError):
        logger.warning("markdown library not available \u2014 returning raw markdown")
        return markdown_text


def _render_json(context: dict[str, Any]) -> str:
    """Render the digest as a JSON string.

    The JSON structure separates metadata, LLM synthesis, and entries
    so consumers can parse with full fidelity.
    """
    output = {
        "digest_type": "digest",
        "domain": context["domain"],
        "period": context["period"],
        "period_label": context["period_label"],
        "date_from": context["date_from"],
        "date_to": context["date_to"],
        "generated_at": context["generated_at"],
        "entry_count": len(context["entries"]),
        "llm_synthesis": context["llm_synthesis"],
        "entries": context["entries"],
    }
    return json.dumps(output, indent=2, ensure_ascii=False, default=str)
