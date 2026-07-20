"""Shared test fixtures for AutoInfo.

Provides reusable fixtures used across all test modules:
temporary project directories, sample data objects, CLI runner, and
PubMed response cache.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml

from autoinfo.models import ExtractionResult, Item, KBEntry

if TYPE_CHECKING:
    from typer.testing import CliRunner

# ---------------------------------------------------------------------------
# Pytest hooks
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers to suppress 'unknown marker' warnings."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )
    config.addinivalue_line(
        "markers",
        "network: marks tests that make network requests (use VCR cassettes instead)",
    )
    config.addinivalue_line(
        "markers",
        "llm: marks tests that require LLM integration (mocked in CI)",
    )


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
