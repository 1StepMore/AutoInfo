"""Tests for the Director backdoor (T5 — plan kb-curation-gap-closure).

Covers the KBStore-level director-only operations and the 03-Wiki delete
guard:

  1. Force-promote bypass — a draft that WOULD fail the admission gate
     (incomplete provenance / zero scores) force-promotes with a director
     actor: tier 03-Wiki, frontmatter ``promotion_source: director``.
  2. Demote preserves content — a promoted Wiki entry demotes back to
     02-Draft with body/summary intact and a ``demoted_at`` marker.
  3. Soft-delete guard on 03-Wiki — non-director actors are refused with
     ``DirectorOnlyError``; directors (and the default no-actor path) may
     soft-delete Wiki entries.
  4. Purge (hard-delete) guard on 03-Wiki — non-director refused, director
     allowed; 01-Raw/02-Draft deletion is unchanged for ALL actors.
  5. ``AUTOINFO_DIRECTOR_ACTORS`` whitelist — ``is_director`` honors the
     env var; the default actor ``"director"`` is whitelisted by default.

G4 is an LLM call; tests that use the normal (gated) promotion path
monkeypatch ``autoinfo.promotion.G4FactualConsistency`` with a fake
checker.  Force-promote skips the gate, so those tests need no patch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from autoinfo.kb import DirectorOnlyError, KBStore, PromotionRejected, is_director
from autoinfo.models import Item, KBEntry
from autoinfo.quality import QualityResult

# ===================================================================
# Fixtures / builders
# ===================================================================


@pytest.fixture
def store(tmp_path: Path) -> KBStore:
    """A KBStore rooted in a fresh temp directory."""
    return KBStore(base_path=tmp_path / "knowledge")


def make_scored_raw(
    store: KBStore,
    *,
    source_url: str = "https://example.com/paper1",
    source_platform: str = "pubmed",
    g1_score: float = 72.0,
    g3_score: float = 85.0,
    with_quality_results: bool = True,
) -> KBEntry:
    """Store a 01-Raw entry with full provenance and (optionally) real
    G1/G3 gate scores, mirroring ``test_promotion.make_scored_raw``."""
    item = Item(
        id="raw-001",
        source_name="pubmed",
        source_type="api",
        source_url=source_url,
        source_platform=source_platform,
        title="Raw source paper",
        content=(
            "Time-lapse embryo imaging has been proposed as a non-invasive "
            "method to improve embryo selection in IVF cycles."
        ),
        content_type="text",
        collected_at="2026-07-15T10:30:00Z",
        language="en",
        domain="medical-research",
        topic_tags=["IVF"],
        quality_tier=2,
    )
    if not with_quality_results:
        return store.store_entry(item)
    g3 = QualityResult(
        gate_name="G3-RelevanceScoring", passed=True, score=g3_score
    )
    g1 = QualityResult(
        gate_name="G1-SourceAuthority",
        passed=True,
        score=0.0,
        details={"source_score": g1_score},
    )
    return store.store_entry(
        item,
        quality_results={
            "G3-RelevanceScoring": g3,
            "G1-SourceAuthority": g1,
        },
    )


def patch_g4(
    monkeypatch: pytest.MonkeyPatch,
    passed: bool,
) -> list[tuple[object, object]]:
    """Monkeypatch the module-level G4 class; returns the recorded calls."""
    result = QualityResult(
        gate_name="G4-SummaryFactual",
        passed=passed,
        score=1.0 if passed else 0.0,
        flagged=not passed,
        details={"contradiction": not passed},
    )
    calls: list[tuple[object, object]] = []

    class _FakeG4:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def check(
            self,
            item: object,
            extraction: object,
            gate_config: object | None = None,
        ) -> QualityResult:
            calls.append((item, extraction))
            return result

    monkeypatch.setattr(
        "autoinfo.promotion.G4FactualConsistency",
        _FakeG4,
    )
    return calls


def read_frontmatter(path: Path) -> dict[str, object]:
    """Parse the YAML frontmatter of a KB Markdown file."""
    raw = path.read_text(encoding="utf-8")
    assert raw.startswith("---")
    end = raw.find("---", 3)
    assert end != -1
    fm = yaml.safe_load(raw[3:end])
    assert isinstance(fm, dict)
    return fm


def body_of(path: Path) -> str:
    """Return the body text after the YAML frontmatter."""
    raw = path.read_text(encoding="utf-8")
    end = raw.find("---", 3)
    return raw[end + 3 :].lstrip("\n")


def promote_valid_draft(
    store: KBStore,
    monkeypatch: pytest.MonkeyPatch,
    title: str = "Admission pass draft",
) -> tuple[dict[str, Any], Path]:
    """Create a fully-eligible draft and promote it via the gated path.

    Returns the promotion result dict and the promoted Wiki file path.
    """
    patch_g4(monkeypatch, passed=True)
    raw = make_scored_raw(store)
    draft = store.create_kb_draft(
        raw_ids=[raw.entry_id],
        title=title,
        summary="Time-lapse embryo imaging improves IVF selection.",
    )
    result = store.promote_kb_draft(draft_id=draft.entry_id)
    return result, Path(result["new_path"])


def force_to_wiki(store: KBStore, title: str) -> KBEntry:
    """Create a draft and force-promote it (director) to 03-Wiki."""
    raw = make_scored_raw(store)
    draft = store.create_kb_draft(raw_ids=[raw.entry_id], title=title)
    store.force_promote_kb_draft(draft_id=draft.entry_id, caller="director")
    return draft


# ===================================================================
# 1. Force-promote bypass
# ===================================================================


class TestForcePromoteBypass:
    def test_force_promote_bypasses_admission_gate(self, store: KBStore) -> None:
        """A draft that fails admission (incomplete provenance) still
        force-promotes with a director: tier 03-Wiki, promotion_source=director."""
        raw = make_scored_raw(store, source_url="")  # provenance incomplete
        draft = store.create_kb_draft(
            raw_ids=[raw.entry_id],
            title="Bypass draft",
            summary="Draft with incomplete provenance",
        )

        # Prove the normal gated path rejects this draft...
        with pytest.raises(PromotionRejected):
            store.promote_kb_draft(draft_id=draft.entry_id)

        # ...then the director bypass succeeds.
        result = store.force_promote_kb_draft(draft_id=draft.entry_id, caller="director")
        assert result["status"] == "promoted"
        new_path = Path(result["new_path"])
        assert "03-Wiki" in new_path.parts

        fm = read_frontmatter(new_path)
        assert fm["promotion_source"] == "director"
        assert fm["promoted_by"] == "director"
        assert "promoted_at" in fm

        meta = store.index.get_entry(draft.entry_id)
        assert meta is not None
        assert meta["tier"] == "03-Wiki"

    def test_force_promote_bypasses_zero_scores(self, store: KBStore) -> None:
        """Zero G1/G3 scores (gate would reject) do not block the director."""
        raw = make_scored_raw(store, with_quality_results=False)
        draft = store.create_kb_draft(raw_ids=[raw.entry_id], title="Zero score draft")

        with pytest.raises(PromotionRejected):
            store.promote_kb_draft(draft_id=draft.entry_id)

        result = store.force_promote_kb_draft(draft_id=draft.entry_id, caller="director")
        assert result["status"] == "promoted"
        meta = store.index.get_entry(draft.entry_id)
        assert meta is not None and meta["tier"] == "03-Wiki"

    def test_force_promote_records_caller(
        self, store: KBStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``caller`` lands in promoted_by; promotion_source stays director."""
        monkeypatch.setenv("AUTOINFO_DIRECTOR_ACTORS", "director,director-alice")
        raw = make_scored_raw(store)
        draft = store.create_kb_draft(raw_ids=[raw.entry_id], title="Caller draft")

        result = store.force_promote_kb_draft(
            draft_id=draft.entry_id, caller="director-alice"
        )
        fm = read_frontmatter(Path(result["new_path"]))
        assert fm["promotion_source"] == "director"
        assert fm["promoted_by"] == "director-alice"

    def test_force_promote_refused_for_non_director(self, store: KBStore) -> None:
        """A non-whitelisted actor gets a typed DirectorOnlyError."""
        raw = make_scored_raw(store)
        draft = store.create_kb_draft(raw_ids=[raw.entry_id], title="Refused draft")

        with pytest.raises(DirectorOnlyError) as exc_info:
            store.force_promote_kb_draft(draft_id=draft.entry_id, caller="agent")
        assert exc_info.value.operation == "force-promote"
        # Draft untouched
        meta = store.index.get_entry(draft.entry_id)
        assert meta is not None and meta["tier"] == "02-Draft"
        assert Path(draft.file_path).is_file()

    def test_force_promote_requires_draft_tier(self, store: KBStore) -> None:
        """Force-promoting a non-Draft entry errors like the gated path."""
        raw = make_scored_raw(store)
        with pytest.raises(ValueError, match="not a Draft"):
            store.force_promote_kb_draft(draft_id=raw.entry_id, caller="director")

    def test_force_promote_not_found(self, store: KBStore) -> None:
        with pytest.raises(ValueError, match="not found"):
            store.force_promote_kb_draft(draft_id="ghost-draft", caller="director")


