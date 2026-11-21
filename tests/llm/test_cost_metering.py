"""Choke-point cost metering tests (#863).

Every successful LLM call through ``autoinfo.llm.call_with_fallback`` must
leave one ``llm_tokens`` row in ``cost_log`` — before #863 the G3 relevance
judge and any direct ``LLMExtractor`` usage were invisible to budget-alert /
cost-dashboard entirely (issue #863: the #851 pilot made 40 LLM calls with
zero ``cost_log`` increment).  Metering is best-effort: it must never break
the LLM call itself, and non-integer (test-double) usage must never be logged.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from autoinfo.config import Config, QualityGateConfig
from autoinfo.llm import LLMExtractor, call_with_fallback, cost_attributes
from autoinfo.models import Item
from autoinfo.quality import G3RelevanceScoring


@pytest.fixture(autouse=True)
def _hermetic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate the CWD-relative ``cost_log`` DB and the provider key per test."""
    monkeypatch.chdir(tmp_path)
    # Test-only dummy value, inline per the tests/llm/test_fallback_injection.py
    # convention (_keys fixture) — never a real credential reference.
    monkeypatch.setenv("AUTOINFO_LLM_API_KEY", "primary-secret")


def _usage_response(prompt_tokens: int = 100, completion_tokens: int = 50) -> MagicMock:
    """A litellm-shaped response stub with REAL int token counters."""
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="ok"))]
    response.usage.prompt_tokens = prompt_tokens
    response.usage.completion_tokens = completion_tokens
    response.usage.total_tokens = prompt_tokens + completion_tokens
    return response


def _llm_rows() -> list[sqlite3.Row]:
    """Read ``llm_tokens`` rows from the CWD-local ``cost_log`` (tmp_path)."""
    if not Path("autoinfo.db").exists():
        return []
    conn = sqlite3.connect("autoinfo.db")
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT meter_type, meter_category, units, domain, item_id, model "
            "FROM cost_log WHERE meter_type = 'llm_tokens'"
        ).fetchall()
    finally:
        conn.close()


class TestChokePointMetering:
    """call_with_fallback is the single metering seam — one row per response."""

    def test_successful_call_writes_single_row(self) -> None:
        seen: list[str] = []
        mock_lm = MagicMock()
        mock_lm.completion.side_effect = lambda **kwargs: (
            seen.append(str(kwargs["model"])),
            _usage_response(),
        )[1]

        with patch.object(LLMExtractor, "_get_litellm", return_value=mock_lm):
            call_with_fallback(
                messages=[{"role": "user", "content": "short test"}],
                config=Config(),
                max_tokens=64,
            )

        rows = _llm_rows()
        assert len(rows) == 1
        assert rows[0]["meter_type"] == "llm_tokens"
        assert rows[0]["units"] == 150.0  # 100 prompt + 50 completion
        assert rows[0]["model"] == seen[0]

    def test_response_without_usage_is_not_logged(self) -> None:
        mock_lm = MagicMock()
        mock_lm.completion.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            usage=None,
        )

        with patch.object(LLMExtractor, "_get_litellm", return_value=mock_lm):
            call_with_fallback(
                messages=[{"role": "user", "content": "short test"}],
                config=Config(),
                max_tokens=64,
            )

        assert _llm_rows() == []

    def test_non_integer_usage_is_never_logged(self) -> None:
        """MagicMock auto-attributes are not ints — the guard keeps every
        existing MagicMock-based LLM test from writing garbage cost rows."""
        mock_lm = MagicMock()
        mock_lm.completion.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="ok"))]
        )

        with patch.object(LLMExtractor, "_get_litellm", return_value=mock_lm):
            call_with_fallback(
                messages=[{"role": "user", "content": "short test"}],
                config=Config(),
                max_tokens=64,
            )

        assert _llm_rows() == []

    def test_meter_failure_never_breaks_the_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from autoinfo.cost import CostMeter

        def _boom(*args: object, **kwargs: object) -> None:
            raise RuntimeError("cost db locked")

        monkeypatch.setattr(CostMeter, "log_llm_tokens", _boom)

        mock_lm = MagicMock()
        mock_lm.completion.return_value = _usage_response()

        with patch.object(LLMExtractor, "_get_litellm", return_value=mock_lm):
            response = call_with_fallback(
                messages=[{"role": "user", "content": "short test"}],
                config=Config(),
                max_tokens=64,
            )

        assert response.choices[0].message.content == "ok"
        assert _llm_rows() == []

    def test_cost_attributes_flow_into_the_row(self) -> None:
        mock_lm = MagicMock()
        mock_lm.completion.return_value = _usage_response()

        with (
            patch.object(LLMExtractor, "_get_litellm", return_value=mock_lm),
            cost_attributes(domain="demo-domain", item_id="item-42"),
        ):
            call_with_fallback(
                messages=[{"role": "user", "content": "short test"}],
                config=Config(),
                max_tokens=64,
            )

        rows = _llm_rows()
        assert len(rows) == 1
        assert rows[0]["domain"] == "demo-domain"
        assert rows[0]["item_id"] == "item-42"


class TestJudgedAndExtractedPaths:
    """The two paths #863 found invisible: G3 judge + direct extractor."""

    def test_g3_judge_path_is_metered(self, sample_item: Item) -> None:
        """G3's LLM relevance judge goes through call_with_fallback and must
        leave a cost_log row (pre-#863: zero rows for judge calls)."""
        mock_lm = MagicMock()
        mock_lm.completion.side_effect = lambda **kwargs: _scored_response()

        g3 = G3RelevanceScoring(model="test/g3-judge")
        config = QualityGateConfig(
            name="G3-RelevanceScoring",
            category="soft",
            retries=1,
            action="flag",
            threshold=30,
        )

        with patch.object(LLMExtractor, "_get_litellm", return_value=mock_lm):
            result = g3.check(
                sample_item,
                topic_keywords=["IVF", "embryo"],
                threshold=30,
                gate_config=config,
            )

        assert result.details["scoring_method"] == "llm"
        rows = [r for r in _llm_rows() if r["model"] == "test/g3-judge"]
        assert len(rows) >= 1

    def test_direct_extractor_path_is_metered(self, sample_item: Item) -> None:
        """Direct LLMExtractor.extract() usage (no process pipeline) must be
        metered by the choke point, not silently dropped."""
        mock_lm = MagicMock()
        mock_lm.completion.side_effect = lambda **kwargs: _extracted_response()

        cfg = Config()
        cfg.llm.model = "test/direct-extractor"
        extractor = LLMExtractor(config=cfg)

        with patch.object(LLMExtractor, "_get_litellm", return_value=mock_lm):
            extraction = extractor.extract(sample_item)

        assert extraction.tl_dr
        rows = [r for r in _llm_rows() if r["model"] == "test/direct-extractor"]
        assert len(rows) >= 1


def _scored_response() -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="85"))]
    response.usage.prompt_tokens = 60
    response.usage.completion_tokens = 5
    response.usage.total_tokens = 65
    return response


def _extracted_response() -> MagicMock:
    payload = json.dumps(
        {
            "tl_dr": "Choke-point metering test file summary.",
            "key_points": ["Point one"],
            "entities": [],
            "relevance_score": 85,
        }
    )
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=payload))]
    response.usage.prompt_tokens = 40
    response.usage.completion_tokens = 30
    response.usage.total_tokens = 70
    return response
