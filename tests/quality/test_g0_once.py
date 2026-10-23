"""G0 runs exactly once per item on both the normal and blocked paths (#583)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from autoinfo.kb import KBStore
from autoinfo.llm import LLMExtractor
from autoinfo.models import ExtractionResult, Item, KBEntry
from autoinfo.process import run_processing
from autoinfo.quality import G0SchemaIntegrity


def _item(item_id: str, source_url: str) -> Item:
    return Item(
        id=item_id,
        source_name="pubmed",
        source_type="api",
        source_platform="pubmed",
        source_url=source_url,
        title=f"Article {item_id} about IVF",
        content="IVF outcomes improved with time-lapse imaging.",
        content_type="text",
        collected_at="2026-07-15T10:00:00Z",
        language="en",
        domain="medical-research",
        quality_tier=1,
    )


def run_pipeline_with_counted_g0(path: str, tmp_path: Path | None = None) -> int:
    """Run the real ``run_processing`` path and return G0 invocation count."""
    cwd = tmp_path or Path.cwd()
    item = _item("g0-once", "" if path == "blocked" else "https://example.com/a")

    extraction = ExtractionResult(
        item_id=item.id,
        title=item.title,
        tl_dr="IVF outcomes improved.",
        key_points=["time-lapse imaging"],
        entities=[{"name": "IVF", "type": "procedure"}],
        relevance_score=85.0,
    )
    store = MagicMock(spec=KBStore)
    store.store_entry.return_value = KBEntry(entry_id="e1", title="t", domain="medical-research")
    store.list_entries.return_value = []

    calls = {"n": 0}
    original = G0SchemaIntegrity.check

    def _counting(self: G0SchemaIntegrity, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return original(self, *args, **kwargs)

    previous = os.getcwd()
    os.chdir(cwd)
    try:
        with (
            patch("autoinfo.process.load_cached_items", return_value=[item]),
            patch.object(LLMExtractor, "extract", return_value=extraction),
            patch("autoinfo.process.KBStore", return_value=store),
            patch.object(G0SchemaIntegrity, "check", _counting),
        ):
            run_processing("medical-research")
    finally:
        os.chdir(previous)
    return calls["n"]
