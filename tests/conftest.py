"""Shared test fixtures for AutoInfo.

Provides reusable fixtures used across all test modules:
temporary project directories, sample data objects, CLI runner,
PubMed response cache, LLM mock helpers, and API-key skip guards.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Generator
from unittest.mock import MagicMock

import pytest
import yaml

from autoinfo.models import ExtractionResult, Item, KBEntry

if TYPE_CHECKING:
    from typer.testing import CliRunner

# ---------------------------------------------------------------------------
# LLM API key guard
# ---------------------------------------------------------------------------

HAVE_LLM_KEY: bool = bool(os.environ.get("AUTOINFO_LLM_API_KEY"))
"""``True`` when ``AUTOINFO_LLM_API_KEY`` is set — real LLM tests can run."""

requires_llm_key = pytest.mark.skipif(
    not HAVE_LLM_KEY,
    reason="AUTOINFO_LLM_API_KEY not set — requires real LLM API key",
)
"""Decorator / skip condition for tests that need a real LLM API key.

Usage::

    @requires_llm_key
    def test_something_that_needs_real_llm():
        ...

Or on a class::

    @requires_llm_key
    class TestRealLLM:
        ...
"""

# ---------------------------------------------------------------------------
# Optional dependency guards (extras: pdf, tts, video; system: ffmpeg)
# ---------------------------------------------------------------------------

HAVE_PIL: bool = importlib.util.find_spec("PIL") is not None
"""``True`` when Pillow is installed (``video`` extra) — image/video tests can run."""

HAVE_STRIPE: bool = importlib.util.find_spec("stripe") is not None
"""``True`` when ``stripe`` is installed (core dependency) — billing tests can run."""

HAVE_PYMUPDF: bool = importlib.util.find_spec("fitz") is not None
"""``True`` when PyMuPDF is installed (``pdf`` extra) — PDF import tests can run."""

HAVE_WEASYPRINT: bool = importlib.util.find_spec("weasyprint") is not None
"""``True`` when weasyprint is installed (``pdf`` extra) — PDF-render tests can run."""

HAVE_FFMPEG: bool = shutil.which("ffmpeg") is not None
"""``True`` when the ``ffmpeg`` binary is on PATH — media-processing tests can run."""


def requires_optional_dep(*deps: str):
    """Return a skipif marker for tests that need one or more optional deps.

    Mirrors :data:`requires_llm_key` for the optional-dependency gates above.
    Each ``dep`` must be a key of :data:`_OPTIONAL_DEP_PRESENT`. Usage::

        @requires_optional_dep("PIL")
        def test_pillow_rendering():
            ...

        @requires_optional_dep("ffmpeg", "PIL")
        def test_video_pipeline():
            ...
    """
    missing = [dep for dep in deps if not _OPTIONAL_DEP_PRESENT[dep]]
    return pytest.mark.skipif(
        bool(missing),
        reason=f"missing optional dep(s): {', '.join(missing)} — install '.[dev,stripe,pdf,tts,web,video]'",
    )


_OPTIONAL_DEP_PRESENT: dict[str, bool] = {
    "PIL": HAVE_PIL,
    "stripe": HAVE_STRIPE,
    "fitz": HAVE_PYMUPDF,
    "weasyprint": HAVE_WEASYPRINT,
    "ffmpeg": HAVE_FFMPEG,
}

# ---------------------------------------------------------------------------
# Pytest hooks
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers to suppress 'unknown marker' warnings.

    Marker taxonomy (rationalized M0T7, 2026-08-05):
    - ``slow`` / ``network`` **removed** — zero usages anywhere in tests/
      (both as decorators and as module-level ``pytestmark``); dead registrations.
    - ``v1_2`` kept — used as module-level ``pytestmark`` in
      ``tests/test_v1_2_integration.py``.
    - ``llm`` kept — used by ``TestRealLLM`` (``tests/test_real_api.py``).
    - ``real_api`` kept — module-level ``pytestmark`` in
      ``tests/test_real_api.py``.
    - ``optional`` kept — added in M0T2; consumed by M0T3 env-dep skip gates.
    - ``callback`` / ``envelope`` **added** — registered ahead of later waves
      that will tag tests against the agent-callback surface (M4) and the
      ``{success, data}`` / ``{success, error}`` response envelope (M1).
    """
    config.addinivalue_line(
        "markers",
        "llm: marks tests that require LLM integration (mocked in CI)",
    )
    config.addinivalue_line(
        "markers",
        "v1_2: marks tests covering v1.2 features (vector, API, CEFR, email, etc.)",
    )
    config.addinivalue_line(
        "markers",
        "real_api: marks tests that call real external APIs (PubMed, RSS, LLM); "
        "skipped by default in CI",
    )
    config.addinivalue_line(
        "markers",
        "optional: marks tests that need an optional dependency (PIL/stripe/"
        "PyMuPDF/weasyprint/ffmpeg); skipped when the HAVE_* gate in conftest is False",
    )
    config.addinivalue_line(
        "markers",
        "callback: marks tests exercising the agent-callback delivery surface "
        "(set_agent_callback / list_agent_callbacks / remove_agent_callback)",
    )
    config.addinivalue_line(
        "markers",
        "envelope: marks tests asserting the {success, data} / {success, error} "
        "response-envelope shape",
    )


