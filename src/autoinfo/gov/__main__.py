"""The ONLY entry point for governance verbs: ``python -m autoinfo.gov``.

Both platforms run the same command; ``autoinfo gov`` (Typer) and
``scripts/gov.py`` are thin forwards with zero business logic. Exit codes:
0 = green/amber, 1 = red (a gate failed), 2 = schema or environment error —
aligned with scripts/quality_gate.py. ``--force-pass`` is refused everywhere
(hard constraint 6): any occurrence is an exit-2 assertion failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

EXIT_OK = 0
EXIT_RED = 1
EXIT_ENV = 2

#: All verbs (T04: --help must list exactly these 13).
VERBS = (
    "status",
    "derive",
    "check",
    "adjudicate",
    "escalate",
    "run",
    "doctor",
    "acceptance",
    "negative-control",
    "confidence",
    "contract",
    "adr",
    "scripts",
)

#: Verbs implemented in later PRs (plan T09-T17); registered, honestly stubbed.
_LATER_PR: dict[str, str] = {
    "escalate": "T12 (PR-D) — human escalations",
    "run": "T15 (PR-D) — profile probes",
    "acceptance": "T12 (PR-D) — acceptance report instrument",
    "negative-control": "T17 (PR-E) — negative-control harness",
    "confidence": "T17 (PR-E) — E2/E3 confidence grading",
    "adr": "T10 (PR-C) — ADR guard + consumer sync",
    "scripts": "T14 (PR-E) — scripts/ registry",
}


def _print(payload: dict[str, Any], as_json: bool) -> None:
    """Emit the payload: one JSON line for --json, readable text otherwise."""
    if as_json:
        sys.stdout.write(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        )
        return
    for key, value in payload.items():
        if isinstance(value, list):
            print(f"{key}:")
            for item in value:
                print(f"  - {item}")
        else:
            print(f"{key}: {value}")


def _stub(verb: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": "NOT_IMPLEMENTED_YET",
            "message": f"verb {verb!r} lands in {_LATER_PR.get(verb, 'a later PR')}",
            "actionable": "track the plan: deliverables/software-company/"
            "autoinfo-governance-remediation-2026-11-06.md",
        },
    }


def _env_error(message: str, actionable: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": {"code": "ENVIRONMENT", "message": message, "actionable": actionable},
    }


def cmd_contract(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from autoinfo.gov import contract as contract_mod

    data = contract_mod.check()
    rc = EXIT_OK if data.get("valid") else EXIT_RED
    return data, rc


def cmd_derive(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from autoinfo.gov import artifacts
    from autoinfo.gov import facts as facts_mod
    from autoinfo.gov.contract import ContractError, load

    try:
        contract = load()
        facts = facts_mod.derive_all(contract)
    except (ContractError, facts_mod.FactsError) as exc:
        return (
            _env_error(str(exc), "run from the repo root with the project venv interpreter"),
            EXIT_ENV,
        )
    payload: dict[str, Any] = {
        "contract_version": contract.version,
        "generator_version": artifacts.GENERATOR_VERSION,
        "input_hash": artifacts.input_hash(contract.version, facts),
        "facts": facts,
    }
    if args.write:
        facts_path, evidence_path = artifacts.write_artifacts(
            contract.root, contract.version, facts
        )
        payload["written"] = [facts_path.as_posix(), evidence_path.as_posix()]
    return payload, EXIT_OK


def cmd_check(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from autoinfo.gov import artifacts
    from autoinfo.gov import facts as facts_mod
    from autoinfo.gov.contract import ContractError

    del args
    try:
        data = facts_mod.check()
    except (ContractError, facts_mod.FactsError) as exc:
        return (
            _env_error(str(exc), "run from the repo root with the project venv interpreter"),
            EXIT_ENV,
        )
    clean = data["fail"] == 0 and data["stale"] == 0 and data["unexplained_not_run"] == 0
    rc = EXIT_OK if clean else EXIT_RED
    data["generator_version"] = artifacts.GENERATOR_VERSION
    return data, rc


def cmd_adjudicate(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from autoinfo.gov import adjudicate as adj
    from autoinfo.gov.contract import ContractError, load

    try:
        contract = load()
        data = adj.adjudicate(contract, args.fact, args.candidates)
    except (ContractError, ValueError) as exc:
        return (
            _env_error(str(exc), "pass --fact <name> --candidates 'src=value,...'"),
            EXIT_ENV,
        )
    return data, EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from autoinfo.gov import doctor as doctor_mod
    from autoinfo.gov.contract import ContractError, resolve_repo_root

    del args
    try:
        root = resolve_repo_root()
    except ContractError as exc:
        return _env_error(str(exc), "run from the repository root"), EXIT_ENV
    data = doctor_mod.doctor(root)
    return data, EXIT_OK


def cmd_status(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from autoinfo.gov import artifacts
    from autoinfo.gov import facts as facts_mod
    from autoinfo.gov import status as status_mod
    from autoinfo.gov.contract import ContractError, load

    try:
        contract = load()
        facts = facts_mod.derive_all(contract)
    except (ContractError, facts_mod.FactsError) as exc:
        return (
            _env_error(str(exc), "run from the repo root with the project venv interpreter"),
            EXIT_ENV,
        )
    report = status_mod.status(
        contract,
        facts | {"_input_hash": artifacts.input_hash(contract.version, facts)},
        only=args.only,
    )
    return report, status_mod.exit_code(report)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m autoinfo.gov",
        description="AutoInfo governance verbs (single entry point; plan 2026-11-06).",
    )
    sub = parser.add_subparsers(dest="verb", required=True, metavar="<verb>")

    derive = sub.add_parser("derive", help="derive the 8 governance facts from code")
    derive.add_argument("--all", action="store_true", help="derive every contract fact")
    derive.add_argument("--json", action="store_true", help="emit one JSON line")
    derive.add_argument(
        "--write", action="store_true", help="also write facts.json/evidence.json artifacts"
    )
    derive.set_defaults(func=cmd_derive)

    check = sub.add_parser("check", help="full-repo drift check against derived facts")
    check.add_argument("--json", action="store_true", help="emit one JSON line")
    check.set_defaults(func=cmd_check)

    adjudicate = sub.add_parser("adjudicate", help="resolve a fact dispute via the authority order")
    adjudicate.add_argument("--fact", required=True, help="fact name, e.g. mcp_tools")
    adjudicate.add_argument("--candidates", required=True, help="'README.md=151,OTHER.md=999'")
    adjudicate.add_argument("--json", action="store_true", help="emit one JSON line")
    adjudicate.set_defaults(func=cmd_adjudicate)

    contract = sub.add_parser("contract", help="contract self-check (incl. ADR consumer sync)")
    contract.add_argument("action", choices=["check"], help="only 'check' for now")
    contract.add_argument("--json", action="store_true", help="emit one JSON line")
    contract.set_defaults(func=cmd_contract)

    doctor = sub.add_parser("doctor", help="platform/environment diagnostics (read-only)")
    doctor.add_argument("--json", action="store_true", help="emit one JSON line")
    doctor.set_defaults(func=cmd_doctor)

    status_cmd = sub.add_parser("status", help="8-state status model over every contract gate")
    status_cmd.add_argument("--json", action="store_true", help="emit one JSON line")
    status_cmd.add_argument("--only", help="restrict the report to one gate id")
    status_cmd.add_argument(
        "--simulate",
        choices=["offline", "no-service", "no-key"],
        help="degraded-environment simulation (lands in T16)",
    )
    status_cmd.set_defaults(func=cmd_status)

    stub_verbs = (
        "escalate",
        "acceptance",
        "negative-control",
        "confidence",
        "adr",
        "scripts",
    )
    for verb in stub_verbs:
        stub = sub.add_parser(verb, help=f"lands in {_LATER_PR[verb]}")
        stub.add_argument("--json", action="store_true", help="emit one JSON line")
        stub.set_defaults(func=None)

    run = sub.add_parser("run", help="profile probe runner (lands in T15)")
    run.add_argument("--mode", help="profile name (cloud|local)")
    run.add_argument("--probe", help="probe id, e.g. git:push-protected")
    run.add_argument("--diff-profiles", action="store_true")
    run.add_argument("--json", action="store_true", help="emit one JSON line")
    run.set_defaults(func=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    raw = list(argv) if argv is not None else sys.argv[1:]
    as_json = "--json" in raw
    parser = build_parser()
    args, extras = parser.parse_known_args(raw)
    if "--force-pass" in raw or "--force-pass" in extras:
        # Hard constraint 6 — the flag does not exist anywhere; refuse, exit 2.
        _print(
            {
                "success": False,
                "error": {
                    "code": "FORCE_PASS_REFUSED",
                    "message": "--force-pass does not exist in this governance stack; "
                    "a gate that would fail must fail",
                    "actionable": "fix the underlying gate instead (plan hard constraint 6)",
                },
            },
            as_json,
        )
        return EXIT_ENV
    if extras:
        _print(
            _env_error(f"unrecognized arguments: {' '.join(extras)}", "see --help for verb usage"),
            as_json,
        )
        return EXIT_ENV

    func = getattr(args, "func", None)
    if func is None:
        _print(_stub(args.verb), as_json)
        return EXIT_ENV

    try:
        result = func(args)
    except Exception as exc:  # noqa: BLE001 — the CLI must never traceback at a user
        _print(
            _env_error(f"{type(exc).__name__}: {exc}", "re-run with the project venv interpreter"),
            as_json,
        )
        return EXIT_ENV
    payload, rc = result
    _print(payload, as_json)
    return int(rc)


if __name__ == "__main__":
    sys.exit(main())
