"""Checkpoint/resume + rollback + idempotency tests (R-A-01, R-B-01, R-B-02).

These lock the recovery engine introduced for Todo 19 of the agent-oriented
gap register:

* ``CheckpointStore`` persists atomically and is signature-scoped.
* ``run_pipeline`` checkpoints after every completed step; ``resume_from="auto"``
  skips completed steps and never re-executes them (side-effect-free retry).
* ``rollback_pipeline`` removes the checkpoint and the partial files journaled
  by the aborted collect step, restoring the pre-run state.
* ``AUTOINFO_PIPELINE_FAULT`` injects a deterministic mid-pipeline failure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from autoinfo.checkpoint import (
    RUN_COMPLETE,
    STEP_COMPLETED,
    CheckpointStore,
    PipelineCheckpoint,
    StepCheckpoint,
    make_signature,
)
from autoinfo.pipeline import (
    FAULT_ENV,
    PipelineFaultError,
    PipelineStep,
    pipeline_status,
    rollback_pipeline,
    run_pipeline,
)


def _counting_steps(calls: dict[str, int], names: list[str]) -> list[PipelineStep]:
    """Build steps that record each execution in *calls*."""

    def _make(name: str) -> PipelineStep:
        def _run(ctx: dict[str, Any]) -> dict[str, Any]:
            calls[name] = calls.get(name, 0) + 1
            return {"step": name, "executions": calls[name]}

        return PipelineStep(name, _run)

    return [_make(name) for name in names]


class TestCheckpointStore:
    def test_round_trips_state(self, tmp_path: Path) -> None:
        store = CheckpointStore(tmp_path / "collections")
        cp = PipelineCheckpoint(
            domain="demo",
            pipeline="pipeline",
            signature="abc",
            steps=[StepCheckpoint(name="a"), StepCheckpoint(name="b")],
        )
        cp.mark("a", STEP_COMPLETED)
        path = store.save(cp)

        assert path.is_file()
        loaded = store.load("demo", "pipeline")
        assert loaded is not None
        assert loaded.completed_steps() == ["a"]
        assert loaded.last_completed() == "a"
        assert loaded.status == cp.status

    def test_load_missing_returns_none(self, tmp_path: Path) -> None:
        store = CheckpointStore(tmp_path / "collections")
        assert store.load("nope", "pipeline") is None

    def test_atomic_write_leaves_no_tmp(self, tmp_path: Path) -> None:
        store = CheckpointStore(tmp_path / "collections")
        cp = PipelineCheckpoint(domain="demo", pipeline="pipeline", signature="x")
        store.save(cp)
        leftovers = list(store.path("demo", "pipeline").parent.glob("*.tmp"))
        assert leftovers == []

    def test_clear_removes_file(self, tmp_path: Path) -> None:
        store = CheckpointStore(tmp_path / "collections")
        store.save(PipelineCheckpoint(domain="d", pipeline="pipeline", signature="x"))
        assert store.clear("d", "pipeline") is True
        assert store.clear("d", "pipeline") is False

    def test_corrupt_file_is_ignored(self, tmp_path: Path) -> None:
        store = CheckpointStore(tmp_path / "collections")
        path = store.path("d", "pipeline")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        assert store.load("d", "pipeline") is None

    def test_signature_is_stable_and_sensitive(self) -> None:
        assert make_signature(a=1, b="x") == make_signature(b="x", a=1)
        assert make_signature(a=1) != make_signature(a=2)


class TestRunPipelineResume:
    def test_completed_run_persists_every_step(self, tmp_path: Path) -> None:
        calls: dict[str, int] = {}
        steps = _counting_steps(calls, ["s1", "s2", "s3"])
        result = run_pipeline("demo", steps=steps, resume_from="start", base_dir=tmp_path)
        assert result.status == RUN_COMPLETE
        assert result.executed == ["s1", "s2", "s3"]
        status = pipeline_status("demo", base_dir=tmp_path)
        assert status["completed"] == ["s1", "s2", "s3"]

    def test_failure_at_step_3_of_5_saves_partial_checkpoint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: dict[str, int] = {}
        steps = _counting_steps(calls, ["s1", "s2", "s3", "s4", "s5"])
        monkeypatch.setenv(FAULT_ENV, "s3")

        result = run_pipeline("demo", steps=steps, resume_from="start", base_dir=tmp_path)
        assert result.status == "partial"
        assert result.failed_step == "s3"
        assert result.executed == ["s1", "s2"]
        assert result.skipped == []
        assert isinstance(result.error, str) and "s3" in result.error
        # s3 and later never ran; the checkpoint records the durable prefix.
        assert calls == {"s1": 1, "s2": 1}
        status = pipeline_status("demo", base_dir=tmp_path)
        assert status["last_completed"] == "s2"
        assert status["completed"] == ["s1", "s2"]

    def test_resume_completes_and_skips_completed_steps(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: dict[str, int] = {}
        steps = _counting_steps(calls, ["s1", "s2", "s3", "s4", "s5"])
        monkeypatch.setenv(FAULT_ENV, "s3")
        run_pipeline("demo", steps=steps, resume_from="start", base_dir=tmp_path)

        monkeypatch.delenv(FAULT_ENV)
        result = run_pipeline("demo", steps=steps, resume_from="auto", base_dir=tmp_path)

        assert result.status == RUN_COMPLETE
        assert result.skipped == ["s1", "s2"]
        assert result.executed == ["s3", "s4", "s5"]
        # Idempotency: skipped steps were never re-executed.
        assert calls == {"s1": 1, "s2": 1, "s3": 1, "s4": 1, "s5": 1}

    def test_retry_after_success_is_fully_skipped(self, tmp_path: Path) -> None:
        calls: dict[str, int] = {}
        steps = _counting_steps(calls, ["s1", "s2"])
        run_pipeline("demo", steps=steps, resume_from="start", base_dir=tmp_path)
        result = run_pipeline("demo", steps=steps, resume_from="auto", base_dir=tmp_path)

        assert result.status == RUN_COMPLETE
        assert result.skipped == ["s1", "s2"]
        assert result.executed == []
        assert calls == {"s1": 1, "s2": 1}

    def test_named_step_resume_starts_there(self, tmp_path: Path) -> None:
        calls: dict[str, int] = {}
        steps = _counting_steps(calls, ["s1", "s2", "s3"])
        result = run_pipeline("demo", steps=steps, resume_from="s2", base_dir=tmp_path)
        assert result.skipped == ["s1"]
        assert result.executed == ["s2", "s3"]
        assert calls == {"s2": 1, "s3": 1}

    def test_unknown_step_resume_is_rejected(self, tmp_path: Path) -> None:
        steps = _counting_steps({}, ["s1"])
        with pytest.raises(ValueError, match="unknown step"):
            run_pipeline("demo", steps=steps, resume_from="nope", base_dir=tmp_path)

    def test_signature_mismatch_restarts_instead_of_skipping(self, tmp_path: Path) -> None:
        calls: dict[str, int] = {}
        steps = _counting_steps(calls, ["s1"])
        run_pipeline("demo", steps=steps, topic="a", resume_from="start", base_dir=tmp_path)
        # A materially different run must not reuse the stale cursor.
        run_pipeline("demo", steps=steps, topic="b", resume_from="auto", base_dir=tmp_path)
        assert calls == {"s1": 2}

    def test_fault_raises_pipeline_fault_type(self) -> None:
        assert issubclass(PipelineFaultError, RuntimeError)


class TestRollback:
    def _journaling_steps(self, target: Path) -> list[PipelineStep]:
        def _collect(ctx: dict[str, Any]) -> dict[str, Any]:
            target.mkdir(parents=True, exist_ok=True)
            item = target / "item.json"
            item.write_text("{}", encoding="utf-8")
            ctx["journal"].append(str(item))
            return {"created": str(item)}

        def _process(ctx: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("network down")

        def _kb(ctx: dict[str, Any]) -> dict[str, Any]:
            return {"ok": True}

        return [
            PipelineStep("collect", _collect),
            PipelineStep("process", _process),
            PipelineStep("kb", _kb),
        ]

    def test_rollback_removes_partial_files_and_checkpoint(self, tmp_path: Path) -> None:
        target = tmp_path / "demo" / "src1"
        steps = self._journaling_steps(target)
        result = run_pipeline("demo", steps=steps, resume_from="start", base_dir=tmp_path)
        assert result.status == "partial"
        assert (target / "item.json").is_file()

        report = rollback_pipeline("demo", base_dir=tmp_path)
        assert report["rolled_back"] is True
        assert not (target / "item.json").exists()
        assert pipeline_status("demo", base_dir=tmp_path)["status"] == "none"

    def test_rollback_is_a_noop_without_checkpoint(self, tmp_path: Path) -> None:
        report = rollback_pipeline("demo", base_dir=tmp_path)
        assert report["rolled_back"] is False
        assert report["removed_files"] == []

    def test_rollback_on_failure_auto_cleans(self, tmp_path: Path) -> None:
        target = tmp_path / "demo" / "src1"
        steps = self._journaling_steps(target)
        result = run_pipeline(
            "demo",
            steps=steps,
            resume_from="start",
            rollback_on_failure=True,
            base_dir=tmp_path,
        )
        assert result.status == "rolled_back"
        assert not (target / "item.json").exists()
        assert pipeline_status("demo", base_dir=tmp_path)["status"] == "none"
