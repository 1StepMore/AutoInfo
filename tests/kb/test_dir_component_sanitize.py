"""Windows path-component sanitization for KB topic directories (issue #862).

A colon-bearing topic tag ("3.6:1 ratio") is a valid directory name on Linux
but invalid on Windows — ``process`` dropped the item there with
``[WinError 267]``.  The fix sanitizes every KB directory component derived
from raw metadata (store_entry + the 02-Draft writer) deterministically;
identity stays fingerprint-based (#695) so dedup/idempotency is unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autoinfo.kb import KBStore, _sanitize_dir_component
from autoinfo.models import Item


def _make_item(topic_tags: list[str]) -> Item:
    return Item(
        id="item-colon-topic",
        source_name="rss",
        source_type="rss",
        source_platform="rss",
        source_url="https://example.org/colon-topic/1",
        title="A Case Report Series on Supplementation with 1100 mg Myo-Inositol",
        content="Body text long enough to satisfy any content guard in this suite.",
        content_type="text",
        collected_at="2026-11-21T08:00:00Z",
        language="en",
        domain="medical-research",
        topic_tags=topic_tags,
        quality_tier=1,
    )


@pytest.mark.parametrize(
    "forbidden",
    ["<", ">", ":", '"', "/", "\\", "|", "?", "*", "\x01"],
)
def test_forbidden_characters_become_spaces(forbidden: str) -> None:
    cleaned = _sanitize_dir_component(f"3.6{forbidden}1 ratio")
    for ch in ("<", ">", ":", '"', "/", "\\", "|", "?", "*"):
        assert ch not in cleaned
    assert "\x01" not in cleaned


def test_forbidden_run_collapses_to_single_space() -> None:
    assert _sanitize_dir_component("a<>b:c") == "a b c"


def test_leading_trailing_dots_and_spaces_trimmed() -> None:
    assert _sanitize_dir_component("  ..name..  ") == "name"


def test_reserved_device_names_get_underscore_prefix() -> None:
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    for name in ("CON", "con", "Nul", "COM1", "lpt3"):
        cleaned = _sanitize_dir_component(name)
        assert cleaned.upper() not in reserved


def test_empty_or_forbidden_only_falls_back() -> None:
    assert _sanitize_dir_component("") == "topic"
    assert _sanitize_dir_component("///") == "topic"
    assert _sanitize_dir_component(":::") == "topic"


def test_deterministic_same_input_same_directory() -> None:
    assert _sanitize_dir_component("3.6:1 ratio") == _sanitize_dir_component("3.6:1 ratio")
    assert _sanitize_dir_component("3.6:1 ratio") == "3.6 1 ratio"


def test_store_entry_writes_sanitized_topic_dir(tmp_path: Path) -> None:
    """Real Windows repro: a colon-bearing topic tag must not raise WinError
    267 and must land in the sanitized directory (this suite runs on Windows
    CI too — the assertion holds on Linux by construction)."""
    item = _make_item(topic_tags=["3.6:1 ratio"])
    store = KBStore(base_path=tmp_path / "knowledge", min_content_chars=0)
    entry = store.store_entry(item)

    topic_dir = Path(entry.file_path).parent
    assert ":" not in topic_dir.name
    assert topic_dir.name == "3.6 1 ratio"
    assert topic_dir.exists()


def test_draft_writer_reuses_sanitized_topic_dir(tmp_path: Path) -> None:
    """The 02-Draft writer derives its topic from existing raw-file paths;
    a Windows-invalid topic dir upstream must not propagate into drafts."""
    from autoinfo.kb import KBStore

    item = _make_item(topic_tags=["ratio 3:1"])
    store = KBStore(base_path=tmp_path / "knowledge", min_content_chars=0)
    entry = store.store_entry(item)

    draft = store.create_kb_draft(
        raw_ids=[entry.entry_id],
        title="Draft from colon-bearing topic",
        summary="Summary body long enough for any draft guard.",
    )

    assert ":" not in Path(draft.file_path).parent.name
    assert Path(draft.file_path).exists()
