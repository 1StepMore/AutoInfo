"""Derived truth for the governance facts (T03, principle P2).

Counts are DERIVED from code, never declared. Every function here is a
``derive`` target named in the contract; each returns an int or a flat dict of
ints (the 8 sections of ``facts.json``). Import errors inside a deriver mean
the *environment* is broken, not that docs drifted — callers map that to exit
2 exactly like ``doc_inventory.environment_failure`` does.
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from autoinfo.gov.contract import Contract

_FACT_ORDER: tuple[str, ...] = (
    "mcp_tools",
    "cli_groups",
    "validation_scenarios",
    "tests",
    "demo_domains",
    "delivery_channels",
    "llm_required_tools",
    "adr_count",
)


class FactsError(Exception):
    """A derive instrument failed — environment problem, not doc drift."""


def mcp_tools() -> int:
    """Live declared MCP tool count from the runtime registry."""
    from autoinfo.mcp.server import _full_tool_list

    return len(_full_tool_list())


def cli_groups() -> int:
    """Live Typer command-group count (sub-apps registered on the CLI app)."""
    from autoinfo.cli import app

    names = [info.name for info in getattr(app, "registered_groups", []) if info.name]
    return len(names)


def validation_scenarios() -> dict[str, int]:
    """Scenario totals from the on-disk YAML library (total/functional/regression)."""
    from autoinfo.gov.contract import resolve_repo_root

    base = resolve_repo_root() / "src" / "autoinfo" / "mcp" / "scenarios"
    if not base.is_dir():
        raise FactsError(f"scenario directory missing: {base}")
    return {
        "total": sum(1 for _ in base.rglob("*.yaml")),
        "functional": sum(1 for _ in base.glob("*.yaml")),
        "regression": sum(1 for _ in (base / "regression").glob("*.yaml")),
    }


def tests() -> int:
    """Live pytest collection count (slow: shells out to pytest --collect-only)."""
    from autoinfo.gov.contract import resolve_repo_root

    root = resolve_repo_root()
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise FactsError(f"pytest --collect-only failed to run: {exc}") from exc
    match = re.search(r"(\d+)\s+tests?\s+collected", f"{proc.stdout}\n{proc.stderr}")
    if match is None:
        raise FactsError(f"unparsable pytest output (exit {proc.returncode})")
    return int(match.group(1))


def demo_domains() -> int:
    """Demo-domain count: domains/ subdirectories carrying a sources.yaml."""
    from autoinfo.gov.contract import resolve_repo_root

    base = resolve_repo_root() / "src" / "autoinfo" / "data" / "domains"
    if not base.is_dir():
        raise FactsError(f"domains directory missing: {base}")
    return sum(
        1 for entry in base.iterdir() if entry.is_dir() and (entry / "sources.yaml").is_file()
    )


def delivery_channels() -> int:
    """Registered delivery-channel count from the runtime registry."""
    from autoinfo.delivery import get_available_channels

    return len(get_available_channels())


def llm_required_tools() -> int:
    """Count of tools that require a configured LLM key."""
    from autoinfo.mcp.server import _LLM_REQUIRED_TOOLS

    return len(_LLM_REQUIRED_TOOLS)


def adr_count() -> int:
    """Count of numbered ADR files (docs/adr/NNNN-*.md; TEMPLATE/README excluded)."""
    from autoinfo.gov.contract import resolve_repo_root

    base = resolve_repo_root() / "docs" / "adr"
    if not base.is_dir():
        raise FactsError(f"adr directory missing: {base}")
    return sum(1 for _ in base.glob("[0-9][0-9][0-9][0-9]-*.md"))


#: name → deriver; the contract names the target, this table supplies it.
DERIVERS: dict[str, Any] = {
    "mcp_tools": mcp_tools,
    "cli_groups": cli_groups,
    "validation_scenarios": validation_scenarios,
    "tests": tests,
    "demo_domains": demo_domains,
    "delivery_channels": delivery_channels,
    "llm_required_tools": llm_required_tools,
    "adr_count": adr_count,
}


def derive_all(contract: Contract) -> dict[str, Any]:
    """Derive every fact the contract declares, in contract declaration order.

    The result is the 8-section facts tree. A contract fact without a local
    deriver is a contract/implementation mismatch — FactsError (exit 2 class),
    never a silent partial artifact.
    """
    tree: dict[str, Any] = {}
    for name in contract.facts:
        deriver = DERIVERS.get(name)
        if deriver is None:
            raise FactsError(f"contract fact {name!r} has no deriver in gov.facts.DERIVERS")
        tree[name] = deriver()
    return tree


def flatten(facts: dict[str, Any]) -> dict[str, int]:
    """Map dotted paths ('validation_scenarios.total') to leaf ints."""
    flat: dict[str, int] = {}
    for name, value in facts.items():
        if isinstance(value, dict):
            for leaf, leaf_value in value.items():
                flat[f"{name}.{leaf}"] = int(leaf_value)
        else:
            flat[name] = int(value)
    return flat


def check(root: Path | None = None) -> dict[str, Any]:
    """facts_parity gate instrument: derive + full-repo scan (used by `gov check`).

    Lazy-imports scan/artifacts so this module stays importable standalone.
    """
    from autoinfo.gov import artifacts, scan
    from autoinfo.gov.contract import load

    contract = load(root)
    facts = derive_all(contract)
    result = scan.scan_markdown(contract, facts)
    return {
        "fail": len(result.violations),
        "stale": 0,
        "unexplained_not_run": 0,
        "violations": list(result.violations),
        "files_scanned": result.files_scanned,
        "facts": facts,
        "flat_facts": flatten(facts),
        "input_hash": artifacts.input_hash(contract.version, facts),
        "contract_version": contract.version,
        "generator_version": artifacts.GENERATOR_VERSION,
    }


__all__ = [
    "DERIVERS",
    "FactsError",
    "adr_count",
    "check",
    "cli_groups",
    "delivery_channels",
    "demo_domains",
    "derive_all",
    "flatten",
    "llm_required_tools",
    "mcp_tools",
    "tests",
    "validation_scenarios",
]
