"""Guard: the known-red test budget has exactly one authority (tests/TRIAGE.md).

The failure-count budget drifted across documents: ``.github/workflows/ci.yml``
restated a stale "12 documented M1-deferred envelope failures" while
``tests/TRIAGE.md`` claimed a different superseding baseline. This guard locks
the single-source rule:

* ``tests/TRIAGE.md`` carries the authoritative section with the verified
  environment triple and the canonical baseline counts.
* ``.github/workflows/ci.yml`` points at that section and does NOT restate any
  numeric documented-failure claim.

Reference: tests/TRIAGE.md §Authoritative known-red budget.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRIAGE = ROOT / "tests" / "TRIAGE.md"
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"

# The number before "documented ... failures" is the contradiction this guard
# exists to prevent (e.g. "12 documented M1-deferred envelope failures").
_NUMERIC_FAILURE_CLAIM = re.compile(r"\d+\s+documented\b.*?\bfailures\b", re.IGNORECASE)


def test_triage_carries_authoritative_known_red_budget() -> None:
    """TRIAGE.md is the single authority: section header + env triple + baseline."""
    content = TRIAGE.read_text(encoding="utf-8")
    assert "## Authoritative known-red budget" in content, (
        "tests/TRIAGE.md must declare the authoritative known-red budget section"
    )
    assert "Python 3.11.15" in content, "env triple missing Python 3.11.15"
    assert "pytest 8.4.2" in content, "env triple missing pytest 8.4.2"
    assert "2594" in content, "canonical baseline test count (2594) missing"


def test_ci_does_not_restate_known_red_budget() -> None:
    """ci.yml must point at TRIAGE.md, never restate a numeric failure claim."""
    content = CI_YML.read_text(encoding="utf-8")
    assert "M1-deferred" not in content, (
        "ci.yml must not restate the retired M1-deferred budget — "
        "point at tests/TRIAGE.md §Authoritative known-red budget instead"
    )
    match = _NUMERIC_FAILURE_CLAIM.search(content)
    assert match is None, (
        f"ci.yml restates a numeric documented-failure claim: {match.group(0)!r}; "
        "the budget lives only in tests/TRIAGE.md"
    )
