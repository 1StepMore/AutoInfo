"""Guard test: evidence-matrix row IDs must not collide with keystone A/B IDs.

Plan gap **T-A-04** (`.omo/plans/agent-oriented-gap-register.md` Todo 6):
``docs/dev/validation-scenario-contract.md`` §2.5 used rows ``A1…I6`` that
collided with the keystone taxonomy — pipeline stages ``A1–A7`` and user
levels ``B1/B2/B3`` — so a reader could mistake an evidence row for a pipeline
stage or user level. The rows were renamed to the namespaced ``EV-A1…EV-I6``.

This test locks the rename:

1. Parses §2.5 of the contract and extracts every evidence-row first-cell ID.
2. Fails if any extracted ID is un-prefixed (not ``EV-*``) — catches any
   reintroduced plain ``A1…I6`` row (including ``C1``/``F3`` which do not
   collide with the keystone but must still be namespaced).
3. Fails if any extracted ID matches a keystone stage/user ID
   (``^A[1-7]$`` or ``^B[123](\\.[0-9]+)?$``).
4. Proves the guard itself works with a deliberately un-prefixed sample.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs" / "dev" / "validation-scenario-contract.md"

# Keystone taxonomy IDs: pipeline stages A1-A7, user levels B1/B2/B3 (+ sub-levels).
KEYSTONE_ID_RE = re.compile(r"^A[1-7]$|^B[123](\.[0-9]+)?$")

# Evidence-row first cell: "| EV-A1 | ... |" / (pre-fix) "| A1 | ... |".
ROW_ID_RE = re.compile(r"^\|\s*([A-Za-z][A-Za-z0-9_.-]*)\s*\|")
# An evidence ID is either namespaced (EV-A1) or plain (A1).
EVIDENCE_ID_RE = re.compile(r"^(EV-)?[A-I][0-9]+$")

SECTION_START = "## 2.5 Full-Coverage Validation Matrix"
SECTION_END = "## 2.6"


def _section_2_5(text: str) -> str:
    start = text.index(SECTION_START)
    end = text.index(SECTION_END, start)
    return text[start:end]


def extract_evidence_row_ids(text: str) -> list[str]:
    """Return every evidence-row ID (first table cell) inside §2.5."""
    ids: list[str] = []
    for line in _section_2_5(text).splitlines():
        match = ROW_ID_RE.match(line)
        if match and EVIDENCE_ID_RE.match(match.group(1)):
            ids.append(match.group(1))
    return ids


def colliding_evidence_ids(ids: list[str]) -> list[str]:
    """Evidence IDs that equal a keystone stage/user ID."""
    return [i for i in ids if KEYSTONE_ID_RE.match(i)]


def unprefixed_evidence_ids(ids: list[str]) -> list[str]:
    """Evidence IDs missing the ``EV-`` namespace prefix."""
    return [i for i in ids if not i.startswith("EV-")]


def test_contract_2_5_evidence_ids_are_namespaced() -> None:
    """§2.5 has 51 evidence rows, all ``EV-*``, none colliding with A/B keystone."""
    text = CONTRACT.read_text(encoding="utf-8")
    ids = extract_evidence_row_ids(text)

    assert len(ids) == 51, f"expected 51 evidence rows in §2.5, got {len(ids)}: {ids}"
    assert unprefixed_evidence_ids(ids) == [], (
        "un-prefixed evidence IDs reintroduced in §2.5 (must be EV-*): "
        f"{unprefixed_evidence_ids(ids)}"
    )
    assert colliding_evidence_ids(ids) == [], (
        f"evidence IDs collide with keystone A1-A7 / B1-B3: {colliding_evidence_ids(ids)}"
    )


def test_guard_detects_unprefixed_sample() -> None:
    """The guard fails on a deliberately un-prefixed sample (RED proof)."""
    sample_ids = ["A1", "B2.4", "A7", "EV-C1", "EV-I6"]

    # Keystone collisions (A1, B2.4, A7) are detected; EV-* rows pass.
    assert colliding_evidence_ids(sample_ids) == ["A1", "B2.4", "A7"]

    # A plain non-keystone row (C1) is still flagged as un-prefixed.
    assert unprefixed_evidence_ids(sample_ids) == ["A1", "B2.4", "A7"]

    # A fully namespaced set produces no violations.
    assert colliding_evidence_ids(["EV-A1", "EV-B2", "EV-I6"]) == []
    assert unprefixed_evidence_ids(["EV-A1", "EV-B2", "EV-I6"]) == []


def test_guard_flags_unprefixed_row_in_synthetic_matrix() -> None:
    """Extraction + guard on a synthetic un-prefixed table cell fails."""
    synthetic = (
        f"{SECTION_START}\n\n"
        "| # | Feature |\n"
        "|---|---------|\n"
        "| A1 | System health |\n"
        "\n"
        f"{SECTION_END}\n"
    )
    ids = extract_evidence_row_ids(synthetic)
    assert ids == ["A1"]
    assert colliding_evidence_ids(ids) == ["A1"]
