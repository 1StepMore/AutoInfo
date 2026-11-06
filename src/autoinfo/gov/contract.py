"""Load + validate the governance contract (T02).

The contract (``.github/governance-contract.toml``) is the single
machine-readable authority: authority order, derived facts, scan rules, gates,
profiles, decisions, platform, conflicts. ``gov contract check`` verifies its
structure AND that every ``module:function`` reference is really importable —
a contract typo must fail here, not at first use (§8.5).
"""

from __future__ import annotations

import importlib
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONTRACT_REL = Path(".github") / "governance-contract.toml"

#: Version of the gov generator code itself (distinct from [meta].version —
#: both feed input_hash so artifact consumers can detect either drift).
GENERATOR_VERSION = "1.0.0"

#: Authority pseudo-entry that always wins; anything unclassified is last.
RUNTIME_AUTHORITY = "runtime:src+derived_facts"

#: Status states (8-enum; plan §2). There is no ``unknown``.
STATES = (
    "PASS",
    "FAIL",
    "NOT_RUN",
    "STALE",
    "UNMEASURED",
    "ADVISORY",
    "UNCONFIGURED",
    "DEGRADED",
)

#: Evidence fields a PASS must carry (plan §2 judgment 1).
EVIDENCE_FIELDS = ("run_id", "commit_sha", "input_hash", "ts")


class ContractError(Exception):
    """The contract is missing or unparsable — an environment error (exit 2)."""


@dataclass(frozen=True)
class MatchSpec:
    """One pattern + the dotted fact paths its capture groups feed."""

    pattern: re.Pattern[str]
    expects: tuple[str, ...]


@dataclass(frozen=True)
class FactSpec:
    name: str
    derive: str
    matches: tuple[MatchSpec, ...]


@dataclass(frozen=True)
class ExcludeSpec:
    path: str
    reason: str


@dataclass(frozen=True)
class DecisionSpec:
    adr: str
    consumers: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class Contract:
    root: Path
    raw: dict[str, Any]
    version: int
    authority_order: tuple[str, ...]
    facts: dict[str, FactSpec]
    ignore_marker: str
    excludes: tuple[ExcludeSpec, ...]
    gates: dict[str, dict[str, Any]]
    profiles: dict[str, dict[str, list[str]]]
    decisions: dict[str, DecisionSpec]
    platform: dict[str, Any]
    conflicts: dict[str, Any]
    scripts: dict[str, Any] = field(default_factory=dict)


def resolve_repo_root() -> Path:
    """Walk up from CWD (then from this file) to the dir holding the contract.

    Raises ContractError when no repo root can be established — callers map
    that to exit 2 (environment error), never to a drift verdict.
    """
    for start in (Path.cwd(), Path(__file__).resolve()):
        for candidate in (start, *start.parents):
            if (candidate / CONTRACT_REL).is_file():
                return candidate
    raise ContractError(
        f"governance contract not found: walked up from {Path.cwd()} looking for "
        f"{CONTRACT_REL.as_posix()} — run from the repository root"
    )


