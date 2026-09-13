"""Checkpointed production pipeline: collect → process → KB (R-A-01, R-B-01).

This module wires :mod:`autoinfo.checkpoint` to the real AutoInfo production
stages as a *resumable* five-step pipeline:

===============  ===================================================  =======
Step             Real operation                                       Stage
===============  ===================================================  =======
``collect``      :func:`autoinfo.collect.run_collection`               A1
``process``      :func:`autoinfo.process.run_processing`              A2
``kb-verify``    :meth:`autoinfo.kb.KBStore.count_entries`             A3
``kb-index``     :meth:`autoinfo.kb.KBStore.reindex_knowledge_base`    A3
``finalize``     pipeline manifest write (provenance)                  A7
===============  ===================================================  =======

Behaviour
---------
* **Checkpoint/resume** — after every completed step the checkpoint is
  persisted; ``resume_from="auto"`` skips every step already recorded
  completed and continues from the first not-yet-durable step.  ``resume_from``
  may also name a step to start at (skipping the earlier ones).
* **Idempotency** — a completed step is never re-executed on retry, and the
  underlying operations are themselves idempotent (collection dedups, G2
  dedups KB writes, reindex is a rebuild).  Retrying is therefore
  side-effect-free.
* **Rollback** — :func:`rollback_pipeline` removes the checkpoint *and* the
  files this run journaled (partial collection-cache writes), restoring the
  pre-run state.  ``run_pipeline(rollback_on_failure=True)`` does this
  automatically when a step fails.
* **Fault injection** — the ``AUTOINFO_PIPELINE_FAULT`` env var (comma-
  separated step names) makes the named step raise a :class:`PipelineFaultError`
  just before it runs.  This is the documented mutation seam used by the
  ``recover-*.yaml`` validation scenarios to prove RED→GREEN recovery.

The default 5-step sequence is exposed as ``default_steps()``; callers (and
scenarios) may pass a custom ``steps`` sequence for deterministic component
tests of the recovery engine.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from autoinfo.checkpoint import (
    RUN_COMPLETE,
    RUN_PARTIAL,
    RUN_ROLLED_BACK,
    STEP_COMPLETED,
    STEP_FAILED,
    CheckpointStore,
    PipelineCheckpoint,
    StepCheckpoint,
    make_signature,
)

#: Checkpoint namespace for the full production pipeline.
PIPELINE_NAME = "pipeline"

#: Test/dev fault-injection seam (comma-separated step names).
FAULT_ENV = "AUTOINFO_PIPELINE_FAULT"

#: Canonical step names, in execution order.
STEP_COLLECT = "collect"
STEP_PROCESS = "process"
STEP_KB_VERIFY = "kb-verify"
STEP_KB_INDEX = "kb-index"
STEP_FINALIZE = "finalize"

MANIFEST_NAME = "pipeline-manifest.json"


class PipelineFaultError(RuntimeError):
    """Raised when the ``AUTOINFO_PIPELINE_FAULT`` test seam fires."""


@dataclass
class PipelineStep:
    """One named, checkpointable pipeline step."""

    name: str
    run: Callable[[dict[str, Any]], dict[str, Any]]
    description: str = ""


@dataclass
class PipelineResult:
    """Outcome of one :func:`run_pipeline` invocation."""

    domain: str
    pipeline: str
    status: str
    executed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed_step: str | None = None
    error: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    checkpoint: dict[str, Any] | None = None
    resumed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "pipeline": self.pipeline,
            "status": self.status,
            "executed": list(self.executed),
            "skipped": list(self.skipped),
            "failed_step": self.failed_step,
            "error": self.error,
            "steps": list(self.steps),
            "resumed": self.resumed,
            "checkpoint": self.checkpoint,
        }


# ---------------------------------------------------------------------------
# Journaling / rollback helpers
# ---------------------------------------------------------------------------


def _snapshot_files(root: Path) -> set[str]:
    """Return the set of files under *root* (excluding ``_checkpoint``)."""
    if not root.is_dir():
        return set()
    files: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if "_checkpoint" in path.parts:
            continue
        files.add(str(path))
    return files


def _resolve_journal_path(path_str: str, base_dir: Path, domain: str) -> Path | None:
    """Return *path_str* as a Path only when safely inside ``base_dir/domain``.

    Rollback must never delete anything outside the run's own domain tree, so
    a journal entry that escapes it is ignored (defensive; the journal is only
    ever written by the pipeline itself).
    """
    try:
        path = Path(path_str).resolve()
    except OSError:
        return None
    domain_root = (base_dir / domain).resolve()
    try:
        path.relative_to(domain_root)
    except ValueError:
        return None
    if "_checkpoint" in path.parts:
        return None
    return path


# ---------------------------------------------------------------------------
# Default (real) steps
# ---------------------------------------------------------------------------


def _step_collect(ctx: dict[str, Any]) -> dict[str, Any]:
    """Step 1 — run the collection pipeline and journal new cache files."""
    from autoinfo.collect import run_collection

    base = Path(ctx["base_dir"]) / ctx["domain"]
    before = _snapshot_files(base)
    try:
        result = run_collection(
            domain=ctx["domain"],
            topic=ctx.get("topic", ""),
            limit=ctx.get("limit", 20),
        )
        return {
            "total_found": result.get("total_found", 0),
            "total_new": result.get("total_new", 0),
            "collection_id": result.get("collection_id", ""),
        }
    finally:
        new_files = sorted(_snapshot_files(base) - before)
        if new_files:
            ctx["journal"].extend(new_files)


def _step_process(ctx: dict[str, Any]) -> dict[str, Any]:
    """Step 2 — LLM extraction + quality gates + KB write."""
    from autoinfo.process import run_processing

    kwargs: dict[str, Any] = {"domain": ctx["domain"]}
    if ctx.get("model"):
        kwargs["model"] = ctx["model"]
    if ctx.get("topic"):
        kwargs["topic"] = ctx["topic"]
    result = run_processing(**kwargs)
    return {
        "total_items": result.total_items,
        "processed_count": result.processed_count,
        "kb_entries_created": result.kb_entries_created,
        "errors": len(result.errors),
    }


def _step_kb_verify(ctx: dict[str, Any]) -> dict[str, Any]:
    """Step 3 — verify the KB holds entries for the domain."""
    from autoinfo.kb import KBStore

    count = KBStore(min_content_chars=50).count_entries(ctx["domain"])
    return {"kb_entry_count": count}


def _step_kb_index(ctx: dict[str, Any]) -> dict[str, Any]:
    """Step 4 — rebuild the KB index (idempotent)."""
    from autoinfo.kb import KBStore

    report = KBStore(min_content_chars=50).reindex_knowledge_base(ctx["domain"])
    return {
        "indexed": report.get("indexed", report.get("entries_indexed", 0)),
        "domain": ctx["domain"],
    }


def _step_finalize(ctx: dict[str, Any]) -> dict[str, Any]:
    """Step 5 — write the pipeline completion manifest (provenance)."""
    from autoinfo.checkpoint import _utcnow  # local import keeps surface small

    base = Path(ctx["base_dir"]) / ctx["domain"] / "_checkpoint"
    base.mkdir(parents=True, exist_ok=True)
    manifest_path = base / MANIFEST_NAME
    payload = {
        "domain": ctx["domain"],
        "pipeline": PIPELINE_NAME,
        "completed_at": _utcnow(),
        "signature": ctx.get("signature", ""),
    }
    tmp = manifest_path.with_name(manifest_path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, manifest_path)
    return {"manifest": str(manifest_path)}


def default_steps() -> list[PipelineStep]:
    """Return a fresh copy of the canonical 5-step production pipeline."""
    return [
        PipelineStep(STEP_COLLECT, _step_collect, "collect sources into the cache"),
        PipelineStep(STEP_PROCESS, _step_process, "LLM extraction + quality gates + KB"),
        PipelineStep(STEP_KB_VERIFY, _step_kb_verify, "verify KB entry count"),
        PipelineStep(STEP_KB_INDEX, _step_kb_index, "rebuild KB index"),
        PipelineStep(STEP_FINALIZE, _step_finalize, "write completion manifest"),
    ]


def _fault_steps(explicit: Iterable[str] | None) -> set[str]:
    """Resolve the fault set from the explicit arg or the env seam."""
    if explicit is not None:
        return {s.strip() for s in explicit if str(s).strip()}
    raw = os.environ.get(FAULT_ENV, "")
    return {s.strip() for s in raw.split(",") if s.strip()}


# ---------------------------------------------------------------------------
# Run / resume
# ---------------------------------------------------------------------------


def _resolve_skip(
    resume_from: str | None,
    checkpoint: PipelineCheckpoint | None,
    signature: str,
    step_names: list[str],
) -> tuple[set[str], bool]:
    """Return ``(skip_set, is_resume)`` for the requested resume mode.

    * ``None`` / ``""`` / ``"start"`` → run every step from the beginning.
    * ``"auto"`` → skip steps the checkpoint records completed (requires a
      signature match; otherwise the caller starts fresh).
    * a step name → skip every step that precedes it.
    """
    if not resume_from or resume_from == "start":
        return set(), False
    if resume_from == "auto":
        if checkpoint is None or checkpoint.signature != signature:
            return set(), False
        return set(checkpoint.completed_steps()), True
    if resume_from not in step_names:
        raise ValueError(
            f"Cannot resume from unknown step '{resume_from}'. "
            f"Available steps: {', '.join(step_names)}"
        )
    return set(step_names[: step_names.index(resume_from)]), True


def run_pipeline(
    domain: str,
    *,
    topic: str = "",
    limit: int = 20,
    model: str = "",
    steps: Sequence[PipelineStep] | None = None,
    resume_from: str | None = None,
    rollback_on_failure: bool = False,
    base_dir: str | Path = "collections",
    fault_steps: Iterable[str] | None = None,
) -> PipelineResult:
    """Run the production pipeline with checkpoint/resume.

    Parameters
    ----------
    domain:
        Domain to run the pipeline for.
    topic, limit, model:
        Forwarded to the real collect/process steps.  They participate in the
        checkpoint signature, so a resumed run must match the original inputs.
    steps:
        Optional step sequence override (defaults to :func:`default_steps`).
        Used by component tests/scenarios for deterministic recovery proofs.
    resume_from:
        ``"auto"`` resumes from the persisted checkpoint (skips completed
        steps); a step name starts at that step; ``None``/``"start"`` runs
        everything from the beginning with checkpointing enabled.
    rollback_on_failure:
        When ``True``, a failed step triggers :func:`rollback_pipeline` —
        removing the checkpoint and any journaled partial files — and the run
        reports ``status="rolled_back"``.
    base_dir:
        Pipeline data root (default ``collections/``).
    fault_steps:
        Explicit fault set overriding ``AUTOINFO_PIPELINE_FAULT`` (test seam).

    Returns
    -------
    PipelineResult
        ``status`` is ``complete`` | ``partial`` | ``rolled_back``.
    """
    step_list = list(steps) if steps is not None else default_steps()
    step_names = [s.name for s in step_list]
    base = Path(base_dir)
    store = CheckpointStore(base)
    signature = make_signature(
        domain=domain,
        topic=topic,
        limit=limit,
        model=model,
        steps=step_names,
    )

    existing = store.load(domain, PIPELINE_NAME)
    skip, is_resume = _resolve_skip(resume_from, existing, signature, step_names)

    # Reuse a matching checkpoint when resuming; otherwise start a fresh one.
    if is_resume and existing is not None and existing.signature == signature:
        checkpoint = existing
        # Rebuild step order to match the current definition.
        known = {s.name: s for s in checkpoint.steps}
        checkpoint.steps = [known.get(name, StepCheckpoint(name=name)) for name in step_names]
    else:
        checkpoint = PipelineCheckpoint(
            domain=domain,
            pipeline=PIPELINE_NAME,
            signature=signature,
            steps=[StepCheckpoint(name=name) for name in step_names],
        )
        is_resume = False

    store.save(checkpoint)

    fault_set = _fault_steps(fault_steps)
    result = PipelineResult(
        domain=domain,
        pipeline=PIPELINE_NAME,
        status=RUN_COMPLETE,
        resumed=is_resume,
    )

    for step in step_list:
        if step.name in skip:
            # Already durable — do NOT re-execute (side-effect-free retry).
            result.skipped.append(step.name)
            continue

        fault = (
            PipelineFaultError(f"injected fault at step '{step.name}'")
            if step.name in fault_set
            else None
        )

        if fault is None:
            ctx: dict[str, Any] = {
                "domain": domain,
                "topic": topic,
                "limit": limit,
                "model": model,
                "base_dir": str(base),
                "signature": signature,
                "journal": [],
            }
            try:
                detail = step.run(ctx) or {}
            except Exception as run_exc:  # noqa: BLE001 — surfaced, never swallowed
                exc: Exception = run_exc
            else:
                if ctx["journal"]:
                    checkpoint.add_journal(ctx["journal"])
                checkpoint.mark(step.name, STEP_COMPLETED, json.dumps(detail, default=str))
                result.executed.append(step.name)
                store.save(checkpoint)
                continue
        else:
            exc = fault

        # -- Failure path (either injected or a real step exception) ---------
        message = str(exc)
        checkpoint.mark(step.name, STEP_FAILED, message)
        checkpoint.status = RUN_PARTIAL
        store.save(checkpoint)
        result.status = RUN_PARTIAL
        result.failed_step = step.name
        result.error = message
        result.steps = checkpoint.steps_summary()
        result.checkpoint = checkpoint.to_dict()
        if rollback_on_failure:
            rollback_pipeline(domain, base_dir=base)
            result.status = RUN_ROLLED_BACK
        return result

    checkpoint.status = RUN_COMPLETE
    store.save(checkpoint)
    result.steps = checkpoint.steps_summary()
    result.checkpoint = checkpoint.to_dict()
    return result


# ---------------------------------------------------------------------------
# Rollback / status
# ---------------------------------------------------------------------------


def rollback_pipeline(
    domain: str,
    *,
    pipeline: str = PIPELINE_NAME,
    base_dir: str | Path = "collections",
) -> dict[str, Any]:
    """Remove the checkpoint and any journaled partial files for *domain*.

    Returns a machine-readable summary::

        {
            "domain": ...,
            "pipeline": ...,
            "rolled_back": bool,        # a checkpoint existed and was cleared
            "removed_files": [str, ...],  # partial files deleted
            "checkpoint_path": str | None,
        }
    """
    base = Path(base_dir)
    store = CheckpointStore(base)
    checkpoint = store.load(domain, pipeline)
    removed: list[str] = []
    checkpoint_path: str | None = None

    if checkpoint is not None:
        for entry in checkpoint.journal:
            target = _resolve_journal_path(entry, base, domain)
            if target is None or not target.is_file():
                continue
            try:
                target.unlink()
                removed.append(str(target))
            except OSError:
                continue
        checkpoint_path = str(store.path(domain, pipeline))
        store.clear(domain, pipeline)

    return {
        "domain": domain,
        "pipeline": pipeline,
        "rolled_back": checkpoint is not None,
        "removed_files": removed,
        "checkpoint_path": checkpoint_path,
    }


def pipeline_status(
    domain: str,
    *,
    pipeline: str = PIPELINE_NAME,
    base_dir: str | Path = "collections",
) -> dict[str, Any]:
    """Return a checkpoint summary for *domain* (or an empty state)."""
    checkpoint = CheckpointStore(base_dir).load(domain, pipeline)
    if checkpoint is None:
        return {
            "domain": domain,
            "pipeline": pipeline,
            "status": "none",
            "last_completed": None,
            "completed": [],
            "steps": [],
        }
    return {
        "domain": domain,
        "pipeline": pipeline,
        "status": checkpoint.status,
        "last_completed": checkpoint.last_completed(),
        "completed": checkpoint.completed_steps(),
        "journal": list(checkpoint.journal),
        "steps": checkpoint.steps_summary(),
    }
