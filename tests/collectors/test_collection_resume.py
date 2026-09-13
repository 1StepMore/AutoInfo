"""Collection checkpoint/resume tests (R-A-01).

``run_collection(resume_from=...)`` checkpoints per-source completion so an
interrupted collection resumes at the first source that did not durably
succeed.  A source that errored is deliberately left pending and retried; a
source that succeeded is skipped on resume.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autoinfo.checkpoint import CheckpointStore
from autoinfo.collect import run_collection
from autoinfo.config import Config, DomainConfig, SourceConfig
from autoinfo.models import CollectionResult


def _config() -> Config:
    sources = [
        SourceConfig(name="s1", type="rss", url="http://example.com/1"),
        SourceConfig(name="s2", type="rss", url="http://example.com/2"),
        SourceConfig(name="s3", type="rss", url="http://example.com/3"),
    ]
    return Config(domains=[DomainConfig(name="demo", sources=sources)])


class _FakeFetch:
    """Deterministic per-source fetch with a switchable s3 outcome."""

    def __init__(self) -> None:
        self.s3_ok = False
        self.calls: list[str] = []

    def __call__(
        self,
        source_config,
        domain,
        topic,
        limit,
        dry_run,
        existing_entries,
        collection_id,
        checker,
        new_items_collector=None,
        force_full=False,
        keywords=None,
    ):
        name = source_config.name
        self.calls.append(name)
        if name == "s3" and not self.s3_ok:
            return CollectionResult(
                collection_id=collection_id,
                domain=domain,
                source=name,
                status="error",
                errors=[{"message": "boom"}],
            )
        return CollectionResult(
            collection_id=collection_id,
            domain=domain,
            source=name,
            status="success",
            items_found=1,
            items_new=1,
        )


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _FakeFetch:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "autoinfo.collect.get_config_path",
        lambda: str(tmp_path / ".autoinfo/config.yaml"),
    )
    monkeypatch.setattr("autoinfo.collect.load_config", lambda _path: _config())
    fake = _FakeFetch()
    monkeypatch.setattr("autoinfo.collect._collect_from_source", fake)
    return fake


def test_no_resume_writes_no_checkpoint(patched: _FakeFetch) -> None:
    result = run_collection(domain="demo")
    assert [r["source"] for r in result["per_source"]] == ["s1", "s2", "s3"]
    assert result["resumed_skipped"] == []
    assert CheckpointStore().load("demo", "collect") is None


def test_resume_start_then_auto_skips_completed(patched: _FakeFetch) -> None:
    first = run_collection(domain="demo", resume_from="start")
    assert [r["status"] for r in first["per_source"]] == ["success", "success", "error"]
    checkpoint = CheckpointStore().load("demo", "collect")
    assert checkpoint is not None
    assert checkpoint.completed_steps() == ["s1", "s2"]
    assert checkpoint.status == "partial"

    patched.s3_ok = True
    second = run_collection(domain="demo", resume_from="auto")
    assert second["resumed_skipped"] == ["s1", "s2"]
    assert [r["source"] for r in second["per_source"]] == ["s3"]
    done = CheckpointStore().load("demo", "collect")
    assert done is not None
    assert done.completed_steps() == ["s1", "s2", "s3"]
    assert done.status == "complete"


def test_resume_from_named_source_skips_earlier(patched: _FakeFetch) -> None:
    result = run_collection(domain="demo", resume_from="s2")
    assert result["resumed_skipped"] == ["s1"]
    assert [r["source"] for r in result["per_source"]] == ["s2", "s3"]


def test_resume_from_unknown_source_raises(patched: _FakeFetch) -> None:
    with pytest.raises(ValueError, match="unknown source"):
        run_collection(domain="demo", resume_from="does-not-exist")


def test_resume_auto_without_checkpoint_runs_all(patched: _FakeFetch) -> None:
    result = run_collection(domain="demo", resume_from="auto")
    assert result["resumed_skipped"] == []
    assert [r["source"] for r in result["per_source"]] == ["s1", "s2", "s3"]


def test_resume_is_idempotent_after_complete(patched: _FakeFetch) -> None:
    run_collection(domain="demo", resume_from="start")
    patched.s3_ok = True
    run_collection(domain="demo", resume_from="auto")
    before = len(patched.calls)
    result = run_collection(domain="demo", resume_from="auto")
    # A fully completed checkpoint re-runs nothing (side-effect-free retry).
    assert result["resumed_skipped"] == ["s1", "s2", "s3"]
    assert result["per_source"] == []
    assert patched.calls[before:] == []
