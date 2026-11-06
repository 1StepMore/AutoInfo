"""Single-entry-point discipline tests (T04): one implementation, thin aliases."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autoinfo.gov.__main__ import EXIT_ENV, EXIT_OK, VERBS, main

ROOT = Path(__file__).resolve().parents[2]


def test_help_lists_exactly_the_thirteen_verbs() -> None:
    from autoinfo.gov.__main__ import build_parser

    parser = build_parser()
    assert len(VERBS) == 13
    choices: set[str] = set()
    for action in parser._actions:  # noqa: SLF001 — argparse introspection
        if isinstance(action.choices, dict):
            choices |= set(action.choices)
    assert choices == set(VERBS)


def test_force_pass_is_refused_with_exit_2() -> None:
    """Hard constraint 6: the flag does not exist — refusal is exit 2 + code."""
    rc = main(["status", "--json", "--force-pass"])
    assert rc == EXIT_ENV


def test_stub_verbs_fail_honestly() -> None:
    for verb in ("status", "escalate", "negative-control"):
        rc = main([verb, "--json"])
        assert rc == EXIT_ENV, verb


def test_contract_check_verb_is_green() -> None:
    assert main(["contract", "check", "--json"]) == EXIT_OK


def test_adjudicate_verb_json_payload(capsys: object) -> None:  # noqa: ARG001
    rc = main(
        [
            "adjudicate",
            "--fact",
            "mcp_tools",
            "--candidates",
            "README.md=151,CONTRIBUTING.md=999",
            "--json",
        ]
    )
    assert rc == EXIT_OK
    out = getattr(capsys, "readouterr")().out
    payload = json.loads(out.strip().splitlines()[-1])
    assert payload["winner"]["value"] == 151


def test_scripts_gov_py_is_byte_identical() -> None:
    """R4: the bootstrap alias must produce identical bytes to the entry point."""
    proc_a = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoinfo.gov",
            "adjudicate",
            "--fact",
            "mcp_tools",
            "--candidates",
            "README.md=151,CONTRIBUTING.md=999",
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    proc_b = subprocess.run(
        [
            sys.executable,
            "scripts/gov.py",
            "adjudicate",
            "--fact",
            "mcp_tools",
            "--candidates",
            "README.md=151,CONTRIBUTING.md=999",
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert proc_a.returncode == proc_b.returncode == EXIT_OK
    assert proc_a.stdout == proc_b.stdout


def test_cli_gov_forward_is_byte_identical() -> None:
    """T04: `autoinfo gov ...` must equal `python -m autoinfo.gov ...` byte-for-byte."""
    argv = [
        "adjudicate",
        "--fact",
        "mcp_tools",
        "--candidates",
        "README.md=151,CONTRIBUTING.md=999",
        "--json",
    ]
    proc_a = subprocess.run(
        [sys.executable, "-m", "autoinfo.gov", *argv],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    proc_b = subprocess.run(
        [sys.executable, "-m", "autoinfo.cli", "gov", *argv],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert proc_a.returncode == proc_b.returncode == EXIT_OK
    assert proc_a.stdout == proc_b.stdout


def test_unknown_verb_is_argparse_error() -> None:
    import pytest

    with pytest.raises(SystemExit) as excinfo:
        main(["definitely-not-a-verb"])
    assert excinfo.value.code == 2
