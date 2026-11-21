"""Tests for the #351 V5 named-year exemption in ``_no_year_hallucination``.

V5 closes a false-positive class introduced by the #351 year-hallucination
gate: a FUTURE year used as part of a title/list/guide/ranking/survey/
publication NAME ("The Princeton Review's 2027 Best Colleges guide") is a
legitimate reference — the year names the edition of the guide — not a
hallucinated fact.  Those must PASS.  Bare future years asserted as
completed facts ("In 2031, adoption tripled") must STILL fail P0.  Pre-1950
years ("founded in 1917") are INFORMATIONAL only (#351 maintainer decision):
they are listed in ``details`` but do NOT fail the assertion.

Deterministic unit test: no LLM, no network.  Exercises the real
``_no_year_hallucination`` paths directly.
"""

from __future__ import annotations

from autoinfo import validation_matrix as vm


def test_named_year_guide_title_passes() -> None:
    """A future year inside a publication/guide NAME is legitimate — the year
    identifies the edition, not a hallucinated fact.  Pre-V5 this fired a P0
    false positive on the bare ``2027``; V5 exempts the name-shaped run."""
    r = vm._no_year_hallucination(
        "# T\n\nThe Princeton Review's 2027 Best Colleges guide ranks the "
        "top 10 colleges for financial aid.\n",
        "financial-intelligence",
        "report",
    )
    assert r.passed, r.details
    assert r.severity != "P0"


def test_named_year_guide_title_without_owner_passes() -> None:
    """The owner-possessive prefix is optional — "The 2027 Best Colleges
    guide is out now." is still a name-shaped run, not a hallucination."""
    r = vm._no_year_hallucination(
        "# T\n\nThe 2027 Best Colleges guide is out now.\n",
        "financial-intelligence",
        "report",
    )
    assert r.passed, r.details


def test_named_year_publication_name_passes() -> None:
    """A possessive publication name before the year (Bloomberg's 2027
    outlook ... list) is exempted by V5."""
    r = vm._no_year_hallucination(
        "# T\n\nBloomberg's 2027 outlook lists the key risks.\n",
        "financial-intelligence",
        "report",
    )
    assert r.passed, r.details


def test_bare_future_fact_still_p0_fails() -> None:
    """V5 must NOT weaken the P0 gate: a bare future year asserted as a
    completed fact still fails hard."""
    r = vm._no_year_hallucination(
        "# T\n\nIn 2031, adoption tripled\n",
        "financial-intelligence",
        "report",
    )
    assert not r.passed
    assert r.severity == "P0"


def test_bare_future_month_year_still_p0_fails() -> None:
    """Bare future month-years ("In March 2031, adoption tripled") still
    fail P0 — the named-year exemption only covers name-shaped runs."""
    r = vm._no_year_hallucination(
        "# T\n\nIn March 2031, adoption tripled\n",
        "financial-intelligence",
        "report",
    )
    assert not r.passed
    assert r.severity == "P0"


def test_pre_1950_informational_pass() -> None:
    """Pre-1950 years ("founded in 1917") are INFORMATIONAL, not failures:
    historical references are legitimate in some products, so the assertion
    passes at P1 and keeps the find visible in ``details``."""
    r = vm._no_year_hallucination(
        "# T\n\nFounded in 1917, the bank survived two wars.\n",
        "financial-intelligence",
        "report",
    )
    assert r.passed, r.details
    assert r.severity == "P1"
    assert "informational" in r.details
    assert "distant-past year 1917" in r.details


# ---------------------------------------------------------------------------
# #864 — source-grounding exemption for a FUTURE year the source really says.
# A future year backed by an inline URL / markdown link, a ``Source:`` /
# ``来源：`` label, or a quotation is grounded evidence, not a hallucination.
# A future year with none of those is STILL a P0 failure (no over-loosening).
# ---------------------------------------------------------------------------


def test_grammy_nominations_with_source_url_passes() -> None:
    """The 2027 Grammy nominations line carries the source URL, so the future
    year is source-grounded — not a hallucination (#864)."""
    r = vm._no_year_hallucination(
        "# T\n\nThe 2027 Grammy nominations were announced, with Olivia Rodrigo "
        "receiving seven nominations. "
        "[source](https://www.billboard.com/lists/"
        "grammy-nominations-2027-see-the-full-list)\n",
        "online-video",
        "digest",
    )
    assert r.passed, r.details
    assert r.severity != "P0"


def test_grammy_event_name_without_url_passes() -> None:
    """The event-name form ("2027 Grammy nominations") is a named year even
    without an inline URL — ``_is_named_year`` covers it (#864)."""
    r = vm._no_year_hallucination(
        "# T\n\nThe 2027 Grammy nominations were announced on Monday.\n",
        "online-video",
        "digest",
    )
    assert r.passed, r.details


def test_roadmap_release_with_source_label_passes() -> None:
    """A roadmap/release future year with a ``Source:`` label is grounded."""
    r = vm._no_year_hallucination(
        "# T\n\nFull release planned for early 2027. "
        "Source: https://vendor.example/roadmap\n",
        "tech-ai-developer",
        "digest",
    )
    assert r.passed, r.details


def test_source_label_alone_grounds_completed_fact_year() -> None:
    """The ``Source:`` label alone grounds a future year even when no
    forward-looking marker is present — proving the #864 grounding path (not
    just the older forward-looking exemption) is what passes it."""
    r = vm._no_year_hallucination(
        "# T\n\n2027 revenue hit 40 units. Source: annual report\n",
        "financial-intelligence",
        "report",
    )
    assert r.passed, r.details
    assert "informational" in r.details
    assert "source-grounded" in r.details


def test_markdown_link_alone_grounds_future_year() -> None:
    """An inline markdown link grounds a completed-fact future year."""
    r = vm._no_year_hallucination(
        "# T\n\n2027 revenue hit 40 units "
        "([source](https://example.com/report)).\n",
        "financial-intelligence",
        "report",
    )
    assert r.passed, r.details
    assert "informational" in r.details
    assert "source-grounded" in r.details


def test_chinese_quoted_future_year_passes() -> None:
    """A Chinese source quotation containing the year is grounded evidence
    (#864).  The spaced form ``2027 年`` is matched by ``_YEAR_RE`` and must be
    exempted by the quotation, not by hiding the content."""
    r = vm._no_year_hallucination(
        "# T\n\n“2027 年火的很可能是 AI 工作台”\n",
        "tech-ai-developer",
        "digest",
    )
    assert r.passed, r.details
    assert "informational" in r.details
    assert "source-grounded" in r.details
    # The exact no-space form from the source is also never flagged.
    r2 = vm._no_year_hallucination(
        "# T\n\n“2027年火的很可能是AI工作台”\n",
        "tech-ai-developer",
        "digest",
    )
    assert r2.passed, r2.details


def test_ungrounded_future_year_still_p0_fails() -> None:
    """Guard against over-loosening: a bare future year with no URL, no
    quotation, and no Source label is STILL a P0 hallucination (#864)."""
    r = vm._no_year_hallucination(
        "# T\n\nIn 2027 the company will have shipped 40 units\n",
        "financial-intelligence",
        "report",
    )
    assert not r.passed
    assert r.severity == "P0"
    assert "future year 2027" in r.details


def test_ungrounded_future_month_year_still_p0_fails() -> None:
    """The month-year branch keeps its P0 behavior when there is no grounding."""
    r = vm._no_year_hallucination(
        "# T\n\nIn March 2031, adoption tripled\n",
        "financial-intelligence",
        "report",
    )
    assert not r.passed
    assert r.severity == "P0"
