"""T17: retry budget is a call-site parameter, not a fixed module policy."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import MagicMock

import pytest

import autoinfo.output as out
from autoinfo.llm import _is_retryable_error


class _StopAfterCallError(Exception):
    """Sentinel raised at the synthesis seam so the caller need not render."""


class _AuthenticationError(Exception):
    status_code = 500


def _entries() -> list[dict[str, Any]]:
    return [
        {
            "entry_id": "retry-001",
            "title": "Time-lapse imaging improves IVF outcomes",
            "summary": "Live birth rates improved in a randomized trial.",
            "domain": "medical-research",
            "tier": "01-Raw",
            "language": "en",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
            "source_type": "api",
            "source_platform": "pubmed",
            "collected_at": date.today().isoformat(),
            "relevance_score": 92.0,
            "tags": "[]",
        }
    ]


def _patch_store(monkeypatch: pytest.MonkeyPatch) -> None:
    store = MagicMock()
    store.list_entries.return_value = _entries()
    monkeypatch.setattr(out, "KBStore", MagicMock(return_value=store))


def _record_summary_kwargs(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def fake_summary(*args: Any, **kwargs: Any) -> None:
        seen.update(kwargs)
        raise _StopAfterCallError

    monkeypatch.setattr(out, "_generate_executive_summary", fake_summary)
    return seen


def _record_digest_kwargs(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def fake_digest(*args: Any, **kwargs: Any) -> None:
        seen.update(kwargs)
        raise _StopAfterCallError

    monkeypatch.setattr(out, "_call_llm_for_digest", fake_digest)
    return seen


def test_report_forwards_explicit_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_store(monkeypatch)
    seen = _record_summary_kwargs(monkeypatch)
    monkeypatch.setattr(out, "_group_by_theme", lambda *a, **k: [])

    with pytest.raises(_StopAfterCallError):
        out.generate_report(
            domain="medical-research",
            max_synthesis_attempts=1,
            retry_backoff_seconds=0.0,
        )

    assert seen["max_synthesis_attempts"] == 1
    assert seen["retry_backoff_seconds"] == 0.0


def test_report_defaults_are_shipped_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_store(monkeypatch)
    seen = _record_summary_kwargs(monkeypatch)
    monkeypatch.setattr(out, "_group_by_theme", lambda *a, **k: [])

    with pytest.raises(_StopAfterCallError):
        out.generate_report(domain="medical-research")

    assert seen["max_synthesis_attempts"] == out._RETRY_MAX_ATTEMPTS
    assert seen["retry_backoff_seconds"] == out._RETRY_BACKOFF_SECONDS


def test_digest_forwards_explicit_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_store(monkeypatch)
    seen = _record_digest_kwargs(monkeypatch)

    with pytest.raises(_StopAfterCallError):
        out.generate_digest(
            domain="medical-research",
            max_synthesis_attempts=1,
            retry_backoff_seconds=0.0,
        )

    assert seen["max_synthesis_attempts"] == 1
    assert seen["retry_backoff_seconds"] == 0.0


def test_digest_defaults_are_shipped_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_store(monkeypatch)
    seen = _record_digest_kwargs(monkeypatch)

    with pytest.raises(_StopAfterCallError):
        out.generate_digest(domain="medical-research")

    assert seen["max_synthesis_attempts"] == 2
    assert seen["retry_backoff_seconds"] == 0.0


def test_internal_digest_call_honours_attempts_and_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = "not json"
    sleeps: list[float] = []
    calls = 0

    def fake_call(**kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return response

    monkeypatch.setattr(out, "call_with_fallback", fake_call)
    monkeypatch.setattr(out, "load_config", lambda path: None)

    result = out._call_llm_for_digest(
        "prompt",
        max_synthesis_attempts=3,
        retry_backoff_seconds=1.5,
        sleep_fn=sleeps.append,
    )

    assert result == {}
    assert calls == 3
    assert sleeps == [1.5, 1.5]


def test_authentication_error_is_not_retried_despite_500_status() -> None:
    assert _is_retryable_error(_AuthenticationError("missing api key")) is False
