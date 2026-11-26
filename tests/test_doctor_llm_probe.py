"""Primary LLM probe for ``autoinfo doctor --probe-llm`` (issue #968).

Regressions locked here:

1. ``--probe-llm`` must cover the **primary** entry — previously it walked
   only the fallback chain, so with an empty fallback list nothing was
   probed and the doctor exited 0 while the primary could not authenticate.
2. A failed probe (e.g. HTTP 401) must be reported ``ok=False`` and make
   the CLI exit non-zero.
3. Without ``--probe-llm`` the LLM line must not claim connectivity — it
   says the key is present but *not verified*.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from autoinfo import config as config_module
from autoinfo import doctor as doctor_module
from autoinfo.cli.doctor import app as doctor_app
from autoinfo.config import Config, LLMConfig, probe_primary_llm
from autoinfo.doctor import run_doctor

PRIMARY_URL = "https://primary.example/v1"
PRIMARY_KEY = "primary-secret-key"


def _config(fallback: list[LLMConfig] | None = None) -> Config:
    return Config(
        llm=LLMConfig(
            provider="openai",
            model="deepseek-v4-flash",
            api_key=PRIMARY_KEY,
            base_url=PRIMARY_URL,
            fallback=fallback or [],
        )
    )


@pytest.fixture
def doctor_env(monkeypatch: Any, tmp_path: Path) -> Config:
    """Point doctor at a synthetic config and disable validation."""
    cfg = _config()
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("# synthetic test config\n", encoding="utf-8")
    monkeypatch.setattr(doctor_module, "get_config_path", lambda: cfg_path)
    monkeypatch.setattr(doctor_module, "load_config", lambda path: cfg)
    monkeypatch.setattr(doctor_module, "validate_config", lambda config: [])
    return cfg


# ---------------------------------------------------------------------------
# probe_primary_llm (config layer)
# ---------------------------------------------------------------------------


class TestProbePrimaryLlm:
    def test_success_is_reported(self, monkeypatch: Any) -> None:
        calls: list[dict[str, Any]] = []

        def fake_completion(**kwargs: Any) -> object:
            calls.append(kwargs)
            return object()

        monkeypatch.setattr(config_module, "_probe_completion", fake_completion)

        result = probe_primary_llm(_config())

        assert result["target"] == "primary"
        assert result["ok"] is True
        assert result["status"] == "ok"
        assert result["error"] is None
        assert result["latency_ms"] >= 0.0
        # One real request to the primary model id, with the primary key.
        assert len(calls) == 1
        assert calls[0]["model"] == "openai/deepseek-v4-flash"
        assert calls[0]["api_key"] == PRIMARY_KEY

    def test_401_is_reported_as_failure(self, monkeypatch: Any) -> None:
        def fake_completion(**kwargs: Any) -> object:
            raise RuntimeError("Error code: 401 - invalid api key")

        monkeypatch.setattr(config_module, "_probe_completion", fake_completion)

        result = probe_primary_llm(_config())

        assert result["ok"] is False
        assert result["status"] == "error"
        assert result["error"] is not None
        # Readable cause, not a bare str(exc) dump — and never the key.
        assert "authentication failed" in result["error"]
        assert PRIMARY_KEY not in result["error"]

    def test_timeout_is_humanized(self, monkeypatch: Any) -> None:
        def fake_completion(**kwargs: Any) -> object:
            raise RuntimeError("Request timed out after 20s")

        monkeypatch.setattr(config_module, "_probe_completion", fake_completion)

        result = probe_primary_llm(_config())

        assert result["ok"] is False
        assert "timed out" in result["error"].lower()

    def test_missing_key_is_a_failure_without_a_request(self, monkeypatch: Any) -> None:
        def fake_completion(**kwargs: Any) -> object:  # pragma: no cover
            raise AssertionError("no request may be sent without a key")

        monkeypatch.setattr(config_module, "_probe_completion", fake_completion)
        monkeypatch.delenv("AUTOINFO_LLM_API_KEY", raising=False)

        cfg = Config(
            llm=LLMConfig(
                provider="openai",
                model="deepseek-v4-flash",
                api_key="",
                base_url=PRIMARY_URL,
            )
        )
        result = probe_primary_llm(cfg)

        assert result["ok"] is False
        assert "no usable API key" in result["error"]


# ---------------------------------------------------------------------------
# run_doctor probe_llm=True (doctor layer)
# ---------------------------------------------------------------------------


class TestRunDoctorProbe:
    def test_primary_probe_present_and_ok(
        self, monkeypatch: Any, doctor_env: Config
    ) -> None:
        monkeypatch.setattr(
            config_module, "_probe_completion", lambda **kwargs: object()
        )

        result = run_doctor(probe_llm=True)

        assert result["llm_probe"]["ok"] is True
        assert result["llm_probe"]["target"] == "primary"

    def test_primary_401_sets_ok_false(
        self, monkeypatch: Any, doctor_env: Config
    ) -> None:
        def fake_completion(**kwargs: Any) -> object:
            raise RuntimeError("Error code: 401 - invalid api key")

        monkeypatch.setattr(config_module, "_probe_completion", fake_completion)

        result = run_doctor(probe_llm=True)

        assert result["llm_probe"]["ok"] is False
        assert "authentication failed" in result["llm_probe"]["error"]

    def test_no_probe_without_flag(self, monkeypatch: Any, doctor_env: Config) -> None:
        monkeypatch.setattr(
            config_module, "_probe_completion", lambda **kwargs: object()
        )

        result = run_doctor(probe_llm=False)

        assert "llm_probe" not in result
        assert "fallback_probe" not in result


# ---------------------------------------------------------------------------
# CLI layer: exit codes and honest wording
# ---------------------------------------------------------------------------


class TestDoctorCliExitCodes:
    def test_probe_success_exits_zero(
        self, monkeypatch: Any, doctor_env: Config
    ) -> None:
        monkeypatch.setattr(
            config_module, "_probe_completion", lambda **kwargs: object()
        )

        result = CliRunner().invoke(doctor_app, ["--probe-llm"])

        assert result.exit_code == 0
        assert "primary" in result.stdout

    def test_empty_fallback_and_primary_failure_exits_nonzero(
        self, monkeypatch: Any, doctor_env: Config
    ) -> None:
        def fake_completion(**kwargs: Any) -> object:
            raise RuntimeError("Error code: 401 - invalid api key")

        monkeypatch.setattr(config_module, "_probe_completion", fake_completion)

        result = CliRunner().invoke(doctor_app, ["--probe-llm"])

        assert result.exit_code != 0
        assert "❌" in result.stdout

    def test_no_probe_llm_line_says_not_verified(
        self, monkeypatch: Any, doctor_env: Config
    ) -> None:
        """Without --probe-llm the ✅ must not read as "connectivity verified"."""
        monkeypatch.setattr(
            config_module, "_probe_completion", lambda **kwargs: object()
        )

        result = CliRunner().invoke(doctor_app, [])

        assert result.exit_code == 0
        assert "not verified" in result.stdout
        assert "--probe-llm" in result.stdout
