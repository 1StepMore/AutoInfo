"""CLI/MCP parity for the global ``--json`` flag (T-S-07).

Every data-returning CLI group must honour ``autoinfo --json <group> <cmd>``
by emitting the same canonical envelope the MCP tools return:

* ``{"success": true, "data": ...}``
* ``{"success": false, "error": {"code", "message", "actionable"}}``

The adversarial class guarded here is ``misleading_success_output``: a
``--json`` that prints human text (or a bespoke shape) instead of the
envelope.  The parse-and-shape assertion below fails on both.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from autoinfo.cli import _output, app

runner = CliRunner()


def _assert_envelope(stdout: str, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        raise AssertionError(
            f"{label}: --json output is not parseable JSON (misleading_success_output): "
            f"{exc}\n--- stdout ---\n{stdout[:500]}"
        ) from exc
    assert isinstance(payload, dict), f"{label}: envelope must be a JSON object"
    assert "success" in payload, f"{label}: envelope missing 'success': {payload!r}"
    if payload["success"]:
        assert "data" in payload, f"{label}: success envelope missing 'data'"
    else:
        error = payload.get("error")
        assert isinstance(error, dict), f"{label}: error envelope missing 'error' object"
        for key in ("code", "message", "actionable"):
            assert key in error, f"{label}: error envelope missing '{key}'"
    return payload


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermetic cwd + no LLM key; reset the global-json context afterwards."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AUTOINFO_LLM_API_KEY", "")
    # Drop any user-store DB path cached by an earlier test so the
    # ``enduser`` case reads this test's empty temp DB, not a leaked one.
    monkeypatch.setattr("autoinfo.user_store._DB_PATH", None)
    yield
    _output.set_global_json(False)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Initialize a demo project so data-returning commands succeed."""
    result = runner.invoke(app, ["init", "--demo", "medical-research"])
    assert result.exit_code == 0, result.output
    return tmp_path


def _cases(tmp_path: Path) -> list[tuple[str, list[str]]]:
    prev_card = tmp_path / "prev-card.json"
    cur_card = tmp_path / "cur-card.json"
    for path in (prev_card, cur_card):
        path.write_text(
            json.dumps({"batch_id": path.stem, "products": []}),
            encoding="utf-8",
        )
    kg_out = tmp_path / "knowledge-graph.json"
    return [
        ("init", ["init", "--demo", "medical-research"]),
        ("doctor", ["doctor"]),
        ("collect", ["collect", "--domain", "no-such-domain-xyz", "--dry-run"]),
        ("process", ["process", "--domain", "no-such-domain-xyz"]),
        ("status", ["status"]),
        ("summaries", ["summaries", "list", "--domain", "medical-research"]),
        ("sources", ["sources", "list", "--domain", "medical-research"]),
        ("topics", ["topics", "list", "--domain", "medical-research"]),
        (
            "topic-group",
            [
                "topic-group",
                "add",
                "--domain",
                "medical-research",
                "--group",
                "g",
                "--topic",
                "nope",
            ],
        ),
        ("domain", ["domain", "list"]),
        ("audit", ["audit", "query", "--limit", "1"]),
        ("kb", ["kb", "list", "--domain", "medical-research", "--tier", "01-Raw"]),
        ("output", ["output", "list-templates"]),
        ("cron", ["cron", "list-schedules"]),
        (
            "knowledge",
            [
                "knowledge",
                "graph",
                "export",
                "--domain",
                "medical-research",
                "--output",
                str(kg_out),
            ],
        ),
        ("cefr", ["cefr", "classify", "hello", "--lang", "en"]),
        ("email", ["email", "config"]),
        ("keywords", ["keywords", "list", "--domain", "medical-research"]),
        ("clean", ["clean", "--collections", "--dry-run"]),
        ("cost", ["cost", "dashboard", "--period", "week"]),
        ("billing", ["billing", "summary", "--user-id", "parity-user"]),
        ("enduser", ["enduser", "list"]),
        ("portal", ["portal", "history", "--user", "parity-user"]),
        ("trace", ["trace", "deadbeef"]),
        (
            "import-kb",
            ["import-kb", "--domain", "medical-research", "--format", "json", "--data", "[]"],
        ),
        (
            "query-collected",
            ["query-collected", "--query", "q", "--domain", "medical-research"],
        ),
        ("alert-rules", ["alert-rules", "list"]),
        ("agent-callback", ["agent-callback", "list"]),
        ("validation", ["validation", "list"]),
        ("validate", ["validate", "diff", str(prev_card), str(cur_card)]),
        ("mvp", ["mvp", "list"]),
    ]