# ===================================================================
# 2. Demote preserves content
# ===================================================================


class TestDemoteEntry:
    def test_demote_preserves_content_and_marks(
        self, store: KBStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Demoting a promoted Wiki entry keeps the body, moves it back to
        02-Draft, appends ``demoted_at``, and keeps promotion provenance."""
        promote_result, wiki_path = promote_valid_draft(store, monkeypatch)
        body_before = body_of(wiki_path)

        demote_result = store.demote_entry(promote_result["draft_id"], caller="director")

        assert demote_result["status"] == "demoted"
        new_path = Path(demote_result["new_path"])
        assert "02-Draft" in new_path.parts
        assert "03-Wiki" not in new_path.parts
        # Content fully preserved
        assert body_of(new_path) == body_before
        # Frontmatter: tier rewritten, demotion marker present, provenance kept
        fm = read_frontmatter(new_path)
        assert fm["tier"] == "02-Draft"
        assert "demoted_at" in fm
        assert fm["demoted_by"] == "director"
        assert fm["promotion_source"] == "agent"  # original provenance kept
        assert fm["promoted_by"] == "agent"
        # Old wiki file moved (gone)
        assert not wiki_path.exists()
        # Index updated
        meta = store.index.get_entry(promote_result["draft_id"])
        assert meta is not None and meta["tier"] == "02-Draft"
        assert meta["file_path"] == str(new_path)

    def test_demote_refused_for_non_director(
        self, store: KBStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        promote_result, _ = promote_valid_draft(store, monkeypatch)
        with pytest.raises(DirectorOnlyError) as exc_info:
            store.demote_entry(promote_result["draft_id"], caller="agent")
        assert exc_info.value.operation == "demote"
        # Entry unchanged
        meta = store.index.get_entry(promote_result["draft_id"])
        assert meta is not None and meta["tier"] == "03-Wiki"
        assert Path(meta["file_path"]).is_file()

    def test_demote_requires_wiki_tier(self, store: KBStore) -> None:
        raw = make_scored_raw(store)
        draft = store.create_kb_draft(raw_ids=[raw.entry_id], title="Still draft")
        with pytest.raises(ValueError, match="not in 03-Wiki"):
            store.demote_entry(draft.entry_id, caller="director")

    def test_demote_not_found(self, store: KBStore) -> None:
        with pytest.raises(ValueError, match="not found"):
            store.demote_entry("ghost-wiki", caller="director")


# ===================================================================
# 3. Soft-delete guard on 03-Wiki
# ===================================================================


class TestSoftDeleteWikiGuard:
    def test_soft_delete_wiki_refused_for_non_director(self, store: KBStore) -> None:
        """A Wiki entry cannot be soft-deleted by a non-director actor;
        the entry (index row + file) remains intact."""
        draft = force_to_wiki(store, "Guard soft delete")

        with pytest.raises(DirectorOnlyError):
            store.soft_delete_entry(draft.entry_id, actor="agent")

        meta = store.index.get_entry(draft.entry_id)
        assert meta is not None
        assert meta["tier"] == "03-Wiki"
        assert meta["deleted"] == 0
        assert Path(meta["file_path"]).is_file()

    def test_soft_delete_wiki_allowed_for_director(self, store: KBStore) -> None:
        draft = force_to_wiki(store, "Director soft delete")
        result = store.soft_delete_entry(draft.entry_id, actor="director")
        assert result["deleted"] is True
        meta = store.index.get_entry(draft.entry_id)
        assert meta is not None and meta["deleted"] == 1

    def test_soft_delete_wiki_default_actor_is_director(self, store: KBStore) -> None:
        """No actor given → defaults to director whitelist behavior (allowed)."""
        draft = force_to_wiki(store, "Default actor soft delete")
        result = store.soft_delete_entry(draft.entry_id)
        assert result["deleted"] is True

    def test_soft_delete_raw_unaffected_for_any_actor(self, store: KBStore) -> None:
        """01-Raw stays deletable by ANY actor — no behavior change outside Wiki."""
        raw = make_scored_raw(store)
        result = store.soft_delete_entry(raw.entry_id, actor="agent")
        assert result["deleted"] is True
        meta = store.index.get_entry(raw.entry_id)
        assert meta is not None and meta["deleted"] == 1


# ===================================================================
# 4. Purge (hard-delete) guard on 03-Wiki
# ===================================================================


class TestPurgeWikiGuard:
    def test_purge_wiki_refused_for_non_director(self, store: KBStore) -> None:
        """Purge path (KBStore.delete_entry) on 03-Wiki refuses non-directors."""
        draft = force_to_wiki(store, "Guard purge")

        with pytest.raises(DirectorOnlyError):
            store.delete_entry(draft.entry_id, actor="agent")

        meta = store.index.get_entry(draft.entry_id)
        assert meta is not None
        assert meta["tier"] == "03-Wiki"
        assert Path(meta["file_path"]).is_file()

    def test_purge_wiki_allowed_for_director(self, store: KBStore) -> None:
        draft = force_to_wiki(store, "Director purge")
        result = store.delete_entry(draft.entry_id, actor="director")
        assert result["deleted"] is True
        assert store.index.get_entry(draft.entry_id) is None

    def test_purge_wiki_default_actor_is_director(self, store: KBStore) -> None:
        """No actor given → purge allowed (legacy behavior, keeps scenario
        cleanups working until T9 rewrites them with explicit directors)."""
        draft = force_to_wiki(store, "Default actor purge")
        result = store.delete_entry(draft.entry_id)
        assert result["deleted"] is True

    def test_purge_raw_unaffected_for_any_actor(self, store: KBStore) -> None:
        raw = make_scored_raw(store)
        result = store.delete_entry(raw.entry_id, actor="agent")
        assert result["deleted"] is True
        assert store.index.get_entry(raw.entry_id) is None


# ===================================================================
# 5. AUTOINFO_DIRECTOR_ACTORS whitelist
# ===================================================================


class TestDirectorWhitelist:
    def test_is_director_defaults(self) -> None:
        assert is_director("director") is True
        assert is_director(None) is True
        assert is_director("") is True
        assert is_director("agent") is False
        assert is_director("agent-editor") is False

    def test_is_director_honors_env_whitelist(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AUTOINFO_DIRECTOR_ACTORS", "alice,bob")
        assert is_director("alice") is True
        assert is_director(" bob ") is True
        assert is_director("director") is False
        assert is_director(None) is False

    def test_whitelist_env_blocks_default_director(
        self, store: KBStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When 'director' is not whitelisted, the default actor is refused."""
        draft = force_to_wiki(store, "Env whitelist")
        monkeypatch.setenv("AUTOINFO_DIRECTOR_ACTORS", "alice")

        with pytest.raises(DirectorOnlyError):
            store.soft_delete_entry(draft.entry_id, actor="director")
        # The whitelisted actor is allowed
        result = store.soft_delete_entry(draft.entry_id, actor="alice")
        assert result["deleted"] is True

    def test_whitelist_env_spaces_trimmed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AUTOINFO_DIRECTOR_ACTORS", " alice , bob ")
        assert is_director("alice") is True
        assert is_director("bob") is True


# ===================================================================
# 6. Restore path unaffected by the guard
# ===================================================================


class TestRestoreUnaffected:
    def test_restore_wiki_entry_still_works(self, store: KBStore) -> None:
        """restore_entry has no actor gate — soft-deleted Wiki entries restore."""
        draft = force_to_wiki(store, "Restore wiki")
        store.soft_delete_entry(draft.entry_id, actor="director")
        result = store.restore_entry(draft.entry_id)
        assert result["restored"] is True
        meta = store.index.get_entry(draft.entry_id)
        assert meta is not None and meta["deleted"] == 0
