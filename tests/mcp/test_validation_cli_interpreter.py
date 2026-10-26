"""Interpreter portability and cleanup-visibility guards for scenario steps (#622).

Scenario CLI steps historically ran a bare ``python3`` through ``shell=True``,
so the step depended on whatever interpreter PATH resolved to — not the venv
running the MCP server that imports ``autoinfo``.  These tests pin the engine
contract (rewrite command-position python commands to ``sys.executable``) and
the reporting contract (a failed cleanup step is surfaced, never silent).
"""

from __future__ import annotations

import shlex
import sys

from autoinfo.mcp.validation import (
    _cleanup_failure_summary,
    _resolve_cli_interpreter,
    _run_cli_step,
)
from autoinfo.output.run_report import build_run_report

QUOTED_EXECUTABLE = shlex.quote(sys.executable)


def test_resolve_rewrites_command_position_python3() -> None:
    assert _resolve_cli_interpreter("python3 -c 'print(1)'") == (
        f"{QUOTED_EXECUTABLE} -c 'print(1)'"
    )


def test_resolve_rewrites_chained_commands_and_versioned_names() -> None:
    resolved = _resolve_cli_interpreter("cd /tmp && python3.11 -m pytest")
    assert resolved == f"cd /tmp && {QUOTED_EXECUTABLE} -m pytest"


def test_resolve_leaves_argument_position_and_path_qualified_python() -> None:
    assert _resolve_cli_interpreter("echo python3") == "echo python3"
    assert _resolve_cli_interpreter(".venv/bin/python script.py") == ".venv/bin/python script.py"


def test_run_cli_step_uses_the_running_interpreter() -> None:
    result = _run_cli_step("python3 -c 'import sys; print(sys.executable)'", timeout=60)
    assert result["success"] is True
    assert result["data"]["stdout"].strip() == sys.executable


def test_cleanup_failure_summary_exposes_failed_steps() -> None:
    summary = _cleanup_failure_summary(
        [
            {"step_id": "cleanup.1", "name": "remove temp dir", "status": "passed"},
            {
                "step_id": "cleanup.2",
                "name": "delete KB entry",
                "status": "failed",
                "detail": "exit 1: entry not found",
            },
        ]
    )
    assert summary["cleanup_failed"] is True
    assert summary["failed_steps"] == [
        {"step_id": "cleanup.2", "name": "delete KB entry", "detail": "exit 1: entry not found"}
    ]


def test_cleanup_failure_summary_empty_when_all_cleanup_steps_pass() -> None:
    assert _cleanup_failure_summary([{"step_id": "cleanup.1", "status": "passed"}]) == {}


def test_run_report_summary_counts_cleanup_failures() -> None:
    report = build_run_report(
        "session-622",
        [
            {
                "scenario": "leaky",
                "status": "passed",
                "summary": {"recovered": 0},
                "cleanup_failed": True,
                "steps": [],
            },
            {
                "scenario": "clean",
                "status": "passed",
                "summary": {"recovered": 0},
                "steps": [],
            },
        ],
        kind="suite",
        started_at="2026-01-01T00:00:00",
        finished_at="2026-01-01T00:00:01",
    )
    assert report["summary"]["cleanup_failed"] == 1
