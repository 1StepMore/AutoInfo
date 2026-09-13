"""Pipeline checkpoint / resume support (R-A-01, R-B-01).

Long-running pipelines (collect → process → KB) persist the last completed
step so an interrupted run can *resume* instead of restarting from scratch
(methodology §2.4 Graceful Degradation / §3.3 Checkpoint-Resume Pattern).

Design contracts
----------------
* **A checkpoint is a resume cursor, not a progress log.**  A step is only
  marked ``completed`` *after* its effect is durable; a step that raised stays
  ``failed`` and will be retried on resume.
* **Atomic writes.**  The JSON state is written to a sibling ``.tmp`` file and
  swapped in with :func:`os.replace`, so a crash mid-write never leaves a torn
  checkpoint that a later run would misread.
* **Signature-scoped.**  A checkpoint carries a short signature of the run's
  inputs.  Resuming with materially different parameters is refused instead of
  silently reusing a stale cursor (that would skip work the new run needs).
* **Self-describing.**  The file is plain JSON at
  ``collections/<domain>/_checkpoint/<pipeline>.json`` (the ``_checkpoint``
  directory is skipped by the collection cache reader, and lives under the
  domain rather than a source so the cross-date dedup scan never sees it).

Public API
----------
``CheckpointStore`` loads/saves/clears :class:`PipelineCheckpoint` objects.
``make_signature`` builds the input digest.  Step statuses are the module
constants ``STEP_PENDING`` / ``STEP_COMPLETED`` / ``STEP_FAILED`` /
``STEP_SKIPPED``; run statuses are ``RUN_RUNNING`` / ``RUN_PARTIAL`` /
``RUN_COMPLETE`` / ``RUN_ROLLED_BACK``.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: Subdirectory (under the pipeline's base dir) holding checkpoint JSON files.
CHECKPOINT_DIRNAME = "_checkpoint"

# -- Step statuses ----------------------------------------------------------
STEP_PENDING = "pending"
STEP_COMPLETED = "completed"
STEP_FAILED = "failed"
STEP_SKIPPED = "skipped"

# -- Run statuses -----------------------------------------------------------
RUN_RUNNING = "running"
RUN_PARTIAL = "partial"
RUN_COMPLETE = "complete"
RUN_ROLLED_BACK = "rolled_back"


def _utcnow() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def make_signature(**params: Any) -> str:
    """Build a short, stable signature for a pipeline run's inputs.

    Non-JSON-serialisable values are stringified (``default=str``), and keys
    are sorted so two invocations with the same logical inputs always hash
    identically.
    """
    payload = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


@dataclass
class StepCheckpoint:
    """Persisted state of one pipeline step."""

    name: str
    status: str = STEP_PENDING
    detail: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StepCheckpoint:
        return cls(
            name=str(data.get("name", "")),
            status=str(data.get("status", STEP_PENDING)),
            detail=str(data.get("detail", "")),
            updated_at=str(data.get("updated_at", "")),
        )


@dataclass
class PipelineCheckpoint:
    """Checkpoint state for one ``(domain, pipeline)`` pair."""

    domain: str
    pipeline: str
    signature: str
    steps: list[StepCheckpoint] = field(default_factory=list)
    status: str = RUN_RUNNING
    #: Files created by this run that a rollback should remove (relative paths).
    journal: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    # -- Queries ------------------------------------------------------------

    def step_names(self) -> list[str]:
        return [s.name for s in self.steps]

    def completed_steps(self) -> list[str]:
        return [s.name for s in self.steps if s.status == STEP_COMPLETED]

    def last_completed(self) -> str | None:
        """Return the name of the last completed step in declared order."""
        last: str | None = None
        for step in self.steps:
            if step.status == STEP_COMPLETED:
                last = step.name
        return last

    def is_completed(self, name: str) -> bool:
        return name in self.completed_steps()

    def get_step(self, name: str) -> StepCheckpoint | None:
        for step in self.steps:
            if step.name == name:
                return step
        return None

    # -- Mutations ----------------------------------------------------------

    def mark(self, name: str, status: str, detail: str = "") -> None:
        """Set *name*'s status (creating the row when it does not exist)."""
        step = self.get_step(name)
        if step is None:
            step = StepCheckpoint(name=name)
            self.steps.append(step)
        step.status = status
        step.detail = detail
        step.updated_at = _utcnow()

    def add_journal(self, paths: list[str]) -> None:
        """Record file paths created by this run (deduped, order preserved)."""
        seen = set(self.journal)
        for path in paths:
            if path not in seen:
                seen.add(path)
                self.journal.append(path)

    def steps_summary(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self.steps]

    # -- Serialization ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "pipeline": self.pipeline,
            "signature": self.signature,
            "status": self.status,
            "journal": list(self.journal),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineCheckpoint:
        steps_raw = data.get("steps") or []
        steps = [StepCheckpoint.from_dict(s) for s in steps_raw if isinstance(s, dict)]
        return cls(
            domain=str(data.get("domain", "")),
            pipeline=str(data.get("pipeline", "")),
            signature=str(data.get("signature", "")),
            steps=steps,
            status=str(data.get("status", RUN_RUNNING)),
            journal=[str(p) for p in (data.get("journal") or [])],
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
        )


class CheckpointStore:
    """Load/save/clear :class:`PipelineCheckpoint` state on disk.

    Parameters
    ----------
    base_dir:
        Root directory holding per-domain pipeline data.  Defaults to the
        project-root ``collections/`` directory (same base the collection
        cache uses), so state travels with the pipeline's own artifacts.
    """

    def __init__(self, base_dir: str | Path = "collections") -> None:
        self.base_dir = Path(base_dir)

    def path(self, domain: str, pipeline: str) -> Path:
        """Return the checkpoint file path for ``(domain, pipeline)``."""
        return self.base_dir / domain / CHECKPOINT_DIRNAME / f"{pipeline}.json"

    def load(self, domain: str, pipeline: str) -> PipelineCheckpoint | None:
        """Read the checkpoint, or ``None`` when absent/unreadable."""
        path = self.path(domain, pipeline)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        return PipelineCheckpoint.from_dict(data)

    def save(self, checkpoint: PipelineCheckpoint) -> Path:
        """Persist *checkpoint* atomically; returns the written path."""
        path = self.path(checkpoint.domain, checkpoint.pipeline)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not checkpoint.created_at:
            checkpoint.created_at = _utcnow()
        checkpoint.updated_at = _utcnow()
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(
            json.dumps(checkpoint.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, path)
        return path

    def clear(self, domain: str, pipeline: str) -> bool:
        """Delete the checkpoint file; returns ``True`` when one existed."""
        path = self.path(domain, pipeline)
        if not path.is_file():
            return False
        try:
            path.unlink()
        except OSError:
            return False
        return True