def load_raw(root: Path | None = None) -> dict[str, Any]:
    """Parse the contract TOML; raise ContractError on missing/broken file."""
    if root is None:
        root = resolve_repo_root()
    path = root / CONTRACT_REL
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError as exc:
        raise ContractError(f"governance contract missing: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ContractError(f"governance contract unparsable: {path}: {exc}") from exc


def _parse_match(raw_pattern: str, expects: list[str], fact: str) -> MatchSpec:
    if not expects:
        raise ContractError(f"[facts.{fact}] match has empty expects")
    try:
        compiled = re.compile(raw_pattern)
    except re.error as exc:
        raise ContractError(f"[facts.{fact}] pattern does not compile: {exc}") from exc
    return MatchSpec(pattern=compiled, expects=tuple(expects))


def _parse_fact(name: str, body: dict[str, Any]) -> FactSpec:
    derive = body.get("derive")
    if not derive or not isinstance(derive, str):
        raise ContractError(f"[facts.{name}] missing 'derive' (module:function)")
    matches: list[MatchSpec] = []
    if "pattern" in body:
        expects = body.get("expects", [])
        if not isinstance(expects, list):
            raise ContractError(f"[facts.{name}] expects must be a list")
        matches.append(_parse_match(str(body["pattern"]), [str(e) for e in expects], name))
    for extra in body.get("match", []):
        pattern = str(extra.get("pattern", ""))
        expects = [str(e) for e in extra.get("expects", [])]
        matches.append(_parse_match(pattern, expects, name))
    if not matches:
        raise ContractError(f"[facts.{name}] has no pattern/match")
    return FactSpec(name=name, derive=derive, matches=tuple(matches))


def _parse_decisions(raw: dict[str, Any]) -> dict[str, DecisionSpec]:
    decisions: dict[str, DecisionSpec] = {}
    for name, body in raw.items():
        if not isinstance(body, dict):
            continue
        consumers = tuple(
            {str(k): str(v) for k, v in entry.items()} for entry in body.get("consumers", [])
        )
        decisions[name] = DecisionSpec(adr=str(body.get("adr", "")), consumers=consumers)
    return decisions


def from_raw(root: Path, raw: dict[str, Any]) -> Contract:
    """Build a Contract, raising ContractError on structural problems."""
    meta = raw.get("meta", {})
    authority = raw.get("authority", {}).get("order", [])
    facts_raw = raw.get("facts", {})
    scan = raw.get("scan", {})
    excludes = tuple(
        ExcludeSpec(path=str(e.get("path", "")), reason=str(e.get("reason", "")))
        for e in scan.get("exclude", [])
    )
    profiles = {
        str(name): {
            "allow": [str(a) for a in body.get("allow", [])],
            "deny": [str(d) for d in body.get("deny", [])],
        }
        for name, body in raw.get("profiles", {}).items()
        if isinstance(body, dict)
    }
    gates = {str(k): dict(v) for k, v in raw.get("gates", {}).items() if isinstance(v, dict)}
    if not authority:
        raise ContractError("[authority].order must be a non-empty list")
    if not facts_raw:
        raise ContractError("[facts] must define at least one derived fact")
    if meta.get("version") is None:
        raise ContractError("[meta].version is required")
    return Contract(
        root=root,
        raw=raw,
        version=int(meta["version"]),
        authority_order=tuple(str(a) for a in authority),
        facts={str(k): _parse_fact(str(k), dict(v)) for k, v in facts_raw.items()},
        ignore_marker=str(scan.get("ignore_marker", "counts-ignore")),
        excludes=excludes,
        gates=gates,
        profiles=profiles,
        decisions=_parse_decisions(raw.get("decisions", {})),
        platform=dict(raw.get("platform", {})),
        conflicts=dict(raw.get("conflicts", {})),
        scripts=dict(raw.get("scripts", {})),
    )


def load(root: Path | None = None) -> Contract:
    """Load + structurally parse the contract (no import probing)."""
    if root is None:
        root = resolve_repo_root()
    return from_raw(root, load_raw(root))


def resolve_target(target: str) -> tuple[str, str]:
    """Split a 'module:function' reference; raise ContractError if malformed."""
    module, sep, func = target.partition(":")
    if not sep or not module or not func:
        raise ContractError(f"reference {target!r} is not 'module:function'")
    return module, func


def _importable_target(target: str) -> str | None:
    """Return an error string when a 'module:function' target cannot be used."""
    try:
        module_name, func_name = resolve_target(target)
    except ContractError as exc:
        return str(exc)
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        return f"{target}: import failed ({exc})"
    if not callable(getattr(module, func_name, None)):
        return f"{target}: {module_name}.{func_name} is not callable"
    return None


def validate(contract: Contract) -> list[str]:
    """Semantic validation — returns human-readable errors (empty = valid).

    Checks (T02 acceptance): derive targets importable + callable; gate sources
    reachable (or a declared file for budget gates); every scan exclusion
    carries a reason; profile key sets match across profiles; each decision's
    ADR file exists.
    """
    errors: list[str] = []
    for fact in contract.facts.values():
        err = _importable_target(fact.derive)
        if err:
            errors.append(f"[facts.{fact.name}] {err}")

    for gate_id, gate in contract.gates.items():
        source = gate.get("source")
        if not source:
            errors.append(f"[gates.{gate_id}] missing source")
            continue
        raw_source = str(source)
        # 'path#anchor' names a step inside a file (e.g. a CI job/step); the
        # anchor is documentation — existence is judged on the file part.
        file_part = raw_source.split("#", 1)[0]
        if "/" in file_part or file_part.endswith((".md", ".yml", ".yaml", ".sh", ".toml")):
            if not (contract.root / file_part).is_file():
                errors.append(f"[gates.{gate_id}] source file missing: {file_part}")
        else:
            err = _importable_target(raw_source)
            if err:
                errors.append(f"[gates.{gate_id}] {err}")
        if "required" not in gate:
            errors.append(f"[gates.{gate_id}] missing required flag")

    for exc in contract.excludes:
        if not exc.reason.strip():
            errors.append(f"[scan.exclude] {exc.path}: every exclusion needs a reason")
        if not exc.path.strip():
            errors.append("[scan.exclude] entry with empty path")

    # Key-set equality is judged on the RAW declarations: from_raw injects
    # empty defaults, which would silently normalize away a missing field.
    raw_profiles = contract.raw.get("profiles", {})
    profile_keys = {
        str(name): sorted(str(k) for k in body)
        for name, body in raw_profiles.items()
        if isinstance(body, dict)
    }
    key_sets = {tuple(keys) for keys in profile_keys.values()}
    if len(key_sets) > 1:
        errors.append(
            f"[profiles] key sets differ across profiles: {profile_keys} — "
            "all profiles must declare the same fields"
        )

    for name, decision in contract.decisions.items():
        adr_path = contract.root / "docs" / "adr" / f"{decision.adr}-*.md"
        if not decision.adr:
            errors.append(f"[decisions.{name}] missing adr number")
        elif not list(adr_path.parent.glob(adr_path.name)):
            errors.append(f"[decisions.{name}] ADR file missing: docs/adr/{decision.adr}-*.md")

    return errors


def unsynced(contract: Contract) -> list[str]:
    """Decision-consumer sync check (full implementation lands with T10).

    Kept here so `gov contract check` output shape is stable from PR-A; the
    adr module replaces this stub with anchor verification (ADR guard).
    """
    del contract
    return []


def check(root: Path | None = None) -> dict[str, Any]:
    """`gov contract check` payload — load, validate, report."""
    try:
        contract = load(root)
        errors = validate(contract)
    except ContractError as exc:
        return {"valid": False, "errors": [str(exc)], "contract_version": None, "unsynced": None}
    return {
        "valid": not errors,
        "errors": errors,
        "contract_version": contract.version,
        "unsynced": unsynced(contract),
        "facts": sorted(contract.facts),
        "gates": sorted(contract.gates),
        "profiles": sorted(contract.profiles),
        "authority_order": list(contract.authority_order),
    }
