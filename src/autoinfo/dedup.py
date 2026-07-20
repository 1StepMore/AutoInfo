"""Deduplication checker for the collection pipeline.

Provides the :class:`DedupChecker` which detects duplicate items by URL
exact match and then by PMID/DOI identifiers.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from autoinfo.models import Item, KBEntry

logger = logging.getLogger(__name__)


class DedupChecker:
    """Detect duplicate items using URL + PMID/DOI matching.

    Priority:
        1. URL exact match (comparing ``item.source_url``)
        2. PMID/DOI match (if the item has raw_data with these identifiers)

    Usage::

        checker = DedupChecker(knowledge_dir="knowledge")
        existing = checker.load_existing("medical-research")
        verdict = checker.check(my_item, existing)
    """

    def __init__(self, knowledge_dir: str | Path = "knowledge") -> None:
        """Initialise checker.

        Args:
            knowledge_dir: Root path of the knowledge base directory
                (contains ``<domain>/01-Raw/`` sub-trees).
        """
        self.knowledge_dir = Path(knowledge_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_existing(self, domain: str) -> list[KBEntry]:
        """Scan ``knowledge/<domain>/01-Raw/`` for existing KB entries.

        Reads Markdown files with YAML frontmatter and returns them as
        :class:`KBEntry` instances.  Returns an empty list when the
        directory does not exist or contains no entries.

        Args:
            domain: Domain name (e.g. ``"medical-research"``).

        Returns:
            List of existing KB entries found on disk.
        """
        raw_dir = self.knowledge_dir / domain / "01-Raw"
        if not raw_dir.is_dir():
            return []

        entries: list[KBEntry] = []
        for md_file in raw_dir.rglob("*.md"):
            try:
                entry = self._parse_kb_file(md_file)
                if entry is not None:
                    entries.append(entry)
            except Exception as exc:
                logger.warning("Skipping unparseable KB file %s: %s", md_file, exc)
                continue

        return entries

    def check(
        self,
        item: Item,
        existing_entries: list[KBEntry],
    ) -> dict[str, Any]:
        """Check *item* against a list of existing KB entries for duplicates.

        Args:
            item: The freshly collected item to check.
            existing_entries: Previously stored KB entries to compare against.

        Returns:
            A dict with the verdict::

                {
                    "is_duplicate": bool,
                    "matched_by": str,      # "url" | "pmid" | "doi" | ""
                    "existing_id": str,     # matched entry ID, or ""
                }
        """
        # -- 1. URL exact match -----------------------------------------
        if item.source_url:
            for entry in existing_entries:
                if entry.source_url and entry.source_url == item.source_url:
                    return {
                        "is_duplicate": True,
                        "matched_by": "url",
                        "existing_id": entry.entry_id,
                    }

        # -- 2. PMID / DOI match ----------------------------------------
        item_pmid = item.raw_data.get("pmid", "")
        item_doi = item.raw_data.get("doi", "")

        for entry in existing_entries:
            entry_pmid = entry.custom_fields.get("pmid", "")
            entry_doi = entry.custom_fields.get("doi", "")

            if item_pmid and entry_pmid and item_pmid == entry_pmid:
                return {
                    "is_duplicate": True,
                    "matched_by": "pmid",
                    "existing_id": entry.entry_id,
                }

            if item_doi and entry_doi and item_doi == entry_doi:
                return {
                    "is_duplicate": True,
                    "matched_by": "doi",
                    "existing_id": entry.entry_id,
                }

        return {
            "is_duplicate": False,
            "matched_by": "",
            "existing_id": "",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_kb_file(path: Path) -> KBEntry | None:
        """Parse a Markdown KB file with YAML frontmatter into a KBEntry.

        The file is expected to have the format::

            ---
            title: "..."
            entry_id: "..."
            ...
            ---
            <body>

        Returns ``None`` if the file lacks valid frontmatter.
        """
        content = path.read_text(encoding="utf-8")

        # -- Extract YAML frontmatter between --- markers ----------------
        if not content.startswith("---"):
            return None

        # Find the closing ---
        end_idx = content.find("---", 3)
        if end_idx == -1:
            return None

        yaml_block = content[3:end_idx].strip()
        if not yaml_block:
            return None

        try:
            data: dict[str, Any] = yaml.safe_load(yaml_block) or {}
        except yaml.YAMLError:
            logger.warning("Invalid YAML frontmatter in %s", path)
            return None

        entry = KBEntry.from_dict(data)
        entry.file_path = str(path)
        return entry
