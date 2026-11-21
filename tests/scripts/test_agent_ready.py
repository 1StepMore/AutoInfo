"""Tests for the agent-ready entrypoint (scripts/agent_ready.py, issue #884).

Locks the executable contract: agent-ready/v1 shape, the three-step model
ladder (implemented in code, no vendor hardcoding), and the machine exit
codes 0/2/3/4.  No network, no LLM, no real credentials — env vars are
monkeypatched, the repo config seam is pointed at tmp_path.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# scripts/ is not a package — load it via sys.path like the script itself does.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import agent_ready as ar  # noqa: E402  (sys.path insert above)

_LADDER_ENV_VARS = (
    "OPENAI_BASE_URL",
    "OPENAI_API_BASE",
    "OPENAI_API_KEY",
    "AUTOINFO_LLM_API_KEY",
)


@pytest.fixture(autouse=True)
def _hermetic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the config seam at tmp_path and clear every ladder env var."""
    monkeypatch.setattr(ar, "REPO_ROOT", tmp_path)
    for var in _LADDER_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# ladder 1: harness-default
# ---------------------------------------------------------------------------


def test_ladder_step1_harness_default_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-harness-key")
    check = ar.check_llm()
    assert check["status"] == "ok"
    assert check["code"] == "ok"
    assert check["ladder"][0]["result"] == "present"
    assert check["ladder"][1]["result"] == "absent"


# ---------------------------------------------------------------------------
# ladder 2: machine endpoint
# ---------------------------------------------------------------------------


def test_ladder_step2_machine_endpoint_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOINFO_LLM_API_KEY", "test-machine-key")
    check = ar.check_llm()
    assert check["status"] == "ok"
    assert check["code"] == "ok"
    assert check["ladder"][0]["result"] == "absent"
    assert check["ladder"][1]["result"] == "present"


def test_ladder_step2_config_reference_hit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # BYOK contract: the repo config stores a ${ENV} reference; the ladder
    # probes the referenced env var's presence, never its value.
    (tmp_path / ".autoinfo").mkdir()
    (tmp_path / ".autoinfo" / "config.yaml").write_text(
        "llm:\n  api_key: ${MY_TEST_KEY_VAR}\n", encoding="utf-8"
    )
    monkeypatch.setenv("MY_TEST_KEY_VAR", "test-config-key")
    check = ar.check_llm()
    assert check["status"] == "ok"
    assert "${MY_TEST_KEY_VAR}" in check["ladder"][1]["result"]


# ---------------------------------------------------------------------------
# ladder 3: ask-human (blocked)
# ---------------------------------------------------------------------------


def test_ladder_step3_blocked_without_any_key() -> None:
    check = ar.check_llm()
    assert check["status"] == "blocked"
    assert check["code"] == "blocked:no-llm-key"
    assert check["ladder"][2] == {"step": 3, "probe": "ask-human", "result": "required"}
    assert check["remedy"]


# ---------------------------------------------------------------------------
# exit codes + contract shape
# ---------------------------------------------------------------------------


def test_exit_code_mapping() -> None:
    assert ar.exit_code_for([]) == 0
    assert ar.exit_code_for([{"status": "blocked", "code": "blocked:no-llm-key"}]) == 2
    assert ar.exit_code_for([{"status": "blocked", "code": "blocked:missing-dep"}]) == 3
    assert ar.exit_code_for([{"status": "blocked", "code": "blocked:no-venv"}]) == 4
    # Precedence: 2 > 3 > 4.
    assert (
        ar.exit_code_for(
            [
                {"status": "blocked", "code": "blocked:no-venv"},
                {"status": "blocked", "code": "blocked:missing-dep"},
                {"status": "blocked", "code": "blocked:no-llm-key"},
            ]
        )
        == 2
    )


def test_contract_shape_all_green() -> None:
    with (
        patch.object(
            ar,
            "check_venv",
            return_value={"id": "venv", "status": "ok", "code": "ok", "detail": ""},
        ),
        patch.object(
            ar,
            "check_deps_state",
            return_value={"id": "deps", "status": "ok", "code": "ok", "detail": ""},
        ),
        patch.object(
            ar, "check_llm", return_value={"id": "llm", "status": "ok", "code": "ok", "detail": ""}
        ),
        patch.object(
            ar,
            "check_docs",
            return_value={"id": "docs", "status": "ok", "code": "ok", "detail": ""},
        ),
        patch.object(
            ar,
            "check_matrix_evidence",
            return_value={"id": "matrix-evidence", "status": "ok", "code": "ok", "detail": ""},
        ),
    ):
        report = ar.build_report()
    assert report["schema"] == "agent-ready/v1"
    assert report["ok"] is True
    assert report["next_action"]
    assert all(c["status"] in ("ok", "degraded", "blocked") for c in report["checks"])
    assert all(
        c["code"]
        in (
            "ok",
            "blocked:no-llm-key",
            "blocked:missing-dep",
            "blocked:no-venv",
            "blocked:not-onboarded",
        )
        for c in report["checks"]
    )
    assert report["next_action"].startswith("run the goal gate")
