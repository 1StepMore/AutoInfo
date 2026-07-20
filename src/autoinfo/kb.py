"""Knowledge base storage — Markdown files + SQLite index.

Provides the ``KBStore`` (high-level file + index orchestration) and
``SQLiteIndex`` (lightweight metadata index) classes.

File layout::

    knowledge/<domain>/01-Raw/<topic>/<YYYY-MM-DD>-<slug>.md

Each file carries YAML frontmatter with all metadata fields needed for
fast filtering / browsing, and a plain-text body with the original
collected content plus any LLM-extracted summary / key points.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from autoinfo.models import ExtractionResult, Item, KBEntry
from autoinfo.quality import QualityResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slugify(text: str, max_len: int = 80) -> str:
    """Turn *text* into a lowercase, alphanumeric-plus-hyphens slug.

    Examples
    --------
    >>> _slugify("Improved IVF outcomes: a RCT")
    'improved-ivf-outcomes-a-rct'
    """
    slug = text.lower()
    # Replace any run of non-alphanumeric (except hyphens) with a single hyphen
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:max_len].rstrip("-")


def _parse_date(s: str) -> date:
    """Extract a ``date`` from an ISO-format datetime string or date string."""
    try:
        return datetime.fromisoformat(s).date()
    except (ValueError, TypeError):
        pass
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        pass
    return date.today()


# ---------------------------------------------------------------------------
# SQLite Index
# ---------------------------------------------------------------------------


class SQLiteIndex:
    """Lightweight SQLite metadata index for KB entries.

    Stores a subset of entry metadata to support fast listing, filtering,
    and ordering without reading Markdown files.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a connection (with row factory for dict-like rows)."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def init_db(self) -> None:
        """Create tables and indexes if they don't exist."""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS entries (
                    entry_id        TEXT PRIMARY KEY,
                    title           TEXT,
                    domain          TEXT,
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
                );

                CREATE INDEX IF NOT EXISTS idx_domain
                    ON entries(domain);

                CREATE INDEX IF NOT EXISTS idx_collected_at
                    ON entries(collected_at);

                CREATE INDEX IF NOT EXISTS idx_domain_collected
                    ON entries(domain, collected_at DESC);
            """)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def index_entry(self, entry: KBEntry) -> None:
        """Insert or replace *entry* in the SQLite index."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO entries
                    (entry_id, title, domain, source_url, source_type,
                     source_platform, collected_at, summary, quality_tier,
                     relevance_score, dedup_status, file_path, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.entry_id,
                    entry.title,
                    entry.domain,
                    entry.source_url,
                    entry.source_type,
                    entry.source_platform,
                    entry.collected_at,
                    entry.summary,
                    entry.quality_tier,
                    entry.relevance_score,
                    entry.dedup_status,
                    entry.file_path,
                    json.dumps(entry.tags, ensure_ascii=False),
                ),
            )

    def list_entries(
        self,
        domain: str,
        date_from: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List entries for *domain*, newest first, with optional date filter.

        Parameters
        ----------
        domain:
            Domain to filter by.
        date_from:
            Optional ISO date string — only entries collected on or after
            this date are returned.
        limit:
            Maximum number of rows (default 20).
        offset:
            Number of rows to skip (for pagination).

        Returns
        -------
        list[dict]
            Each dict contains the columns from the ``entries`` table.
        """
        with self._connect() as conn:
            if date_from:
                rows = conn.execute(
                    """
                    SELECT * FROM entries
                    WHERE domain = ? AND collected_at >= ?
                    ORDER BY collected_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (domain, date_from, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM entries
                    WHERE domain = ?
                    ORDER BY collected_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (domain, limit, offset),
                ).fetchall()

            return [dict(r) for r in rows]

    def get_entry(self, entry_id: str) -> dict[str, Any] | None:
        """Return a single entry dict by *entry_id*, or ``None``."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM entries WHERE entry_id = ?",
                (entry_id,),
            ).fetchone()
            return dict(row) if row else None

    def search_by_field(
        self, field: str, value: str
    ) -> list[dict[str, Any]]:
        """Search entries where *field* LIKE ``%value%``.

        .. caution::
            This is a naive LIKE search. FTS5 full-text search will be
            added in v0.2.
        """
        allowed = {
            "title", "domain", "source_url", "source_type",
            "source_platform", "dedup_status",
        }
        if field not in allowed:
            raise ValueError(
                f"search_by_field: '{field}' is not allowed. "
                f"Allowed fields: {sorted(allowed)}"
            )

        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM entries WHERE {field} LIKE ? ORDER BY collected_at DESC",
                (f"%{value}%",),
            ).fetchall()
            return [dict(r) for r in rows]

    def count_entries_today(self, domain: str | None = None) -> int:
        """Return the number of entries collected today, optionally filtered by domain."""
        today = date.today().isoformat()  # "YYYY-MM-DD"
        with self._connect() as conn:
            if domain:
                (count,) = conn.execute(
                    "SELECT COUNT(*) FROM entries WHERE domain = ? AND collected_at >= ?",
                    (domain, today),
                ).fetchone()
            else:
                (count,) = conn.execute(
                    "SELECT COUNT(*) FROM entries WHERE collected_at >= ?",
                    (today,),
                ).fetchone()
            return count

    def count_entries(self, domain: str | None = None) -> int:
        """Return the total number of entries, optionally filtered by domain."""
        with self._connect() as conn:
            if domain:
                (count,) = conn.execute(
                    "SELECT COUNT(*) FROM entries WHERE domain = ?", (domain,)
                ).fetchone()
            else:
                (count,) = conn.execute("SELECT COUNT(*) FROM entries").fetchone()
            return count


# ---------------------------------------------------------------------------
# KBStore
# ---------------------------------------------------------------------------


class KBStore:
    """High-level knowledge base store that combines Markdown files + SQLite.

    File path convention::

        knowledge/<domain>/01-Raw/<topic>/<YYYY-MM-DD>-<slug>.md

    Usage
    -----
    >>> store = KBStore(base_path=Path("knowledge"))
    >>> entry = store.store_entry(item, extraction, quality_results)
    >>> entries = store.list_entries("medical-research")
    >>> full = store.get_entry(entry.entry_id)
    """

    def __init__(self, base_path: Path = Path("knowledge")) -> None:
        self.base_path = base_path.resolve()
        # Place the SQLite db alongside the knowledge directory
        db_path = self.base_path.parent / "autoinfo.db"
        self.index = SQLiteIndex(db_path)
        self.index.init_db()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def store_entry(
        self,
        item: Item,
        extraction: ExtractionResult | None = None,
        quality_results: dict[str, QualityResult] | None = None,
    ) -> KBEntry:
        """Create a Markdown KB entry for *item* and index it in SQLite.

        Parameters
        ----------
        item:
            The collected item to persist.
        extraction:
            Optional LLM extraction output (adds TL;DR + key points to body).
        quality_results:
            Quality gate results keyed by gate name.  Used to populate
            ``relevance_score`` (from G3) and ``dedup_status`` (from G2).

        Returns
        -------
        KBEntry
            The newly created entry (also persisted to disk + index).
        """
        # --- derive metadata ---------------------------------------------------
        domain = item.domain or "default"
        topic = item.topic_tags[0] if item.topic_tags else "general"
        slug = _slugify(item.title)
        collected_date = _parse_date(item.collected_at)

        topic_slug = _slugify(topic)
        entry_id = f"{domain}-{topic_slug}-{slug}"

        # File path: knowledge/<domain>/01-Raw/<topic>/<YYYY-MM-DD>-<slug>.md
        date_str = collected_date.isoformat()
        file_dir = self.base_path / domain / "01-Raw" / topic
        file_name = f"{date_str}-{slug}.md"
        file_path = file_dir / file_name

        # --- parse quality gate results ----------------------------------------
        relevance_score: float = 0.0
        dedup_status: str = "unique"
        quality_tier: int = item.quality_tier

        if quality_results:
            g3 = quality_results.get("G3-RelevanceScoring")
            if g3 is not None:
                relevance_score = g3.score

            g2 = quality_results.get("G2-Dedup")
            if g2 is not None:
                # Prefer explicit dedup_status if set, else derive from is_duplicate
                raw = g2.details.get("dedup_status")
                if raw:
                    dedup_status = str(raw)
                elif g2.details.get("is_duplicate"):
                    dedup_status = "duplicate"

        # --- build KBEntry -----------------------------------------------------
        summary = extraction.tl_dr if extraction and extraction.tl_dr else ""
        tags = item.topic_tags[:]

        entry = KBEntry(
            entry_id=entry_id,
            title=item.title,
            domain=domain,
            tier="01-Raw",
            source_url=item.source_url,
            source_type=item.source_type,
            source_platform=item.source_name,
            collected_at=item.collected_at,
            summary=summary,
            tags=tags,
            quality_tier=quality_tier,
            relevance_score=relevance_score,
            dedup_status=dedup_status,
            file_path=str(file_path),
            language=item.language,
        )

        # --- write Markdown file ----------------------------------------------
        file_dir.mkdir(parents=True, exist_ok=True)

        frontmatter = _build_frontmatter(entry, quality_results)
        body = _build_body(item, extraction)

        full_content = f"---\n{frontmatter}---\n\n{body}"
        file_path.write_text(full_content, encoding="utf-8")

        # --- index in SQLite --------------------------------------------------
        self.index.index_entry(entry)

        return entry

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def list_entries(
        self,
        domain: str,
        date_from: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Fast listing from the SQLite index.

        Returns entries sorted by ``collected_at DESC``.
        """
        return self.index.list_entries(domain, date_from, limit, offset)

    def get_entry(self, entry_id: str) -> dict[str, Any] | None:
        """Return full entry content from the Markdown file + SQLite metadata.

        The returned dict contains all SQLite columns plus the parsed
        ``content`` (body text from the Markdown file).
        Returns ``None`` if the entry is not found.
        """
        meta = self.index.get_entry(entry_id)
        if meta is None:
            return None

        file_path = Path(meta["file_path"]) if meta["file_path"] else None
        if file_path and file_path.is_file():
            raw = file_path.read_text(encoding="utf-8")
            content = _strip_frontmatter(raw)
            meta["content"] = content
        else:
            meta["content"] = ""

        return meta

    def get_entry_by_path(self, file_path: str) -> dict[str, Any] | None:
        """Look up an entry by its file path and return full content."""
        meta = self.index.search_by_field("file_path", file_path)
        if not meta:
            return None
        return self.get_entry(meta[0]["entry_id"])


# ---------------------------------------------------------------------------
# Internal helpers — frontmatter / body building
# ---------------------------------------------------------------------------


def _build_frontmatter(
    entry: KBEntry,
    quality_results: dict[str, QualityResult] | None = None,
) -> str:
    """Render YAML frontmatter for *entry*."""
    data: dict[str, Any] = {
        "title": entry.title,
        "domain": entry.domain,
        "tier": entry.tier,
        "entry_id": entry.entry_id,
        "source_url": entry.source_url,
        "source_type": entry.source_type,
        "source_platform": entry.source_platform,
        "collected_at": entry.collected_at,
        "summary": entry.summary,
        "tags": entry.tags,
        "quality_tier": entry.quality_tier,
        "relevance_score": entry.relevance_score,
        "dedup_status": entry.dedup_status,
        "language": entry.language,
    }

    # Include quality gate flags in frontmatter for transparency
    if quality_results:
        flags: dict[str, bool] = {}
        for gname, gresult in quality_results.items():
            flags[gname] = gresult.flagged
        data["quality_flags"] = flags

    return yaml.dump(
        data,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=120,
    )


def _build_body(
    item: Item,
    extraction: ExtractionResult | None = None,
) -> str:
    """Render the body of a KB entry Markdown file.

    Structure::

        ## Original Content
        <item.content>

        ## Summary
        <extraction.tl_dr>

        ## Key Points
        - <key_point_1>
        - <key_point_2>
    """
    parts: list[str] = []

    parts.append("## Original Content\n")
    parts.append(item.content)

    if extraction:
        if extraction.tl_dr:
            parts.append("\n\n## Summary\n")
            parts.append(extraction.tl_dr)

        if extraction.key_points:
            parts.append("\n\n## Key Points\n")
            for kp in extraction.key_points:
                parts.append(f"- {kp}\n")

        if extraction.entities:
            parts.append("\n\n## Entities\n")
            for ent in extraction.entities:
                name = ent.get("name", "")
                etype = ent.get("type", "")
                rel = ent.get("relevance", "")
                parts.append(f"- **{name}** ({etype}, relevance={rel})\n")

    return "".join(parts)


def _strip_frontmatter(text: str) -> str:
    """Return the body text after the YAML frontmatter block (if any)."""
    # python-frontmatter is available in deps, but for a lightweight
    # approach we just strip the --- delimited block here.
    if text.startswith("---"):
        # Find the closing ---
        idx = text.find("---", 3)
        if idx != -1:
            return text[idx + 3 :].lstrip("\n")
    return text