# ---------------------------------------------------------------------------
# Skip-ceiling guard (M0T10, 2026-08-05)
# ---------------------------------------------------------------------------
# Only tests carrying ``@pytest.mark.optional`` that actually SKIP count
# against the tagged-skip ceiling. Plain skips (typer-on-Py3.14, missing
# VCR cassettes, module-level importorskip, no-LLM-key) are outside the
# tagged-skip budget by design — see tests/TRIAGE.md §Skip-count ceiling.

_OPTIONAL_SKIPPED: set[str] = set()
"""Nodeids of ``@pytest.mark.optional`` tests that were skipped in this run."""


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call) -> Generator:  # noqa: N802 (pytest hook name)
    """Accumulate optional-marked tests that skipped (setup or call phase).

    Hookwrapper so the real ``TestReport`` is inspected after pytest's own
    implementation built it. Dedup by nodeid — a skip can be reported at
    both the setup and call phases, and must not be double-counted. Every
    exception is swallowed: this guard is additive and must never break
    collection or the run itself.
    """
    outcome = yield
    try:
        report = outcome.get_result()
        if report.when in ("setup", "call") and report.skipped:
            if item.get_closest_marker("optional") is not None:
                _OPTIONAL_SKIPPED.add(item.nodeid)
    except Exception:
        pass


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Assert the tagged-skip ceiling (25) at session end (M0T10 gate).

    Ceiling 25 = 20 plan baseline + 14 M0T3-gated skips - 9 typer/Py3.14
    pre-existing (which carry no ``optional`` marker and are never counted).
    On breach, fail loudly so the gate run shows the excess immediately.
    """
    try:
        count = len(_OPTIONAL_SKIPPED)
        if count > 25:
            raise AssertionError(
                "SKIP CEILING EXCEEDED: %d optional-marked skips > 25. "
                "Skip ceiling 25 — per-test justification in TRIAGE.md "
                "§Ceiling update — M0T3. Optional-marked skipped tests:\n  - %s"
                % (count, "\n  - ".join(sorted(_OPTIONAL_SKIPPED)))
            )
    except AssertionError:
        raise
    except Exception:
        # Never let the guard itself break session teardown.
        pass


# ---------------------------------------------------------------------------
# Fixture data helpers
# ---------------------------------------------------------------------------


_SAMPLE_CONFIG = {
    "project": {"name": "Test Project", "created_at": "2026-07-01"},
    "llm": {
        "provider": "openrouter",
        "model": "deepseek/deepseek-chat",
        "api_key": "test-key",
    },
    "domains": [
        {
            "name": "medical-research",
            "active": True,
            "sources": [
                {
                    "name": "pubmed",
                    "type": "api",
                    "url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
                    "quality_tier": 1,
                }
            ],
            "topics": [{"name": "IVF breakthroughs", "keywords": ["IVF", "embryo"]}],
        }
    ],
}

_PUBMED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE PubmedArticleSet PUBLIC "-//NLM//DTD PubMed 2.0//EN"
  "https://dtd.nlm.nih.gov/ncbi/pubmed/out/PubMed.dtd">
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation Status="PubMed-not-MEDLINE" Owner="NLM">
      <PMID Version="1">12345678</PMID>
      <DateCompleted>
        <Year>2026</Year>
        <Month>03</Month>
        <Day>15</Day>
      </DateCompleted>
      <Article PubModel="Print-Electronic">
        <Journal>
          <ISSN IssnType="Print">1234-5678</ISSN>
          <JournalIssue CitedMedium="Print">
            <Volume>42</Volume>
            <Issue>3</Issue>
            <PubDate>
              <Year>2026</Year>
              <Month>Mar</Month>
            </PubDate>
          </JournalIssue>
          <Title>Journal of Reproductive Medicine</Title>
          <ISOAbbreviation>J Reprod Med</ISOAbbreviation>
        </Journal>
        <ArticleTitle>Improved IVF outcomes with time-lapse embryo imaging: a randomized controlled trial</ArticleTitle>
        <Pagination>
          <MedlinePgn>234-245</MedlinePgn>
        </Pagination>
        <AuthorList CompleteYN="Y">
          <Author ValidYN="Y">
            <LastName>Zhang</LastName>
            <ForeName>Wei</ForeName>
            <Initials>W</Initials>
          </Author>
          <Author ValidYN="Y">
            <LastName>Chen</LastName>
            <ForeName>Li</ForeName>
            <Initials>L</Initials>
          </Author>
          <Author ValidYN="Y">
            <LastName>Smith</LastName>
            <ForeName>James A</ForeName>
            <Initials>JA</Initials>
          </Author>
        </AuthorList>
        <Abstract>
          <AbstractText Label="Background" NlmCategory="BACKGROUND">
            Time-lapse embryo imaging has been proposed as a non-invasive method to improve embryo selection in IVF cycles.
          </AbstractText>
          <AbstractText Label="Methods" NlmCategory="METHODS">
            We conducted a multicenter randomized controlled trial involving 1,200 patients undergoing IVF treatment.
          </AbstractText>
          <AbstractText Label="Results" NlmCategory="RESULTS">
            The live birth rate was significantly higher in the time-lapse group (48.2% vs. 39.5%, p=0.006).
          </AbstractText>
          <AbstractText Label="Conclusions" NlmCategory="CONCLUSIONS">
            Time-lapse embryo imaging significantly improves live birth rates compared to standard morphological assessment.
          </AbstractText>
        </Abstract>
        <Language>eng</Language>
        <PublicationTypeList>
          <PublicationType UI="D016428">Journal Article</PublicationType>
          <PublicationType UI="D017064">Randomized Controlled Trial</PublicationType>
        </PublicationTypeList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="doi">10.1000/j.jrm.2026.03.004</ArticleId>
        <ArticleId IdType="pubmed">12345678</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project with a valid ``.autoinfo/config.yaml``.

    Returns the root path of the temporary project.
    """
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_path = config_dir / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as fh:
        yaml.dump(_SAMPLE_CONFIG, fh, default_flow_style=False)

    return tmp_path


