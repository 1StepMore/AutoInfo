"""Chinese/English deadline and forward-marker cases (#851).

Two real false positives from the tech-ai-developer digest run
(digest-markdown-20261119-074908/75317): the Apple compliance summary
"by January 31, 2027" (a DAY between month and year broke _BY_YEAR_RE)
and — for mixed-corpus Chinese lines whose years sit next to non-word
punctuation — the English-centric marker set missing Chinese forward/
deadline words.  Corpus grounding: 33 raw files in the domain mention
2027, so these are faithful citations, not hallucinations.  Bare future
years without any marker still fail (strictness preserved).

Note on CJK adjacency: "2027年" carries no ``\b`` boundary (CJK chars are
``\\w`` in Python re), so CJK-adjacent years never match _YEAR_RE at all —
the Chinese-marker cases below use the spaced form ("2027 年") that the
regex actually sees.
"""

from __future__ import annotations

from autoinfo.validation_matrix import _no_year_hallucination


def test_en_deadline_with_day_passes() -> None:
    # The real firing line (digest entry 48): "by January 31, 2027" — the
    # optional day between month and year must not break the by-year marker.
    text = (
        "**Summary**: Apple has introduced two compliance requirements for apps "
        "available in mainland China, requiring all developers to complete a "
        "compliance confirmation by January 31, 2027, to avoid App Store removal.\n"
    )
    assert _no_year_hallucination(text, "tech-ai-developer", "digest").passed


def test_zh_prediction_headline_spaced_form_passes() -> None:
    # Prediction phrasing ("很可能") is forward-looking for the spaced form.
    text = "# 本周摘要\n\n### 14. 2027 年火的很可能是AI工作台\n\n正文略。\n"
    assert _no_year_hallucination(text, "tech-ai-developer", "digest").passed


def test_zh_deadline_spaced_form_passes() -> None:
    text = "**Summary**: 苹果要求开发者请在 2027 年 1 月 31 日前完成合规验证。\n"
    assert _no_year_hallucination(text, "tech-ai-developer", "digest").passed


def test_zh_roadmap_marker_spaced_form_passes() -> None:
    text = "**Summary**: 官方预计完整版本将于 2027 年发布。\n"
    assert _no_year_hallucination(text, "tech-ai-developer", "digest").passed


def test_bare_future_year_without_marker_still_fails() -> None:
    # Strictness preserved: a bare spaced future year with no forward marker,
    # no named-year context and no same-line grounding still fails at P0.
    result = _no_year_hallucination("2029 年的会议记录如下：无。", "tech-ai-developer", "digest")
    assert not result.passed
    assert result.severity == "P0"
