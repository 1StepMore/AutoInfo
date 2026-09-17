"""Guard: the known-red test budget has exactly one authority (tests/TRIAGE.md).

The failure-count budget drifted across documents: ``.github/workflows/ci.yml``
restated a stale "12 documented M1-deferred envelope failures" while
``tests/TRIAGE.md`` claimed a different superseding baseline. This guard locks
the single-source rule:

* ``tests/TRIAGE.md`` carries the authoritative section with the verified
  environment triple, the canonical selection and the baseline counts.
* ``.github/workflows/ci.yml`` points at that section and does NOT restate any
  numeric documented-failure claim.

It also locks the budget's **identity**, not just its size. A count-only budget
silently permits a new failure to be cancelled out by an old one healing — the
count stays put while the composition rots. The authoritative section
therefore enumerates the failing node ids explicitly, and this guard asserts
that every listed id resolves to a real test on disk and that the stated
failure count matches the list length.

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

_AUTHORITATIVE_HEADER = "## Authoritative known-red budget"

# `**Baseline**: **2594 tests -> 17 failed / 2553 passed / 24 skipped / 0 errors**`
_BASELINE = re.compile(
    r"\*\*Baseline\*\*:\s*\*\*(\d+)\s+tests\s*->\s*(\d+)\s+failed\s*/\s*"
    r"(\d+)\s+passed\s*/\s*(\d+)\s+skipped\s*/\s*(\d+)\s+errors\*\*"
)

# A bare pytest node id line (no leading `|`, no list bullet).
_NODE_ID = re.compile(r"^(tests/[\w./-]+\.py)::(\S+)$", re.MULTILINE)

# A node id may name a bare function or a Class::method — so the definition
# being looked for may be a module-level or an indented (class) def.
_TEST_NAME = re.compile(r"^\s*(?:async\s+)?def\s+(?P<name>\w+)\s*\(", re.MULTILINE)


def _authoritative_section() -> str:
    """Return the authoritative known-red budget section of TRIAGE.md."""
    content = TRIAGE.read_text(encoding="utf-8")
    start = content.index(_AUTHORITATIVE_HEADER)
    rest = content[start + len(_AUTHORITATIVE_HEADER) :]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def _budgeted_node_ids() -> list[str]:
    """Return every bare node id line in the authoritative section, in order."""
    section = _authoritative_section()
    return [f"{match.group(1)}::{match.group(2)}" for match in _NODE_ID.finditer(section)]


def test_triage_carries_authoritative_known_red_budget() -> None:
    """TRIAGE.md is the single authority: section header + env triple + baseline."""
    content = TRIAGE.read_text(encoding="utf-8")
    assert _AUTHORITATIVE_HEADER in content, (
        "tests/TRIAGE.md must declare the authoritative known-red budget section"
    )
    assert "Python 3.14.4" in content, "env triple missing Python 3.14.4"
    assert "pytest 8.4.2" in content, "env triple missing pytest 8.4.2"
    assert "pytest-timeout 2.4.0" in content, "env triple missing pytest-timeout 2.4.0"
    assert "pytest tests/mcp tests/validation tests/cli tests/output tests/llm" in content, (
        "canonical selection command missing from the authoritative section"
    )
    assert _BASELINE.search(_authoritative_section()), (
        "authoritative section must state the baseline as "
        "'**Baseline**: **N tests -> F failed / P passed / S skipped / E errors**'"
    )


def test_budget_lists_exact_failing_node_ids() -> None:
    """The budget records test identity: the stated count equals the list length."""
    node_ids = _budgeted_node_ids()
    assert node_ids, (
        "the authoritative section must enumerate the failing node ids — a bare "
        "count lets a new failure be cancelled out by an old one healing"
    )

    duplicates = sorted({node_id for node_id in node_ids if node_ids.count(node_id) > 1})
    assert not duplicates, f"duplicate node ids in the budget: {duplicates}"

    match = _BASELINE.search(_authoritative_section())
    assert match is not None, "baseline line missing (see the sibling guard test)"
    stated_failed = int(match.group(2))
    assert stated_failed == len(node_ids), (
        f"baseline says {stated_failed} failed but the budget lists "
        f"{len(node_ids)} node id(s) — the count and the identity list must agree"
    )


def test_every_budgeted_node_id_resolves_to_a_real_test() -> None:
    """No budget entry may be stale: each id must exist on disk right now."""
    stale: list[str] = []
    for node_id in _budgeted_node_ids():
        rel_path, test_path = node_id.split("::", 1)
        source = ROOT / rel_path
        if not source.is_file():
            stale.append(f"{node_id}  (file missing: {rel_path})")
            continue
        leaf = test_path.split("::")[-1]
        names = {m.group("name") for m in _TEST_NAME.finditer(source.read_text(encoding="utf-8"))}
        if leaf not in names:
            stale.append(f"{node_id}  (no `def {leaf}` in {rel_path})")

    assert not stale, (
        "known-red budget entries no longer resolve to real tests — remove or "
        "re-point them in tests/TRIAGE.md §Authoritative known-red budget:\n  - "
        + "\n  - ".join(stale)
    )


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
