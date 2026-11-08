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


def _print(payload: dict[str, Any], as_json: bool) -> None:
    """Emit the payload: one JSON line for --json, readable text otherwise.

    JSON goes through ``sys.stdout.buffer`` in binary: text mode translates
    newlines to CRLF on Windows and would break the cross-platform sha256
    comparison of redirected ``derive --all --json`` output (DoD #5).
    """
    if as_json:
        line = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        sys.stdout.buffer.write((line + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()
        return
    for key, value in payload.items():
        if isinstance(value, list):
            print(f"{key}:")
            for item in value:
                print(f"  - {item}")
        else:
            print(f"{key}: {value}")


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
    from autoinfo.gov.contract import ContractError, load

    try:
        data = facts_mod.check()
        contract = load()
    except (ContractError, facts_mod.FactsError) as exc:
        return (
            _env_error(str(exc), "run from the repo root with the project venv interpreter"),
            EXIT_ENV,
        )
    clean = data["fail"] == 0 and data["stale"] == 0 and data["unexplained_not_run"] == 0
    rc = EXIT_OK if clean else EXIT_RED
    data["generator_version"] = artifacts.GENERATOR_VERSION
    if args.write_evidence:
        data["parity_evidence"] = (
            artifacts.write_parity_evidence(
                contract.root,
                contract.version,
                data["facts"],
                {
                    key: data[key]
                    for key in ("fail", "stale", "unexplained_not_run", "files_scanned")
                },
            ).as_posix()
            if clean
            else None
        )
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
        simulate=args.simulate,
    )
    return report, status_mod.exit_code(report)


def cmd_run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from autoinfo.gov import artifacts, policy
    from autoinfo.gov.contract import ContractError, load

    try:
        contract = load()
    except ContractError as exc:
        return _env_error(str(exc), "run from the repository root"), EXIT_ENV
    log_dir = artifacts.artifact_dir(contract.root)
    if args.diff_profiles:
        diffs = policy.diff_profiles(contract.profiles)
        data: dict[str, Any] = {"diff": diffs, "profiles": sorted(contract.profiles)}
        return data, EXIT_OK if not diffs else EXIT_RED
    if not args.mode or not args.probe:
        return (
            _env_error(
                "run needs --mode <profile> --probe <action> (or --diff-profiles)",
                "e.g. run --mode cloud --probe git:push-protected --json",
            ),
            EXIT_ENV,
        )
    decision = policy.decide(contract.profiles, args.mode, args.probe, log_dir=log_dir)
    rc = EXIT_OK if decision["allowed"] else EXIT_RED
    return decision, rc


def cmd_negative_control(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from autoinfo.gov import negative_control as negctl
    from autoinfo.gov.contract import ContractError, load

    try:
        contract = load()
    except ContractError as exc:
        return _env_error(str(exc), "run from the repository root"), EXIT_ENV
    data = negctl.run_all(contract.root, only=args.case)
    rc = EXIT_OK if data["all_three_evidences"] else EXIT_RED
    return data, rc


def cmd_confidence(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from autoinfo.gov import confidence as confidence_mod
    from autoinfo.gov.contract import ContractError

    del args
    try:
        data = confidence_mod.confidence()
    except ContractError as exc:
        return _env_error(str(exc), "run from the repository root"), EXIT_ENV
    rc = EXIT_OK if data["overall"] == "E3" else EXIT_RED
    return data, rc


def cmd_scripts(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from autoinfo.gov import registry as registry_mod
    from autoinfo.gov.contract import ContractError, load

    del args
    try:
        contract = load()
        data = registry_mod.registry_report(contract)
    except (ContractError, RuntimeError) as exc:
        return _env_error(str(exc), "run from the repository root"), EXIT_ENV
    rc = EXIT_OK if not data["unregistered"] else EXIT_RED
    return data, rc


def cmd_escalate(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from autoinfo.gov import escalate as escalate_mod
    from autoinfo.gov import sources
    from autoinfo.gov.contract import ContractError, load

    try:
        contract = load()
    except ContractError as exc:
        return _env_error(str(exc), "run from the repository root"), EXIT_ENV
    if args.pending:
        open_items = escalate_mod.pending(contract.root)
        data: dict[str, Any] = {"pending": open_items, "count": len(open_items)}
        rc = EXIT_RED if any(e["escalation"]["state"] == "OVERDUE" for e in open_items) else EXIT_OK
        return data, rc
    if not args.item:
        return (
            _env_error(
                "escalate needs --item <id> (or --pending)",
                "e.g. escalate --item acceptance-1.21.17",
            ),
            EXIT_ENV,
        )
    try:
        record = escalate_mod.escalate(
            contract,
            item=args.item,
            role=args.role,
            channel=args.channel,
            deadline=args.deadline,
        )
    except escalate_mod.EscalationError as exc:
        return {
            "success": False,
            "error": {
                "code": "ESCALATION_REFUSED",
                "message": str(exc),
                "actionable": "route to a human receiver role",
            },
        }, EXIT_ENV
    gate_raw = sources.read_gate("escalations", contract, {})
    record["gate"] = {"id": "escalations", "state": gate_raw["state"], "reason": gate_raw["reason"]}
    overdue = record["escalation"]["state"] == "OVERDUE"
    rc = EXIT_RED if overdue or gate_raw["state"] == "FAIL" else EXIT_OK
    return record, rc


def cmd_acceptance(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from autoinfo.gov import acceptance as acceptance_mod

    del args
    try:
        data = acceptance_mod.check()
    except (FileNotFoundError, ImportError, ValueError) as exc:
        return _env_error(str(exc), "run from the repository root"), EXIT_ENV
    return data, EXIT_OK if data["success"] else EXIT_RED


def cmd_adr(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from autoinfo.gov.adr import check as adr_check
    from autoinfo.gov.contract import ContractError, load

    del args
    try:
        contract = load()
    except ContractError as exc:
        return _env_error(str(exc), "run from the repository root"), EXIT_ENV
    data = adr_check(contract.root, contract)
    data["success"] = not data["errors"] and not data["unsynced"]
    rc = EXIT_OK if data["success"] else EXIT_RED
    return data, rc


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
    check.add_argument(
        "--write-evidence",
        action="store_true",
        help="on a clean check, write .autoinfo/gov/derived-parity.json for the parity gate",
    )
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

    adr = sub.add_parser("adr", help="ADR guard + decision consumer sync (T10)")
    adr.add_argument("action", choices=["check"], help="only 'check' for now")
    adr.add_argument("--json", action="store_true", help="emit one JSON line")
    adr.set_defaults(func=cmd_adr)

    escalate = sub.add_parser("escalate", help="route a human decision (receiver+deadline, T12)")
    escalate.add_argument("--item", help="escalation item id, e.g. acceptance-1.21.17")
    escalate.add_argument(
        "--role", default="human.director", help="receiver role (never executor.profile)"
    )
    escalate.add_argument("--channel", default="github-issue", help="receiver channel")
    escalate.add_argument("--deadline", help="ISO-8601 deadline (default: now+7d)")
    escalate.add_argument("--pending", action="store_true", help="list open escalations")
    escalate.add_argument("--json", action="store_true", help="emit one JSON line")
    escalate.set_defaults(func=cmd_escalate)

    acceptance = sub.add_parser("acceptance", help="acceptance-instrument bridge check (T12)")
    acceptance.add_argument("--json", action="store_true", help="emit one JSON line")
    acceptance.set_defaults(func=cmd_acceptance)

    negctl = sub.add_parser(
        "negative-control", help="break -> red -> restore -> green harness (T17)"
    )
    negctl.add_argument("--all", action="store_true", help="run every case")
    negctl.add_argument("--case", help="run a single case id")
    negctl.add_argument("--json", action="store_true", help="emit one JSON line")
    negctl.set_defaults(func=cmd_negative_control)

    confidence = sub.add_parser("confidence", help="E2/E3 confidence grading (T17)")
    confidence.add_argument("--json", action="store_true", help="emit one JSON line")
    confidence.set_defaults(func=cmd_confidence)

    scripts = sub.add_parser("scripts", help="scripts/ registry report (T14)")
    scripts.add_argument("--json", action="store_true", help="emit one JSON line")
    scripts.set_defaults(func=cmd_scripts)

    run = sub.add_parser("run", help="profile probe runner — policy decision only (T15)")
    run.add_argument("--mode", help="profile name (cloud|local)")
    run.add_argument("--probe", help="probe id, e.g. git:push-protected")
    run.add_argument("--diff-profiles", action="store_true")
    run.add_argument("--json", action="store_true", help="emit one JSON line")
    run.set_defaults(func=cmd_run)

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
    if func is None:  # unreachable today: every verb has a handler
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
