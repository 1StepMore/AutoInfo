"""Deterministic facts artifact + separate runtime evidence (T03, decision 4).

Two artifacts, never mixed:

- ``facts.json`` — deterministic serialization (sorted keys, compact
  separators, no ``ts``/``run_id``): byte-identical across Windows/WSL for the
  same tree, so its sha256 is the cross-platform comparison anchor (DoD #5).
- ``evidence.json`` — run-scoped metadata (``run_id``/``ts``/``commit_sha``);
  never participates in sha comparison.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from autoinfo.gov.contract import GENERATOR_VERSION as GENERATOR_VERSION

ARTIFACT_DIR_REL = Path(".autoinfo") / "gov"
FACTS_NAME = "facts.json"
EVIDENCE_NAME = "evidence.json"


def input_hash(contract_version: int, facts: dict[str, Any]) -> str:
    """sha256 over (contract_version, generator_version, normalized facts).

    The normalized JSON uses the same canonical serialization as the artifact,
    so any change to a derived value, the contract version or the generator
    version changes the hash → STALE detection works across runs.
    """
    payload_doc = {
        "contract_version": contract_version,
        "generator_version": GENERATOR_VERSION,
        "facts": facts,
    }
    payload = json.dumps(
        payload_doc,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def render_facts(
    contract_version: int,
    facts: dict[str, Any],
    ih: str | None = None,
) -> str:
    """The deterministic facts.json bytes (no ts/run_id anywhere)."""
    if ih is None:
        ih = input_hash(contract_version, facts)
    return json.dumps(
        {
            "contract_version": contract_version,
            "generator_version": GENERATOR_VERSION,
            "input_hash": ih,
            "facts": facts,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def run_id() -> str:
    """Best-effort unique run id (host-pid-seconds); never part of facts.json."""
    return f"{socket.gethostname()}-{os.getpid()}-{int(datetime.now(UTC).timestamp())}"


def commit_sha(root: Path) -> str | None:
    """Short commit sha of the working tree HEAD, or None outside a repo."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def evidence(root: Path, contract_version: int, facts: dict[str, Any]) -> dict[str, Any]:
    """Run-scoped evidence block (the four mandatory fields for a PASS)."""
    return {
        "run_id": run_id(),
        "commit_sha": commit_sha(root),
        "input_hash": input_hash(contract_version, facts),
        "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def artifact_dir(root: Path) -> Path:
    return root / ARTIFACT_DIR_REL


def write_artifacts(
    root: Path,
    contract_version: int,
    facts: dict[str, Any],
) -> tuple[Path, Path]:
    """Persist facts.json (deterministic) + evidence.json (run-scoped)."""
    directory = artifact_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    facts_path = directory / FACTS_NAME
    evidence_path = directory / EVIDENCE_NAME
    # trailing newline keeps a stdout redirect byte-identical to the artifact
    facts_path.write_text(
        render_facts(contract_version, facts) + "\n", encoding="utf-8", newline="\n"
    )
    evidence_path.write_text(
        json.dumps(evidence(root, contract_version, facts), sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
        newline="\n",
    )
    return facts_path, evidence_path


def load_cached_facts(root: Path) -> dict[str, Any] | None:
    """Last derived facts tree, or None when no artifact exists yet."""
    path = artifact_dir(root) / FACTS_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    facts = data.get("facts")
    return facts if isinstance(facts, dict) else None


def load_cached_evidence(root: Path) -> dict[str, Any] | None:
    path = artifact_dir(root) / EVIDENCE_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None
