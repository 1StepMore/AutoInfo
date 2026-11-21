"""E2E journey fixtures (issue #849)."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _journeys_run_in_ci_llm_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Journeys must see the CI LLM mode (no key), not the harness environment.

    The journeys and their scenarios are designed for the no-key CI
    environment: ``requires_env`` scenarios honestly report ``unconfigured``
    and LLM-required MCP tools take the not-configured dispatch branch
    (``_is_llm_configured`` reads the same env var).  With a harness key in
    the environment the same journeys walk the real LLM path — on a dead
    endpoint that is the 300s+ IOCP hang of issue #849, and with the
    hermetic gate it degrades into 60s synthesis backoff sleeps that blow
    the per-test timeout anyway.  Removing the key at test level keeps the
    journeys hermetic and CI-equivalent regardless of the host environment;
    tests that need a key still override with their own ``setenv``.
    """
    monkeypatch.delenv("AUTOINFO_LLM_API_KEY", raising=False)
