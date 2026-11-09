"""Filename byte-budget acceptance for KB writes (issue #725).

The nightly run failed item 42978393 with ``[Errno 36] File name too long``:
``_slugify`` truncated by characters with a 255-char budget while the file
name is ``{date}-{slug}-{hash8}.md`` — the prefix/suffix overhead pushed the
total past the ext4 255-**byte** limit.  The issue's acceptance asks for a
300-char ASCII title and a 120-char CJK title to both write successfully
with file names ≤ 255 bytes.  Uniqueness of the truncated slug comes from
the ``-{hash8}`` source fingerprint appended by every caller (#695).
"""

from __future__ import annotations

from pathlib import Path

from autoinfo.kb import KBStore, _slugify
from autoinfo.models import Item

# ext4 per-file-name limit
EXT4_MAX_BYTES = 255


def _make_item(item_id: str, source_url: str, title: str) -> Item:
    return Item(
        id=item_id,
        source_name="rss",
        source_type="rss",
        source_platform="rss",
        source_url=source_url,
        title=title,
        content="Body text long enough to satisfy any content guard in this suite.",
        content_type="text",
        collected_at="2026-11-04T08:00:00Z",
        language="en",
        domain="medical-research",
        topic_tags=[],
        quality_tier=1,
    )


class TestSlugifyBytes:
    def test_ascii_truncation_within_byte_budget(self) -> None:
        long_title = "gay fathers triplet children " * 15  # > 400 chars, ASCII
        slug = _slugify(long_title, 100)
        assert len(slug.encode("utf-8")) <= 100

    def test_max_bytes_is_byte_not_char_semantics(self) -> None:
        # Pure-ASCII slug: bytes == chars, truncation point identical.
        assert _slugify("a" * 300, 100) == "a" * 100

    def test_output_is_ascii_alnum_and_hyphens(self) -> None:
        slug = _slugify("Mélange — café; naïve 東京 trivia", 255)
        assert slug == "m-lange-caf-na-ve-trivia"
        assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in slug)


class TestStoreEntryFilenameBudget:
    def test_300_char_ascii_title_writes_within_ext4_limit(self, tmp_path: Path) -> None:
        store = KBStore(base_path=tmp_path / "knowledge", min_content_chars=0)
        title = (
            "Comprehensive longitudinal analysis of assisted reproduction outcomes "
            "across multicenter cohorts with extended follow-up and stratified "
            "subgroup interpretations for clinical practice guidelines and beyond "
        ) * 2
        assert len(title) >= 300
        item = _make_item("item-long-ascii", "https://example.org/a/1", title)

        entry = store.store_entry(item)

        fp = Path(entry.file_path)
        assert fp.exists()
        assert len(fp.name.encode("utf-8")) <= EXT4_MAX_BYTES, fp.name

    def test_120_char_cjk_title_writes_within_ext4_limit(self, tmp_path: Path) -> None:
        store = KBStore(base_path=tmp_path / "knowledge", min_content_chars=0)
        title = (
            "法国假警报案件：巴黎检察院就连环炸弹威胁展开调查并呼吁公众保持冷静配合执法部门工作" * 3
        )
        assert len(title) >= 120
        item = _make_item("item-long-cjk", "https://example.org/a/2", title)

        entry = store.store_entry(item)

        fp = Path(entry.file_path)
        assert fp.exists()
        assert len(fp.name.encode("utf-8")) <= EXT4_MAX_BYTES, fp.name

    def test_long_titles_stay_idempotent_across_reingest(self, tmp_path: Path) -> None:
        store = KBStore(base_path=tmp_path / "knowledge", min_content_chars=0)
        title = "a" * 300
        item = _make_item("item-long", "https://example.org/a/3", title)

        first = store.store_entry(item)
        second = store.store_entry(_make_item("item-long", "https://example.org/a/3", title))

        assert first.file_path == second.file_path


class TestCreateDraftFilenameBudget:
    def test_long_draft_title_writes_within_ext4_limit(self, tmp_path: Path) -> None:
        store = KBStore(base_path=tmp_path / "knowledge", min_content_chars=0)
        title = (
            "Comprehensive longitudinal analysis of assisted reproduction outcomes "
            "across multicenter cohorts with extended follow-up and stratified "
            "subgroup interpretations for clinical practice guidelines and beyond "
        ) * 2
        raw = store.store_entry(_make_item("item-raw", "https://example.org/a/4", "seed"))

        draft = store.create_kb_draft([raw.entry_id], title, summary="s")

        fp = Path(draft.file_path)
        assert fp.exists()
        assert len(fp.name.encode("utf-8")) <= EXT4_MAX_BYTES, fp.name
