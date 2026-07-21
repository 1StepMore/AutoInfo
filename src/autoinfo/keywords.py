"""Keywords management — per-domain ``_keywords.yaml`` state machine.

Provides the :class:`KeywordsFile` class to manage keyword lifecycles in a
YAML-backed store per domain.  Keyword states follow a simple progression:

    ``AUTO_ADDED`` → ``VERIFIED`` (via :meth:`approve_keyword`)
    ``*`` → ``DEPRECATED``       (via :meth:`deprecate_keyword`)

File format (``knowledge/<domain>/_keywords.yaml``)::

    keywords:
        ivf:
            state: verified
            aliases: ["in-vitro fertilization"]
            created_at: "2026-07-21T12:00:00+00:00"
            updated_at: "2026-07-21T12:00:00+00:00"
            source: "auto-discovery"
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import yaml

logger = logging.getLogger(__name__)

# Sentinel to distinguish "not provided" from AUTO_ADDED in add_keyword
_UNSET = object()


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class KeywordState(str, enum.Enum):
    """Valid states in the keyword lifecycle."""

    VERIFIED = "verified"
    AUTO_ADDED = "auto_added"
    DEPRECATED = "deprecated"


@dataclass
class KeywordEntry:
    """A single keyword entry with metadata."""

    keyword: str
    state: KeywordState = KeywordState.AUTO_ADDED
    aliases: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    source: str = ""


# ---------------------------------------------------------------------------
# File-backed keyword store
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


class KeywordsFile:
    """Manage a per-domain ``_keywords.yaml`` file.

    Parameters
    ----------
    base_dir : str | Path, optional
        Root directory containing ``knowledge/``.  Defaults to current
        working directory.
    """

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self._base_dir = Path(base_dir or Path.cwd())

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _path(self, domain: str) -> Path:
        """Return the full path to ``knowledge/<domain>/_keywords.yaml``."""
        return self._base_dir / "knowledge" / domain / "_keywords.yaml"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, domain: str) -> list[KeywordEntry]:
        """Load all keywords for *domain* from its ``_keywords.yaml``.

        Returns an empty list when the file does not exist (logs a warning).
        """
        path = self._path(domain)
        if not path.is_file():
            logger.warning("Keywords file not found for domain '%s': %s", domain, path)
            return []

        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        kw_map: dict[str, Any] = raw.get("keywords", {}) or {}

        entries: list[KeywordEntry] = []
        for keyword, data in kw_map.items():
            if data is None:
                data = {}
            state_raw = data.get("state", "auto_added")
            try:
                state = KeywordState(state_raw)
            except ValueError:
                state = KeywordState.AUTO_ADDED
            entries.append(
                KeywordEntry(
                    keyword=keyword,
                    state=state,
                    aliases=data.get("aliases", []),
                    created_at=data.get("created_at", ""),
                    updated_at=data.get("updated_at", ""),
                    source=data.get("source", ""),
                )
            )

        return entries

    def save(self, domain: str, entries: list[KeywordEntry]) -> None:
        """Write *entries* to ``knowledge/<domain>/_keywords.yaml``.

        The file is written with the schema::

            keywords:
              <keyword>:
                state: <str>
                aliases: [<str>, ...]
                created_at: <ISO-8601>
                updated_at: <ISO-8601>
                source: <str>
        """
        path = self._path(domain)
        path.parent.mkdir(parents=True, exist_ok=True)

        kw_map: dict[str, dict[str, Any]] = {}
        for entry in entries:
            kw_map[entry.keyword] = {
                "state": entry.state.value,
                "aliases": entry.aliases,
                "created_at": entry.created_at,
                "updated_at": entry.updated_at,
                "source": entry.source,
            }

        raw = {"keywords": kw_map}
        path.write_text(
            yaml.dump(raw, default_flow_style=False, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    def create_if_missing(self, domain: str) -> bool:
        """Create an empty ``_keywords.yaml`` for *domain* if it does not exist.

        Returns ``True`` if the file was created, ``False`` if it already
        existed.
        """
        path = self._path(domain)
        if path.is_file():
            return False

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.dump({"keywords": {}}, default_flow_style=False, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        logger.info("Created keywords file: %s", path)
        return True

    def add_keyword(
        self,
        domain: str,
        keyword: str,
        state: object = _UNSET,
        aliases: list[str] | None = None,
        source: str = "",
    ) -> KeywordEntry:
        """Add a keyword to *domain* (idempotent — updates existing).

        When the keyword already exists, only explicitly-provided fields
        are updated.  If *state* is omitted the existing state is preserved
        for existing keywords; new keywords default to ``AUTO_ADDED``.

        Parameters
        ----------
        domain : str
            Domain name.
        keyword : str
            The keyword string.
        state : KeywordState, optional
            State to set.  When omitted the existing state is preserved
            for existing keywords; new keywords default to ``AUTO_ADDED``.
        aliases : list[str], optional
            Additional aliases (merged with existing, no duplicates).
        source : str, optional
            Provenance source (e.g. ``"auto-discovery"``, ``"user"``).
            Overwrites the existing source when provided.

        Returns
        -------
        KeywordEntry
            The entry as stored (either newly created or updated).
        """
        now = _now_iso()
        aliases = aliases or []
        state_provided = state is not _UNSET

        # Load existing entries
        entries = self.load(domain)

        # Check for existing keyword
        for entry in entries:
            if entry.keyword == keyword:
                # Update in-place — only overwrite state if explicitly provided
                if state_provided:
                    if isinstance(state, str):
                        entry.state = KeywordState(state)
                    elif isinstance(state, KeywordState):
                        entry.state = state
                if aliases:
                    # Merge new aliases (no duplicates)
                    existing_set = set(entry.aliases)
                    for a in aliases:
                        if a not in existing_set:
                            entry.aliases.append(a)
                            existing_set.add(a)
                if source:
                    entry.source = source
                entry.updated_at = now
                self.save(domain, entries)
                return entry

        # Create new entry — accept string or KeywordState
        if state_provided:
            if isinstance(state, str):
                resolved_state = KeywordState(state)
            elif isinstance(state, KeywordState):
                resolved_state = state
            else:
                raise TypeError(f"state must be str or KeywordState, got {type(state).__name__}")
        else:
            resolved_state = KeywordState.AUTO_ADDED
        new_entry = KeywordEntry(
            keyword=keyword,
            state=resolved_state,
            aliases=aliases,
            created_at=now,
            updated_at=now,
            source=source,
        )
        entries.append(new_entry)
        self.save(domain, entries)
        return new_entry

    def approve_keyword(self, domain: str, keyword: str) -> KeywordEntry | None:
        """Move a keyword from ``AUTO_ADDED`` → ``VERIFIED``.

        Returns the updated entry, or ``None`` if the keyword was not found.
        """
        entries = self.load(domain)
        for entry in entries:
            if entry.keyword == keyword:
                entry.state = KeywordState.VERIFIED
                entry.updated_at = _now_iso()
                self.save(domain, entries)
                return entry
        logger.warning("Keyword '%s' not found in domain '%s'", keyword, domain)
        return None

    def deprecate_keyword(self, domain: str, keyword: str) -> KeywordEntry | None:
        """Move a keyword to ``DEPRECATED`` state.

        Returns the updated entry, or ``None`` if the keyword was not found.
        """
        entries = self.load(domain)
        for entry in entries:
            if entry.keyword == keyword:
                entry.state = KeywordState.DEPRECATED
                entry.updated_at = _now_iso()
                self.save(domain, entries)
                return entry
        logger.warning("Keyword '%s' not found in domain '%s'", keyword, domain)
        return None

    def list_keywords(
        self,
        domain: str,
        status: KeywordState | None = None,
    ) -> list[KeywordEntry]:
        """Return keywords for *domain*, optionally filtered by *status*.

        Parameters
        ----------
        domain : str
            Domain name.
        status : KeywordState, optional
            If set, only return entries with this state (e.g. ``VERIFIED``).
            ``None`` returns all entries.

        Returns
        -------
        list[KeywordEntry]
            Matching keyword entries.
        """
        entries = self.load(domain)
        if status is not None:
            entries = [e for e in entries if e.state == status]
        return entries