@pytest.fixture
def sample_item() -> Item:
    """Return a synthetic :class:`Item` with realistic PubMed-like data."""
    return Item(
        id="test-item-001",
        source_name="pubmed",
        source_type="api",
        source_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=12345678",
        title="Improved IVF outcomes with time-lapse embryo imaging: a randomized controlled trial",
        content=(
            "Time-lapse embryo imaging has been proposed as a non-invasive method to improve embryo "
            "selection in IVF cycles. We conducted a multicenter randomized controlled trial involving "
            "1,200 patients undergoing IVF treatment. The live birth rate was significantly higher in "
            "the time-lapse group compared to the control group (48.2% vs. 39.5%, relative risk 1.22, "
            "95% CI 1.06-1.40, p=0.006). Time-lapse embryo imaging significantly improves live birth "
            "rates compared to standard morphological assessment in IVF patients."
        ),
        content_type="text",
        collected_at="2026-07-15T10:30:00Z",
        language="en",
        source_platform="pubmed",
        domain="medical-research",
        topic_tags=["IVF", "embryo imaging"],
        quality_tier=1,
    )


@pytest.fixture
def sample_pubmed_response() -> str:
    """Return a cached PubMed ``efetch`` XML response string.

    The XML contains a single article with PMID 12345678.
    """
    return _PUBMED_XML


