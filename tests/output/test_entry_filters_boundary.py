"""Module-boundary characterization tests for the shared entry-filter kernel [T9].

Locks the CURRENT observable behavior of the deterministic entry-filter block
in :mod:`autoinfo.output` (``_lang_display_name`` .. ``_filter_entries_by_domain_exclusions``,
the T10 ``output/entries.py`` extraction target) BEFORE that extraction.

Boundaries under test
---------------------
* **Public consumers** — ``generate_digest`` / ``generate_report`` over a fixture
  KB whose entries span two languages and include an exclude-keyword entry:
  only the filtered entries reach the LLM synthesis prompt AND the rendered
  body.
* **Deterministic helpers** (stable behavior, no LLM):
  ``_filter_entries_by_language``, ``_filter_entries_by_domain_exclusions``,
  ``_resolve_effective_language``, ``_converge_near_duplicates``,
  ``_filter_digest_entries``.

Per deep-modules-skill the tests exercise the module boundary (public
consumer output, or the deterministic helper's input -> output) rather than
mocking implementation internals.  The seams that are patched are exactly the
ones T7's ``export.py`` extraction preserved as ``autoinfo.output.<name>``
call-time seams (``KBStore`` / ``_call_llm_for_digest`` / ``get_config_path`` /
``date`` / ``datetime``), so the tests keep passing after T10 relocates the
helpers (re-export shim keeps the names importable from ``autoinfo.output``).

Golden byte-identity
--------------------
``tests/fixtures/golden/digest_entries.golden.md`` is a committed render of the
fixture KB.  After T10 the same ``generate_digest`` call must reproduce it
byte-for-byte.

Determinism guard (frozen / normalized fields)
----------------------------------------------
* **Clock** — ``autoinfo.output.date`` is frozen to :data:`FROZEN_TODAY` and
  ``autoinfo.output.datetime`` to :class:`_FrozenDateTime` so the digest's
  ``**Period**: Weekly (date_from – date_to)`` header and the
  ``Generated``/footer date are fixed.
* **Entry ordering** — ``_sorted_ref_entries`` (has-summary desc, relevance
  desc) pins the render order; the fixture gives each entry a distinct
  relevance so the order is total.
* **Freshness** — entries carry ``collected_at = real now - 1 day`` (computed
  at import time, NOT a hardcoded calendar date) so ``calculate_freshness_score``
  (which uses the real clock) always passes.  ``collected_at`` is never
  rendered in the markdown digest (verified: the template renders only period,
  dates, titles, summaries and source URLs), so it cannot affect the golden.
* **Source drift** — the tmp project config declares the fixture
  ``techcrunch`` source, so the selection-time source-drift filter keeps every
  entry (its host matches).
* **No tmp paths / SHAs / version stamps** — the markdown digest embeds none;
  all remaining bytes are fixed literals (titles, summaries, URLs, dates).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

from autoinfo.output import (
    DeliveryOutput,
    _converge_near_duplicates,
    _filter_digest_entries,
    _filter_entries_by_domain_exclusions,
    _filter_entries_by_language,
    _resolve_effective_language,
    generate_digest,
    generate_report,
)

# ---------------------------------------------------------------------------
# Determinism constants
# ---------------------------------------------------------------------------

FROZEN_NOW = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
FROZEN_TODAY = FROZEN_NOW.date()

DOMAIN = "ai-commercial"
DOMAIN_LABEL = "AI Commercial"

# The digest window query is `collected_at >= date_from` (frozen 2026-08-21),
# while freshness is computed against the REAL clock.  A relative "yesterday"
# keeps entries fresh forever and never enters the render.
FRESH_COLLECTED_AT = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

_GOLDEN_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "golden"
_GOLDEN_PATH = _GOLDEN_DIR / "digest_entries.golden.md"


class _FrozenDateTime(datetime):
    """``datetime`` subclass whose ``now()`` returns :data:`FROZEN_NOW`."""

    @classmethod
    def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
        if tz is not None:
            return FROZEN_NOW.astimezone(tz)
        return FROZEN_NOW.replace(tzinfo=None)


class _FrozenDate(date):
    """``date`` subclass whose ``today()`` returns :data:`FROZEN_TODAY`."""

    @classmethod
    def today(cls) -> date:  # type: ignore[override]
        return FROZEN_TODAY


# ---------------------------------------------------------------------------
# Fixture KB + tmp project config
# ---------------------------------------------------------------------------

# The four fixture entries: two English survivors, one zh entry, and one
# English entry carrying an excluded keyword.  Language + exclusion filters
# must drop exactly the latter two.
_FIXTURE_ENTRIES: list[dict[str, Any]] = [
    {
        "entry_id": "en-keep-1",
        "title": "OpenAI ships a new frontier model",
        "summary": "OpenAI released a new model this week.",
        "domain": DOMAIN,
        "tier": "01-Raw",
        "language": "en",
        "source_url": "https://techcrunch.com/en-keep-1",
        "source_type": "rss",
        "source_platform": "techcrunch",
        "collected_at": FRESH_COLLECTED_AT,
        "relevance_score": 90.0,
        "tags": '["AI"]',
        "quality_tier": 1,
        "dedup_status": "unique",
        "file_path": "",
        "custom_fields": "{}",
    },
    {
        "entry_id": "en-keep-2",
        "title": "Anthropic launches enterprise AI agent",
        "summary": "Anthropic launched an enterprise assistant.",
        "domain": DOMAIN,
        "tier": "01-Raw",
        "language": "en",
        "source_url": "https://techcrunch.com/en-keep-2",
        "source_type": "rss",
        "source_platform": "techcrunch",
        "collected_at": FRESH_COLLECTED_AT,
        "relevance_score": 85.0,
        "tags": '["AI"]',
        "quality_tier": 1,
        "dedup_status": "unique",
        "file_path": "",
        "custom_fields": "{}",
    },
    {
        "entry_id": "zh-drop-1",
        "title": "中文 AI 融资报道",
        "summary": "中文摘要内容",
        "domain": DOMAIN,
        "tier": "01-Raw",
        "language": "zh",
        "source_url": "https://techcrunch.com/zh-drop-1",
        "source_type": "rss",
        "source_platform": "techcrunch",
        "collected_at": FRESH_COLLECTED_AT,
        "relevance_score": 88.0,
        "tags": '["AI"]',
        "quality_tier": 1,
        "dedup_status": "unique",
        "file_path": "",
        "custom_fields": "{}",
    },
    {
        "entry_id": "en-excl-1",
        "title": "贝达药业 2026 半年报",
        "summary": "DURAVYU eye-drug phase III trial results.",
        "domain": DOMAIN,
        "tier": "01-Raw",
        "language": "en",
        "source_url": "https://techcrunch.com/en-excl-1",
        "source_type": "rss",
        "source_platform": "techcrunch",
        "collected_at": FRESH_COLLECTED_AT,
        "relevance_score": 80.0,
        "tags": '["AI"]',
        "quality_tier": 1,
        "dedup_status": "unique",
        "file_path": "",
        "custom_fields": "{}",
    },
]

_KEEP_TITLES = (
    "OpenAI ships a new frontier model",
    "Anthropic launches enterprise AI agent",
)
_DROPPED_TITLES = ("中文 AI 融资报道", "贝达药业 2026 半年报")

_EXCLUDE_KEYWORDS = ["贝达药业", "DURAVYU"]

# A minimal VALID project config.  Both filters are declared explicitly so the
# behavior is pinned without leaning on demo-domain seed files:
#   * ``default_language: en`` -> generate_digest/report resolve "en" itself.
#   * ``exclude_keywords`` -> _get_domain_exclude_keywords returns them.
#   * ``min_product_relevance: 0`` -> relevance floor disabled (explicit).
#   * ``sources: techcrunch`` -> source-drift filter keeps the fixture host.
_PROJECT_CONFIG: dict[str, Any] = {
    "project": {"name": "Entry Filter Boundary Test", "created_at": "2026-07-01"},
    "llm": {
        "provider": "openai",
        "model": "deepseek-v4-flash",
        "api_key": "test-key",
    },
    "domains": [
        {
            "name": DOMAIN,
            "active": True,
            "default_language": "en",
            "exclude_keywords": list(_EXCLUDE_KEYWORDS),
            "min_product_relevance": 0,
            "sources": [
                {
                    "name": "techcrunch",
                    "type": "rss",
                    "url": "https://techcrunch.com/feed/",
                    "quality_tier": 1,
                    "tos_classification": "open",
                }
            ],
            "topics": [],
        }
    ],
}


def _write_project(root: Path) -> Path:
    """Write the tmp ``.autoinfo/config.yaml`` and return its path."""
    config_dir = root / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(_PROJECT_CONFIG, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return config_path


class _FixtureStore:
    """A deterministic KB stand-in honoring the ``date_from``/``date_to`` window.

    Mirrors ``KBStore.list_entries`` filtering semantics so ``_select_story_set``
    sees the same shape a real KB store would return, without touching SQLite.
    """

    def __init__(self, entries: list[dict[str, Any]]) -> None:
        self._entries = list(entries)

    def list_entries(
        self,
        domain: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        del domain, offset
        result = list(self._entries)
        if date_from:
            result = [
                e
                for e in result
                if str(e.get("collected_at") or "") >= date_from
            ]
        if date_to:
            result = [
                e
                for e in result
                if str(e.get("collected_at") or "") <= date_to
            ]
        return result[:limit]

    def list_kb_tier(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    def promote_kb_draft(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {}

    def flag_for_knowledge_base(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {}


def _canned_digest_llm(prompt: str, config: Any = None) -> dict[str, Any]:
    """Canned LLM synthesis (no network) — the digest render is template-driven."""
    del prompt, config
    return {
        "executive_summary": "Two AI stories this period.",
        "key_findings": [],
        "recommendations": [],
    }


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Freeze ``autoinfo.output.date``/``datetime`` for a reproducible render."""
    import autoinfo.output as output_mod

    monkeypatch.setattr(output_mod, "date", _FrozenDate)
    monkeypatch.setattr(output_mod, "datetime", _FrozenDateTime)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A tmp project (``.autoinfo/config.yaml``) with both filters declared."""
    _write_project(tmp_path)
    return tmp_path


def _as_text(result: str | DeliveryOutput) -> str:
    if isinstance(result, DeliveryOutput):
        return result.output
    return str(result)


# ===========================================================================
# Public consumer: generate_digest
# ===========================================================================


class TestDigestEntryFiltersBoundary:
    def test_digest_keeps_only_filtered_entries_in_prompt_and_body(
        self, project: Path, frozen_clock: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Language (config ``default_language: en``) + exclude_keywords drop
        exactly the zh and noise entries BEFORE synthesis and render."""
        monkeypatch.chdir(project)
        captured: dict[str, str] = {}

        def _capture(prompt: str, config: Any = None) -> dict[str, Any]:
            captured["prompt"] = prompt
            return _canned_digest_llm(prompt, config)

        with (
            patch(
                "autoinfo.output.KBStore",
                return_value=_FixtureStore(_FIXTURE_ENTRIES),
            ),
            patch("autoinfo.output._call_llm_for_digest", side_effect=_capture),
        ):
            body = _as_text(
                generate_digest(domain=DOMAIN, period="weekly", format="markdown")
            )

        for title in _KEEP_TITLES:
            assert title in body, f"kept entry missing from body: {title!r}"
            assert title in captured["prompt"], f"kept entry missing from prompt: {title!r}"
        for title in _DROPPED_TITLES:
            assert title not in body, f"filtered entry leaked into body: {title!r}"
            assert title not in captured["prompt"], (
                f"filtered entry leaked into prompt: {title!r}"
            )

    def test_explicit_language_param_wins_over_config_default(
        self, project: Path, frozen_clock: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An explicit ``language=`` overrides the config default (precedence)."""
        monkeypatch.chdir(project)
        # 3 zh entries (> collapse guard) so the safety net does NOT relax the
        # filter; the explicit "zh" keeps them and drops the en ones.
        zh_entries = [
            {**_FIXTURE_ENTRIES[0], "entry_id": f"zh-{i}", "language": "zh",
             "title": f"中文条目 {i}", "summary": f"中文摘要 {i}",
             "relevance_score": 90.0 - i}
            for i in range(3)
        ]
        entries = zh_entries + [_FIXTURE_ENTRIES[0]]
        with (
            patch("autoinfo.output.KBStore", return_value=_FixtureStore(entries)),
            patch(
                "autoinfo.output._call_llm_for_digest",
                side_effect=_canned_digest_llm,
            ),
        ):
            body = _as_text(
                generate_digest(
                    domain=DOMAIN, period="weekly", format="markdown", language="zh"
                )
            )
        assert "中文条目 0" in body
        assert "OpenAI ships a new frontier model" not in body


# ===========================================================================
# Public consumer: generate_report
# ===========================================================================


class TestReportEntryFiltersBoundary:
    def test_report_keeps_only_filtered_entries(
        self, project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The report consumes the same language + exclude filters as the digest."""
        monkeypatch.chdir(project)
        with (
            patch(
                "autoinfo.output.KBStore",
                return_value=_FixtureStore(_FIXTURE_ENTRIES),
            ),
            patch("autoinfo.output._group_by_theme", return_value=[]),
            patch(
                "autoinfo.output._generate_executive_summary",
                return_value="Overview.",
            ),
        ):
            body = _as_text(
                generate_report(domain=DOMAIN, period="weekly", format="markdown")
            )

        for title in _KEEP_TITLES:
            assert title in body, f"kept entry missing from report: {title!r}"
        for title in _DROPPED_TITLES:
            assert title not in body, f"filtered entry leaked into report: {title!r}"


# ===========================================================================
# Deterministic helper: _resolve_effective_language
# ===========================================================================


class TestResolveEffectiveLanguage:
    def test_explicit_language_wins_over_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        assert _resolve_effective_language("fr", DOMAIN) == "fr"

    def test_config_declared_default_language_is_used(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        assert _resolve_effective_language("", DOMAIN) == "en"

    def test_cross_domain_never_picks_a_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        assert _resolve_effective_language("", DOMAIN, cross_domain=True) == ""

    def test_no_config_file_returns_empty(self) -> None:
        with patch("autoinfo.output.get_config_path", return_value=None):
            assert _resolve_effective_language("", DOMAIN) == ""

    def test_unknown_domain_with_config_returns_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        assert _resolve_effective_language("", "no-such-domain") == ""


# ===========================================================================
# Deterministic helper: _filter_entries_by_language
# ===========================================================================


class TestFilterEntriesByLanguage:
    @staticmethod
    def _entry(eid: str, lang: str) -> dict[str, Any]:
        return {"entry_id": eid, "language": lang, "title": f"item-{eid}"}

    def test_empty_language_returns_input_unchanged(self) -> None:
        entries = [self._entry("a", "zh"), self._entry("b", "en")]
        assert _filter_entries_by_language(entries, "") is entries

    def test_filters_to_matching_language_with_aliases(self) -> None:
        entries = [
            self._entry("zh", "zh"),
            self._entry("zh-cn", "zh-cn"),
            self._entry("en", "en"),
            self._entry("ja", "ja"),
        ]
        kept = _filter_entries_by_language(entries, "zh")
        assert [e["entry_id"] for e in kept] == ["zh", "zh-cn"]

    def test_empty_or_unknown_language_dropped_when_filter_active(self) -> None:
        entries = [
            self._entry("empty", ""),
            {"entry_id": "none", "language": None, "title": "none"},
            self._entry("en", "en"),
        ]
        kept = _filter_entries_by_language(entries, "en")
        assert [e["entry_id"] for e in kept] == ["en"]

    def test_collapse_guard_relaxes_a_stale_language(self) -> None:
        """5 en entries filtered by a stale 'zh' collapse -> full input back."""
        entries = [self._entry(f"en-{i}", "en") for i in range(5)]
        from autoinfo.output import _filter_entries_by_language_product_safe

        kept, collapsed = _filter_entries_by_language_product_safe(entries, "zh")
        assert collapsed is True
        assert kept == entries


# ===========================================================================
# Deterministic helper: _filter_entries_by_domain_exclusions
# ===========================================================================


class TestFilterEntriesByDomainExclusions:
    @staticmethod
    def _entry(eid: str, title: str, summary: str = "content", tags: Any = "[]") -> dict[str, Any]:
        return {
            "entry_id": eid,
            "title": title,
            "summary": summary,
            "domain": DOMAIN,
            "language": "en",
            "tags": tags,
            "relevance_score": 85.0,
        }

    def test_exclude_keyword_substring_drops_matching_entries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The tmp config declares the blacklist; matching is deterministic.

        The tmp project is the ACTIVE cwd (``get_config_path`` resolves
        ``$PWD/.autoinfo/config.yaml``), so no package-internal patch target is
        relied on — the test survives the helper relocating to ``entries.py``.
        """
        _write_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        entries = [
            self._entry("noise-cjk", "贝达药业 2026 半年报"),
            self._entry("noise-drug", "EyePoint phase III", summary="DURAVYU trial"),
            self._entry("keep", "AI startup raises series A"),
        ]
        kept = _filter_entries_by_domain_exclusions(entries, DOMAIN)
        assert [e["entry_id"] for e in kept] == ["keep"]

    def test_explicit_empty_blacklist_is_a_noop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cfg = _write_project(tmp_path)
        raw = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        raw["domains"][0]["exclude_keywords"] = []
        cfg.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
                       encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        entries = [
            self._entry("noise-cjk", "贝达药业 2026 半年报"),
            self._entry("keep", "AI startup raises series A"),
        ]
        kept = _filter_entries_by_domain_exclusions(entries, DOMAIN)
        assert kept == entries

    def test_keyword_match_in_tags(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        entries = [
            self._entry("tagged", "Phase III readout", tags='["DURAVYU"]'),
            self._entry("keep", "New model release", tags='["LLM"]'),
        ]
        kept = _filter_entries_by_domain_exclusions(entries, DOMAIN)
        assert [e["entry_id"] for e in kept] == ["keep"]


# ===========================================================================
# Deterministic helper: _converge_near_duplicates
# ===========================================================================


class TestConvergeNearDuplicates:
    @staticmethod
    def _entry(
        eid: str,
        title: str,
        url: str,
        *,
        lang: str = "en",
        dedup_status: str = "duplicate",
        relevance: float = 50.0,
        collected_at: str = "2026-08-25T12:00:00",
    ) -> dict[str, Any]:
        return {
            "entry_id": eid,
            "title": title,
            "source_url": url,
            "language": lang,
            "dedup_status": dedup_status,
            "relevance_score": relevance,
            "collected_at": collected_at,
            "tags": "[]",
        }

    def test_cross_language_same_event_converges_to_one(self) -> None:
        entries = [
            self._entry("en", "Dolly Parton has died", "https://example.com/en",
                        lang="en", relevance=90.0),
            self._entry("fr", "Mort de la star américaine Dolly Parton",
                        "https://example.com/fr", lang="fr", relevance=60.0),
        ]
        result = _converge_near_duplicates(entries)
        assert len(result) == 1
        assert result[0]["entry_id"] == "en"  # highest relevance representative

    def test_identical_source_url_never_merged(self) -> None:
        entries = [
            self._entry("a", "Dolly Parton has died", "https://example.com/same"),
            self._entry("b", "Dolly Parton est décédée", "https://example.com/same"),
        ]
        assert len(_converge_near_duplicates(entries)) == 2

    def test_unrelated_same_noun_stories_not_merged(self) -> None:
        entries = [
            self._entry("tokyo", "Donald Trump visits Tokyo",
                        "https://example.com/1", dedup_status="unique"),
            self._entry("indict", "Donald Trump indicted by prosecutors",
                        "https://example.com/2", dedup_status="unique"),
        ]
        assert len(_converge_near_duplicates(entries)) == 2


# ===========================================================================
# Deterministic helper: _filter_digest_entries
# ===========================================================================


class TestFilterDigestEntries:
    @staticmethod
    def _entry(
        eid: str,
        title: str,
        *,
        status: str | None = None,
        url: str | None = None,
        dedup_status: str = "unique",
        relevance: float = 50.0,
        lang: str = "en",
    ) -> dict[str, Any]:
        import json as _json

        return {
            "entry_id": eid,
            "title": title,
            "summary": f"summary for {eid}",
            "domain": "medical-research",
            "tier": "01-Raw",
            "language": lang,
            "source_url": url or f"https://example.com/{eid}",
            "source_type": "rss",
            "source_platform": "pubmed",
            "collected_at": "2026-08-25T12:00:00",
            "relevance_score": relevance,
            "tags": "[]",
            "quality_tier": 1,
            "dedup_status": dedup_status,
            "custom_fields": _json.dumps({"status": status}) if status else "{}",
        }

    def test_archived_test_and_near_dup_entries_are_dropped(self) -> None:
        entries = [
            self._entry("archived", "Archived story", status="archived"),
            self._entry("test", "Entry A"),  # test-title marker
            self._entry("dup-en", "Dolly Parton has died",
                        url="https://example.com/a", dedup_status="duplicate",
                        relevance=90.0),
            self._entry("dup-fr", "Mort de la star américaine Dolly Parton",
                        url="https://example.com/b", dedup_status="duplicate",
                        relevance=60.0, lang="fr"),
            self._entry("keep", "A real medical breakthrough", relevance=95.0),
        ]
        result = _filter_digest_entries(entries)
        ids = {e["entry_id"] for e in result}
        assert "archived" not in ids
        assert "test" not in ids
        # The two same-event duplicates converge to exactly one representative.
        assert len({"dup-en", "dup-fr"} & ids) == 1
        assert "keep" in ids

    def test_empty_input_returns_empty(self) -> None:
        assert _filter_digest_entries([]) == []


# ===========================================================================
# Golden byte-identity
# ===========================================================================


class TestGoldenDigest:
    def test_golden_exists_under_committed_fixtures(self) -> None:
        # Guard against goldens drifting back into a gitignored location.
        assert _GOLDEN_PATH.is_file()
        assert "tests/fixtures/golden" in str(_GOLDEN_PATH)

    def test_digest_byte_identical_to_golden(
        self, project: Path, frozen_clock: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        golden = _GOLDEN_PATH.read_text(encoding="utf-8")
        monkeypatch.chdir(project)
        with (
            patch(
                "autoinfo.output.KBStore",
                return_value=_FixtureStore(_FIXTURE_ENTRIES),
            ),
            patch("autoinfo.output._call_llm_for_digest", side_effect=_canned_digest_llm),
        ):
            body = generate_digest(domain=DOMAIN, period="weekly", format="markdown")
        assert isinstance(body, str)
        assert body == golden


# ---------------------------------------------------------------------------
# Golden capture entry point (regenerate ONLY when current behavior changes)
# ---------------------------------------------------------------------------


def _render_golden(project_dir: Path) -> str:
    """Render the fixture digest under the frozen clock, outside pytest."""
    import autoinfo.output as output_mod

    orig_date = output_mod.date
    orig_datetime = output_mod.datetime
    try:
        output_mod.date = _FrozenDate  # type: ignore[assignment]
        output_mod.datetime = _FrozenDateTime  # type: ignore[assignment]
        with (
            patch("autoinfo.output.KBStore", return_value=_FixtureStore(_FIXTURE_ENTRIES)),
            patch("autoinfo.output._call_llm_for_digest", side_effect=_canned_digest_llm),
        ):
            result = generate_digest(domain=DOMAIN, period="weekly", format="markdown")
    finally:
        output_mod.date = orig_date  # type: ignore[assignment]
        output_mod.datetime = orig_datetime  # type: ignore[assignment]
    return result if isinstance(result, str) else result.output


def _capture_goldens() -> None:
    """Regenerate the committed golden from the CURRENT source."""
    import os
    import tempfile

    _GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_project(root)
        cwd = os.getcwd()
        os.chdir(root)
        try:
            golden = _render_golden(root)
        finally:
            os.chdir(cwd)
        _GOLDEN_PATH.write_text(golden, encoding="utf-8")
    print(f"wrote {_GOLDEN_PATH}")


if __name__ == "__main__":
    _capture_goldens()
