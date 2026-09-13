# mypy: ignore-errors
"""Error-message audit tests (D-工-4 evidence, best-practice-review).

Locks the behavior of ``scripts/error_message_audit.py`` so the D-工-4
evidence the best-practice review depends on stays deterministic:

1. All error envelope call sites in ``server.py`` are parsed (116 sites:
   error_response / error_dict / _error_from_exc).
2. **Actionability** — every explicit-message site (``error_response`` /
   ``error_dict``) carries a fix hint; the strong claim that
   ``no_fix_hint_sites == 0`` is the regression floor.
3. **No raw-exception leakage** — the legacy ``_error_dict(exc)`` (message
   == ``str(exc)``) is gone; the ``_error_from_exc(exc, context)`` helper
   replaces it with a context + template-hint message. Detection covers the
   **keyword** form (``message=str(exc)``) *and* the **positional** form
   (``error_response(ErrorCode.X, str(exc), ...)``) — the false-GREEN
   (T-S-06 / VT-08) that the audit used to miss. The floor
   ``raw_exception_sites == 0`` and ``from_exc_missing_context == 0`` lock
   the fix in place; ``helper_template_ok`` pins the template-level hint.
4. **429 Retry-After** — RATE_LIMITED call sites should carry a retry /
   backoff hint; the audit reports them (0 today — rate limiting is not
   surfaced through the MCP error envelope).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SERVER_SRC = ROOT / "src" / "autoinfo" / "mcp" / "server.py"
AUDIT_SCRIPT = ROOT / "scripts" / "error_message_audit.py"

PLANTED_POSITIONAL_RAW = (
    "def _h(exc):\n    return error_response(ErrorCode.INTERNAL_ERROR, str(exc), actionable=True)\n"
)
PLANTED_KEYWORD_RAW = (
    "def _h(exc):\n"
    "    return error_response(code=ErrorCode.INTERNAL_ERROR, "
    "message=str(exc), actionable=True)\n"
)
CLEAN_FROM_EXC = 'def _h(exc):\n    return _error_from_exc(exc, "operation failed")\n'


@pytest.fixture(scope="module")
def error_audit():
    spec = importlib.util.spec_from_file_location("error_message_audit", AUDIT_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def result(error_audit):
    return error_audit.audit_errors(SERVER_SRC.read_text(encoding="utf-8"))


def test_all_error_sites_parsed(result):
    # VT-05: no exact site count is pinned — the plan's own work adds error
    # sites (the get_coverage_report handler was the 117th). The invariant is
    # structural: every parsed site belongs to a known kind and the parsed
    # count agrees with the per-kind tally.
    from collections import Counter

    kinds = Counter(s["call"] for s in result["sites"])
    assert set(kinds) <= {
        "error_response",
        "error_dict",
        "_error_dict",
        "_error_from_exc",
    }
    assert sum(kinds.values()) == result["total_sites"]
    assert result["total_sites"] > 0


def test_call_site_kind_breakdown(result):
    from collections import Counter

    kinds = Counter(s["call"] for s in result["sites"])
    # The legacy raw-exception helper must stay fully retired (todo-2 floor);
    # the two active explicit-message kinds must both be present. Exact
    # per-kind counts are intentionally NOT pinned — the plan adds sites.
    assert kinds["_error_dict"] == 0
    assert kinds["error_response"] > 0
    assert kinds["_error_from_exc"] > 0
    assert sum(kinds.values()) == result["total_sites"]


def test_every_explicit_message_has_fix_hint(result):
    # The strong D-工-4 claim: no explicit-message site lacks a fix hint.
    assert result["summary"]["no_fix_hint_sites"] == 0


def test_no_raw_exception_sites(result):
    # D-工-4 fixed: _error_dict(exc) → raw str(exc) is gone. Any future
    # reintroduction (or a new _error_dict call site) fails this floor.
    assert result["summary"]["raw_exception_sites"] == 0
    assert result["violations"]["raw_exception"] == []


def test_raw_exception_lines_match_raw_producing_calls(result):
    raw = result["violations"]["raw_exception"]
    by_line = {s["line"]: s["call"] for s in result["sites"]}
    for line in raw:
        assert by_line[line] in (
            "_error_dict",
            "error_response",
            "error_dict",
        ), line


def test_planted_positional_raw_exception_is_flagged(error_audit):
    # RED→GREEN: the old audit only scanned keyword message=, so this
    # positional str(exc) site reported 0 raw sites. It must now be caught.
    result = error_audit.audit_errors(PLANTED_POSITIONAL_RAW)
    assert result["summary"]["raw_exception_sites"] == 1
    assert result["violations"]["raw_exception"] == [2]
    assert result["summary"]["no_fix_hint_sites"] == 1


def test_planted_keyword_raw_exception_is_flagged(error_audit):
    result = error_audit.audit_errors(PLANTED_KEYWORD_RAW)
    assert result["summary"]["raw_exception_sites"] == 1
    assert result["violations"]["raw_exception"] == [result["sites"][0]["line"]]


def test_non_exception_str_call_is_not_flagged(error_audit):
    # str(arguments.get(...)) is not an exception; must not be a false hit.
    src = (
        "def _h(arguments):\n"
        "    return error_response(code=ErrorCode.INTERNAL_ERROR, "
        'message=str(arguments.get("message", "x")), actionable=True)\n'
    )
    result = error_audit.audit_errors(src)
    assert result["summary"]["raw_exception_sites"] == 0


def test_main_exits_nonzero_on_planted_raw_site(error_audit, tmp_path):
    target = tmp_path / "server.py"
    target.write_text(PLANTED_POSITIONAL_RAW, encoding="utf-8")
    assert error_audit.main([str(target)]) != 0


def test_main_exits_zero_on_clean_from_exc(error_audit, tmp_path):
    target = tmp_path / "server.py"
    target.write_text(CLEAN_FROM_EXC, encoding="utf-8")
    assert error_audit.main([str(target)]) == 0


def test_from_exc_sites_carry_context(result):
    # every _error_from_exc call site must pass a non-empty operation
    # context; a missing context would surface a bare exception again.
    assert result["summary"]["from_exc_missing_context"] == 0
    assert result["violations"]["from_exc_missing_context"] == []


def test_from_exc_helper_template_has_fix_hint(result):
    # the fix hint for _error_from_exc sites lives in the helper template
    # (checked statically), not per call site.
    assert result["summary"]["helper_template_ok"] is True


def test_rate_limited_reporting_shape(result):
    v = result["violations"]["rate_limited_no_retry"]
    assert isinstance(v, list)
    assert result["summary"]["rate_limited_sites"] == 0


def test_sites_sorted_by_line(result):
    lines = [s["line"] for s in result["sites"]]
    assert lines == sorted(lines)