@pytest.fixture
def cli_runner() -> "CliRunner":
    """Return a :class:`typer.testing.CliRunner` for CLI tests."""
    from typer.testing import CliRunner

    return CliRunner()


@pytest.fixture
def sample_kb_entry() -> KBEntry:
    """Return a synthetic :class:`KBEntry` with test data."""
    return KBEntry(
        entry_id="kb-entry-001",
        title="Improved IVF outcomes with time-lapse embryo imaging: a randomized controlled trial",
        domain="medical-research",
        tier="01-Raw",
        source_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=12345678",
        source_type="api",
        source_platform="pubmed",
        collected_at="2026-07-15T10:30:00Z",
        summary="Time-lapse embryo imaging significantly improves live birth rates (48.2% vs 39.5%) compared to standard morphological assessment in a large RCT of 1,200 IVF patients.",
        tags=["IVF", "embryo imaging", "time-lapse", "RCT"],
        priority=2,
        language="en",
        quality_tier=1,
        relevance_score=92.0,
        dedup_status="unique",
        file_path="",
    )


@pytest.fixture
def sample_extraction_input() -> dict:
    """Return a synthetic extraction input dict (matches fixture JSON)."""
    return {
        "id": "test-item-001",
        "title": "Improved IVF outcomes with time-lapse embryo imaging: a randomized controlled trial",
        "content": (
            "Time-lapse embryo imaging has been proposed as a non-invasive method to improve embryo "
            "selection in IVF cycles. We conducted a multicenter randomized controlled trial involving "
            "1,200 patients undergoing IVF treatment. The live birth rate was significantly higher in "
            "the time-lapse group compared to the control group (48.2% vs. 39.5%, relative risk 1.22, "
            "95% CI 1.06-1.40, p=0.006). Time-lapse embryo imaging significantly improves live birth "
            "rates compared to standard morphological assessment in IVF patients."
        ),
        "source_name": "pubmed",
        "collected_at": "2026-07-15T10:30:00Z",
    }


@pytest.fixture
def sample_extraction_output() -> ExtractionResult:
    """Return the expected :class:`ExtractionResult` for the sample input."""
    return ExtractionResult(
        item_id="test-item-001",
        title="Improved IVF outcomes with time-lapse embryo imaging: a randomized controlled trial",
        tl_dr=(
            "Time-lapse embryo imaging significantly improves live birth rates (48.2% vs 39.5%) "
            "compared to standard morphological assessment in a large RCT of 1,200 IVF patients."
        ),
        key_points=[
            "Multicenter RCT with 1,200 IVF patients comparing time-lapse imaging to standard morphological assessment",
            "Live birth rate: 48.2% (time-lapse) vs 39.5% (control), RR 1.22, 95% CI 1.06-1.40, p=0.006",
            "Clinical pregnancy rate and implantation rate also significantly improved in the time-lapse group",
            "Time-lapse imaging is a non-invasive method that improves embryo selection in IVF cycles",
        ],
        entities=[
            {"name": "Time-lapse embryo imaging", "type": "technology", "relevance": 0.95},
            {"name": "IVF", "type": "procedure", "relevance": 0.90},
            {"name": "Live birth rate", "type": "outcome", "relevance": 0.85},
        ],
        relevance_score=92.0,
    )


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the ``tests/fixtures/`` directory."""
    return Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------------------
# LLM test helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_litellm_response() -> MagicMock:
    """Return a ``MagicMock`` that simulates a successful ``litellm.completion`` call.

    The mock response contains a single choice with ``{"tl_dr": "test", ...}``
    as its JSON content — suitable for :class:`LLMExtractor` tests.

    Test files should ``patch.object(ClassName, "_get_litellm")`` or
    ``patch("litellm.completion")`` with this fixture's return value.
    """
    m = MagicMock()
    m.completion.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=json.dumps({
            "tl_dr": "Mocked TL;DR for testing",
            "key_points": ["Point one", "Point two"],
            "entities": [],
            "relevance_score": 85,
        })))],
    )
    return m
