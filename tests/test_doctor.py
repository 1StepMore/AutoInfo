"""Tests for the doctor CLI LLM hint (GitHub issue #110)."""

import pytest

from autoinfo.cli.doctor import _print_human


def _result_with_llm_unconfigured() -> dict:
    return {
        "python": {"status": "ok", "version": "3.11.0"},
        "config": {"status": "ok", "path": ".autoinfo/config.yaml"},
        "llm": {
            "status": "error",
            "provider": "openai",
            "model": "gpt-4",
            "key_configured": False,
        },
        "sources": [],
    }


def test_doctor_llm_hint_points_to_mcp_tool(capsys: pytest.CaptureFixture) -> None:
    """The LLM-not-configured hint must mention the real configure_llm() MCP tool.

    Regression: doctor.py used to print "Agent: call configure_llm(...)" which
    is meaningless for CLI users (no `autoinfo configure_llm` command exists).
    """
    _print_human(_result_with_llm_unconfigured())
    out = capsys.readouterr().out
    assert "MCP tool configure_llm()" in out


def test_doctor_llm_hint_mentions_env_var(capsys: pytest.CaptureFixture) -> None:
    """CLI users must be directed to the AUTOINFO_LLM_API_KEY env var."""
    _print_human(_result_with_llm_unconfigured())
    out = capsys.readouterr().out
    assert "AUTOINFO_LLM_API_KEY" in out


def test_doctor_llm_hint_keeps_docs_reference(capsys: pytest.CaptureFixture) -> None:
    """The required-api-keys docs reference must remain."""
    _print_human(_result_with_llm_unconfigured())
    out = capsys.readouterr().out
    assert "docs/dev/required-api-keys.md" in out