def test_global_json_emits_canonical_envelope_for_every_group(
    project: Path, tmp_path: Path
) -> None:
    """One representative data-returning command per group, run with global --json."""
    failures: list[str] = []
    for label, args in _cases(tmp_path):
        result = runner.invoke(app, ["--json", *args])
        try:
            _assert_envelope(result.stdout, label)
        except AssertionError as exc:
            failures.append(f"{label} (exit={result.exit_code}): {exc}")
    assert not failures, "\n\n".join(failures)


def test_global_json_error_path_is_envelope_not_traceback() -> None:
    """A config-less run still yields the canonical error envelope."""
    result = runner.invoke(app, ["--json", "domain", "list"])
    payload = _assert_envelope(result.stdout, "domain-list-no-config")
    assert payload["success"] is False
    assert payload["error"]["code"] == "ConfigNotFound"
    assert payload["error"]["actionable"] is True


def test_llm_commands_degrade_to_error_envelope_without_key() -> None:
    """LLM-required commands report a graceful envelope, never a raw traceback."""
    result = runner.invoke(
        app,
        [
            "--json",
            "query-collected",
            "--query",
            "anything",
            "--domain",
            "medical-research",
        ],
    )
    payload = _assert_envelope(result.stdout, "query-collected-no-key")
    assert payload["success"] is False
    assert payload["error"]["code"] == "LLMNotConfigured"


def test_local_json_flag_shape_is_untouched(project: Path) -> None:
    """The per-command --json keeps its historical (non-envelope) shape."""
    result = runner.invoke(app, ["domain", "list", "--json"])
    payload = json.loads(result.stdout)
    assert payload["domains"] == [] or "count" in payload
    assert "success" not in payload


def test_usage_error_emits_envelope() -> None:
    """Issue #242(a): a subcommand usage error must honour global --json.

    Click raises this after the root callback ran (so the ContextVar is
    already True), but the bare ``app()`` call previously let Typer print the
    rich usage block and exit 2 with empty stdout.
    """
    result = runner.invoke(app, ["--json", "cost", "dashboard", "--days", "abc"])
    payload = _assert_envelope(result.stdout, "usage-error")
    assert payload["success"] is False
    assert payload["error"]["code"] == "ValidationError"
    assert result.exit_code == 2


def test_unknown_command_emits_envelope() -> None:
    """Issue #242(a): an unknown *top-level* command must honour global --json.

    ``Group.invoke`` resolves the command *before* the root callback runs, so
    the ContextVar is still False here — the argv leading-scan is what detects
    ``--json`` and drives the envelope.
    """
    result = runner.invoke(app, ["--json", "bogus-cmd"])
    payload = _assert_envelope(result.stdout, "unknown-command")
    assert payload["success"] is False
    assert payload["error"]["code"] == "ValidationError"
    assert result.exit_code == 2


def test_uncaught_internal_error_emits_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #242(a): an uncaught exception under global --json is enveloped."""

    def _boom() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("autoinfo.cli.domain._load", _boom)
    result = runner.invoke(app, ["--json", "domain", "list"])
    payload = _assert_envelope(result.stdout, "internal-error")
    assert payload["success"] is False
    assert payload["error"]["code"] == "InternalError"
    assert result.exit_code == 1


def test_usage_error_without_json_is_unchanged() -> None:
    """Issue #242(a): the non-json path keeps Click's usage output + exit 2."""
    result = runner.invoke(app, ["cost", "dashboard", "--days", "abc"])
    assert result.exit_code == 2
    assert result.stdout == ""
