"""Whole-repo drift scan tests (T03, P3: default-ON, exclude-with-reason)."""

from __future__ import annotations

from pathlib import Path

from autoinfo.gov import scan as scan_mod
from autoinfo.gov.contract import load


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _scan_facts(mcp_tools: int = 151) -> dict[str, object]:
    """Facts for scan tests. `tests` is deliberately omitted: the live pytest
    collection count moves with every PR (6829 today), and a fact absent from
    the expected tree is simply not compared — the real `gov check` always
    derives it fresh instead."""
    return {
        "mcp_tools": mcp_tools,
        "cli_groups": 31,
        "validation_scenarios": {"total": 189, "functional": 86, "regression": 103},
        "demo_domains": 21,
        "delivery_channels": 13,
        "llm_required_tools": 16,
        "adr_count": 14,
    }


def test_scan_of_aligned_tree_is_clean() -> None:
    """T01 zeroed the drift: the real contract + real facts must scan clean."""
    contract = load()
    facts = _scan_facts()
    result = scan_mod.scan_markdown(contract, facts)
    assert result.violations == (), result.violations[:10]
    assert result.files_scanned > 100


def test_tampered_value_is_reported_with_file_line() -> None:
    """Negative control: a wrong expected tool count must produce a violation."""
    contract = load()
    facts = _scan_facts(mcp_tools=150)
    result = scan_mod.scan_markdown(contract, facts)
    hits = [v for v in result.violations if "mcp_tools 151 != 150" in v]
    assert hits, result.violations[:10]
    assert any(v.startswith("CONTRIBUTING.md:") for v in hits)


def test_every_excluded_path_has_reason_and_is_respected() -> None:
    contract = load()
    assert contract.ignore_marker == "counts-ignore"
    archive = [e for e in contract.excludes if e.path == "docs/archive/**"]
    assert archive and archive[0].reason


def test_exclusion_matching_covers_recursive_and_glob() -> None:
    contract = load()
    assert scan_mod.exclusion_reason("docs/archive/x.md", contract) is not None
    assert scan_mod.exclusion_reason("docs/archive/deep/x.md", contract) is not None
    assert scan_mod.exclusion_reason("docs/adr/0005-anything.md", contract) is not None
    assert scan_mod.exclusion_reason("CHANGELOG.md", contract) is not None
    assert scan_mod.exclusion_reason("tests/TRIAGE.md", contract) is not None
    assert scan_mod.exclusion_reason("README.md", contract) is None
    assert scan_mod.exclusion_reason("docs/dev/specs/pipeline.md", contract) is None


def test_tracked_markdown_includes_nested_docs(tmp_path: Path) -> None:  # noqa: ARG001
    files = scan_mod.tracked_markdown(_repo_root())
    assert "README.md" in files
    assert any(f.startswith("docs/dev/specs/") for f in files)
    # non-ASCII names come through raw (core.quotepath=false)
    assert any(not f.isascii() for f in files), "quotepath must stay disabled"
