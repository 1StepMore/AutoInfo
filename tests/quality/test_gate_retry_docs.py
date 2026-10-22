"""Doc/code consistency for quality-gate retry semantics (issue #565).

G0 is a deterministic schema check: retrying cannot flip an invalid document
to valid, so it blocks without retry. Only G4 (LLM-judged factual consistency)
carries the 3x retry. These tests parse the real docs so the prose cannot drift
from ``_DEFAULT_QUALITY_GATES`` again.
"""

from __future__ import annotations

from pathlib import Path

from autoinfo.config import _DEFAULT_QUALITY_GATES, _GATE_CONFIG_KEY_MAP

REPO_ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE_DOC = REPO_ROOT / "docs" / "dev" / "acceptance-framework.md"
AGENTS_DOC = REPO_ROOT / "AGENTS.md"

RETRY_TABLE_HEADING = "### Quality Gate Retry Semantics (machine-checked)"

# The two gates whose retry semantics are in scope for #565. The table must
# record exactly these and no others.
GATES_IN_SCOPE = ("G0", "G4")


def _parse_retry_table() -> dict[str, int]:
    lines = ACCEPTANCE_DOC.read_text(encoding="utf-8").splitlines()
    assert RETRY_TABLE_HEADING in lines, (
        f"{ACCEPTANCE_DOC} is missing the heading {RETRY_TABLE_HEADING!r}"
    )

    start = lines.index(RETRY_TABLE_HEADING) + 1
    table_lines: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("|"):
            table_lines.append(stripped)
        elif table_lines:
            break

    assert len(table_lines) >= 3, (
        f"expected a header, a separator, and at least one row under "
        f"{RETRY_TABLE_HEADING!r}, found {table_lines!r}"
    )

    header = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    assert header == ["Gate", "Category", "Attempts"], f"unexpected retry-table header: {header!r}"

    parsed: dict[str, int] = {}
    for row in table_lines[2:]:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert len(cells) == 3, f"malformed retry-table row: {row!r}"
        gate, _category, attempts = cells
        parsed[gate] = int(attempts)
    return parsed


def _expected_retries() -> dict[str, int]:
    expected: dict[str, int] = {}
    for short_name in GATES_IN_SCOPE:
        long_name = _GATE_CONFIG_KEY_MAP[short_name]
        expected[long_name] = _DEFAULT_QUALITY_GATES[short_name]["retries"]
    return expected


def test_retry_table_matches_default_quality_gates() -> None:
    parsed = _parse_retry_table()
    expected = _expected_retries()

    assert parsed == expected, (
        "retry table in docs/dev/acceptance-framework.md disagrees with "
        f"_DEFAULT_QUALITY_GATES:\n  doc:    {parsed}\n  config: {expected}"
    )


def test_agents_md_g0_row_says_no_retry() -> None:
    lines = AGENTS_DOC.read_text(encoding="utf-8").splitlines()
    g0_rows = [line for line in lines if line.lstrip().startswith("| G0:")]
    assert len(g0_rows) == 1, (
        f"expected exactly one G0 table row in AGENTS.md, found {len(g0_rows)}"
    )

    row = g0_rows[0]
    assert "3× retry" not in row, f"AGENTS.md G0 row still claims retries: {row!r}"
    assert "no retry" in row, f"AGENTS.md G0 row does not say 'no retry': {row!r}"
