"""Focused tests for the dedup strategies added to :mod:`autoinfo.dedup`.

The original ``tests/collectors/test_collection.py::TestDedupChecker`` covers
URL/PMID/DOI exact matching and ``load_existing``.  This module covers the
later additions:

* fuzzy-title matching (SequenceMatcher threshold 0.85),
* the cross-domain EVENT matcher (shared proper-noun signature + death-word
  co-occurrence in each title's own language + near-dup time window),
* ``load_all_domains_entries`` (the "second domain copy is skipped" path),
* ``_parse_kb_file`` edge cases (missing/empty frontmatter, invalid YAML) and
  the ``load_existing`` skip-unparseable-file path,
* the timestamp helpers ``_within_window`` / ``_parse_dt``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from autoinfo.dedup import DedupChecker
from autoinfo.models import Item, KBEntry


def _item(
    *,
    item_id: str = "new-item",
    title: str = "",
    source_url: str = "",
    collected_at: str = "2026-08-02T00:00:00+00:00",
    language: str = "en",
    pmid: str = "",
    doi: str = "",
) -> Item:
    return Item(
        id=item_id,
        source_name="rss",
        source_type="rss",
        source_url=source_url,
        title=title,
        content="body",
        collected_at=collected_at,
        language=language,
        raw_data={"pmid": pmid, "doi": doi},
    )


def _entry(
    *,
    entry_id: str = "existing-1",
    title: str = "",
    source_url: str = "",
    collected_at: str = "2026-08-02T00:00:00Z",
    language: str = "en",
) -> KBEntry:
    return KBEntry(
        entry_id=entry_id,
        title=title,
        domain="ai-commercial",
        source_url=source_url,
        collected_at=collected_at,
        language=language,
    )


def _write_raw(kb_root: Path, domain: str, name: str, content: str | bytes) -> None:
    raw_dir = kb_root / domain / "01-Raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        (raw_dir / name).write_bytes(content)
    else:
        (raw_dir / name).write_text(content, encoding="utf-8")


# ======================================================================
# Fuzzy-title matching
# ======================================================================


class TestFuzzyTitleMatch:
    """Priority 3: char-level near-identical titles."""

    def test_near_identical_titles_are_duplicates(self) -> None:
        checker = DedupChecker()
        item = _item(title="AI Startup raises 50M Series B")
        existing = [_entry(entry_id="fuzzy-1", title="AI Startup raises 50M in Series B")]

        result = checker.check(item, existing)

        assert result["is_duplicate"] is True
        assert result["matched_by"] == "fuzzy_title"
        assert result["existing_id"] == "fuzzy-1"

    def test_dissimilar_titles_are_unique(self) -> None:
        checker = DedupChecker()
        item = _item(title="AI Startup raises 50M Series B")
        existing = [_entry(entry_id="other", title="Central bank holds rates steady")]

        result = checker.check(item, existing)

        assert result["is_duplicate"] is False

    def test_empty_entry_title_skips_fuzzy(self) -> None:
        """A KB entry without a title cannot bear a fuzzy-title signature."""
        checker = DedupChecker()
        item = _item(title="AI Startup raises 50M Series B")
        existing = [_entry(entry_id="no-title", title="")]

        result = checker.check(item, existing)

        assert result["is_duplicate"] is False

    def test_empty_item_title_skips_fuzzy(self) -> None:
        checker = DedupChecker()
        item = _item(title="")
        existing = [_entry(entry_id="titled", title="AI Startup raises 50M Series B")]

        result = checker.check(item, existing)

        assert result["is_duplicate"] is False
        assert result["matched_by"] == ""


# ======================================================================
# Cross-domain event matching (#109)
# ======================================================================


class TestCrossDomainEventMatch:
    """Priority 4: same event, different language/headline → shared proper
    noun + death word + near-dup window signal."""

    def test_spanish_and_english_obituary_merge(self) -> None:
        """``Muere Dolly Parton ...`` (es) vs ``Dolly Parton has died`` (en):
        no URL/DOI/PMID match and low char-level similarity, yet the same
        event.  The Spanish signature is the longer phrase, so the English
        ``Dolly Parton`` is kept via phrase-subsumption."""
        checker = DedupChecker()
        item = _item(
            title="Muere Dolly Parton a los 76 años",
            language="es",
            collected_at="2026-08-01T00:00:00+00:00",
        )
        existing = [
            _entry(
                entry_id="obit-en",
                title="Dolly Parton has died at 76",
                language="en",
                collected_at="2026-08-02T00:00:00Z",
            )
        ]

        result = checker.check(item, existing)

        assert result["is_duplicate"] is True
        assert result["matched_by"] == "cross_domain_event"
        assert result["existing_id"] == "obit-en"

    def test_same_language_rewrite_merges(self) -> None:
        """Direct intersection of the proper-noun signatures (no subsumption
        needed) also merges — headlines far apart in characters but sharing
        ``Dolly Parton`` and a death word."""
        checker = DedupChecker()
        item = _item(title="Dolly Parton dies at 76", language="en")
        existing = [
            _entry(
                entry_id="obit-rewrite",
                title="Dolly Parton has died following a short illness",
                language="en",
            )
        ]

        result = checker.check(item, existing)

        assert result["is_duplicate"] is True
        assert result["matched_by"] == "cross_domain_event"

    def test_outside_window_is_not_duplicate(self) -> None:
        """The same nouns + death words a month apart are different stories."""
        checker = DedupChecker()
        item = _item(
            title="Muere Dolly Parton a los 76 años",
            language="es",
            collected_at="2026-08-01T00:00:00+00:00",
        )
        existing = [
            _entry(
                entry_id="old-obit",
                title="Dolly Parton has died at 76",
                language="en",
                collected_at="2026-09-15T00:00:00Z",
            )
        ]

        result = checker.check(item, existing)

        assert result["is_duplicate"] is False

    def test_unparseable_timestamps_do_not_block_merge(self) -> None:
        """Missing/garbled ``collected_at`` skips the window clause
        (conservative) — the noun + death-word signals still merge."""
        checker = DedupChecker()
        item = _item(
            title="Muere Dolly Parton a los 76 años",
            language="es",
            collected_at="not-a-date",
        )
        existing = [
            _entry(
                entry_id="obit-unknown-date",
                title="Dolly Parton has died at 76",
                language="en",
                collected_at="",
            )
        ]

        result = checker.check(item, existing)

        assert result["is_duplicate"] is True
        assert result["matched_by"] == "cross_domain_event"

    def test_missing_death_word_in_item_is_not_duplicate(self) -> None:
        """Shared noun alone is not enough: a concert announcement is not the
        obituary."""
        checker = DedupChecker()
        item = _item(title="Dolly Parton announces a new tour", language="en")
        existing = [_entry(entry_id="obit", title="Dolly Parton has died", language="en")]

        result = checker.check(item, existing)

        assert result["is_duplicate"] is False

    def test_missing_death_word_in_entry_is_not_duplicate(self) -> None:
        checker = DedupChecker()
        item = _item(title="Dolly Parton has died", language="en")
        existing = [
            _entry(entry_id="album", title="Dolly Parton releases a new album", language="en")
        ]

        result = checker.check(item, existing)

        assert result["is_duplicate"] is False

    def test_no_shared_proper_noun_is_not_duplicate(self) -> None:
        checker = DedupChecker()
        item = _item(title="Muere Dolly Parton a los 76 años", language="es")
        existing = [
            _entry(entry_id="elvis", title="Obituary: Elvis Presley has died", language="en")
        ]

        result = checker.check(item, existing)

        assert result["is_duplicate"] is False

    def test_entry_without_title_is_not_duplicate(self) -> None:
        """``_cross_domain_event_match`` bails on an untitled entry."""
        checker = DedupChecker()
        item = _item(title="Muere Dolly Parton a los 76 años", language="es")
        existing = [_entry(entry_id="untitled", title="", language="en")]

        result = checker.check(item, existing)

        assert result["is_duplicate"] is False

    def test_naive_and_aware_timestamps_compare(self) -> None:
        """One date-only (naive) and one tz-aware timestamp inside the window
        must compare without a naive/aware TypeError."""
        checker = DedupChecker()
        item = _item(
            title="Muere Dolly Parton a los 76 años",
            language="es",
            collected_at="2026-08-01",
        )
        existing = [
            _entry(
                entry_id="aware",
                title="Dolly Parton has died at 76",
                language="en",
                collected_at="2026-08-03T00:00:00Z",
            )
        ]

        result = checker.check(item, existing)

        assert result["is_duplicate"] is True

    def test_phrase_subsumption_both_directions(self) -> None:
        """Short item signature contained in a longer entry signature
        (``Dolly Parton`` ⊂ ``Dolly Parton Tribute Concert``) still merges
        when both titles carry a death word."""
        checker = DedupChecker()
        item = _item(title="Dolly Parton dies at 76", language="en")
        existing = [
            _entry(
                entry_id="tribute",
                title="Dolly Parton Tribute Concert announced after her death",
                language="en",
            )
        ]

        result = checker.check(item, existing)

        assert result["is_duplicate"] is True
        assert result["matched_by"] == "cross_domain_event"


# ======================================================================
# load_all_domains_entries
# ======================================================================


class TestLoadAllDomainsEntries:
    def test_scans_every_domain_and_skips_non_dirs(self, tmp_path: Path) -> None:
        for i, domain in enumerate(("medical-research", "ai-commercial")):
            data = {
                "entry_id": f"kb-{i}",
                "title": f"Entry {i}",
                "domain": domain,
                "tier": "01-Raw",
            }
            _write_raw(tmp_path, domain, f"entry-{i}.md", "---\n" + yaml.dump(data) + "---\n")
        # A stray non-directory under knowledge/ must be ignored.
        (tmp_path / "README.md").write_text("not a domain", encoding="utf-8")

        checker = DedupChecker(knowledge_dir=str(tmp_path))
        entries = checker.load_all_domains_entries()

        assert {e.entry_id for e in entries} == {"kb-0", "kb-1"}
        assert {e.domain for e in entries} == {"medical-research", "ai-commercial"}

    def test_missing_knowledge_dir_returns_empty(self, tmp_path: Path) -> None:
        checker = DedupChecker(knowledge_dir=str(tmp_path / "does-not-exist"))
        assert checker.load_all_domains_entries() == []


# ======================================================================
# _parse_kb_file / load_existing edge cases
# ======================================================================


class TestParseKbFileEdges:
    def test_missing_closing_frontmatter_delimiter(self, tmp_path: Path) -> None:
        _write_raw(tmp_path, "d", "open.md", "---\ntitle: Broken\n")
        checker = DedupChecker(knowledge_dir=str(tmp_path))
        assert checker.load_existing("d") == []

    def test_empty_frontmatter_block(self, tmp_path: Path) -> None:
        _write_raw(tmp_path, "d", "empty.md", "---\n---\n\nbody\n")
        checker = DedupChecker(knowledge_dir=str(tmp_path))
        assert checker.load_existing("d") == []

    def test_invalid_yaml_frontmatter(self, tmp_path: Path) -> None:
        _write_raw(tmp_path, "d", "bad.md", "---\nkey: [unclosed\n---\n\nbody\n")
        checker = DedupChecker(knowledge_dir=str(tmp_path))
        assert checker.load_existing("d") == []

    def test_undecodable_file_is_skipped(self, tmp_path: Path) -> None:
        """A file that cannot be decoded as UTF-8 is logged and skipped, not
        propagated as an error."""
        _write_raw(tmp_path, "d", "binary.md", b"\xff\xfe\x00not utf8")
        checker = DedupChecker(knowledge_dir=str(tmp_path))
        assert checker.load_existing("d") == []


# ======================================================================
# Timestamp helpers
# ======================================================================


class TestTimestampHelpers:
    def test_parse_dt_handles_missing_aware_and_naive(self) -> None:
        assert DedupChecker._parse_dt("") is None
        assert DedupChecker._parse_dt("garbage") is None
        aware = DedupChecker._parse_dt("2026-08-01T00:00:00Z")
        assert aware is not None and aware.tzinfo is not None
        naive = DedupChecker._parse_dt("2026-08-01")
        assert naive is not None and naive.tzinfo is not None

    def test_within_window_truth_table(self) -> None:
        # Same day → inside.
        assert DedupChecker._within_window("2026-08-01T00:00:00Z", "2026-08-03T00:00:00Z") is True
        # Far apart → outside.
        assert DedupChecker._within_window("2026-08-01T00:00:00Z", "2026-08-20T00:00:00Z") is False
        # Unparseable on either side → conservative True.
        assert DedupChecker._within_window("", "2026-08-01T00:00:00Z") is True
        assert DedupChecker._within_window("2026-08-01T00:00:00Z", "nope") is True
