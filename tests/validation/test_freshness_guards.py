"""Guard against date-literal time bombs in freshness-exposed tests.

A KB entry fixture whose ``collected_at`` is a hardcoded date stops being fresh
the day the domain's freshness threshold passes it. Nothing about the failure
points at the cause: the product generator raises ``StaleSourceError`` and the
suite goes red on an unrelated day. That is exactly how ``main`` went red on
2026-10-11 with 13 failures after being green on 2026-10-09.

The invariant this file enforces:

* a date literal that must read as **fresh** is computed from the clock via
  :mod:`tests._freshness`, never written down;
* a date literal that must read as **old** stays literal, because it only
  gets older and can therefore never expire.

``FRESH_WINDOW_DAYS`` is the warning radius. A literal already older than that
has either aged into the "deliberately stale" category or already broke its
test, and either way the suite reports it — this guard only exists to catch
the window in which a fixture is still green but heading for red.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()

FRESH_WINDOW_DAYS = 90
FUTURE_TOLERANCE_DAYS = 30

GENERATOR_CALL = re.compile(r"generate_(?:digest|tutorial|report|presentation)\s*\(")
ISO_DATE = re.compile(r'"(20\d\d-\d\d-\d\d)(?:T[^"]*)?"')


def offending_literals(text: str, today: datetime.date) -> list[tuple[int, str, int]]:
    """Return ``(lineno, literal, age_days)`` for every date that can expire.

    Only files that reach a freshness-filtered generator are considered, so
    collectors and API tests may keep arbitrary payload dates.
    """
    if not GENERATOR_CALL.search(text):
        return []
    found: list[tuple[int, str, int]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("#"):
            continue
        for match in ISO_DATE.finditer(line):
            age = (today - datetime.date.fromisoformat(match.group(1))).days
            if -FUTURE_TOLERANCE_DAYS <= age <= FRESH_WINDOW_DAYS:
                found.append((lineno, match.group(0), age))
    return found


def test_no_expiring_date_literals_in_freshness_exposed_tests() -> None:
    today = datetime.date.today()
    offenders: list[str] = []
    for path in sorted(TESTS_ROOT.rglob("*.py")):
        if path.resolve() == SELF:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, literal, age in offending_literals(text, today):
            relative = path.relative_to(TESTS_ROOT.parent)
            offenders.append(f"{relative}:{lineno}  {literal}  ({age}d old)")
    assert not offenders, (
        "These date literals will expire and turn into StaleSourceError "
        "failures. Use tests._freshness.fresh_iso()/fresh_date() instead — "
        "pass the age the fixture has today to preserve its internal ordering, "
        "or the default 1 day if it only needs to read as fresh. Only a date "
        "that must read as OLD may stay a literal.\n  " + "\n  ".join(offenders)
    )


def test_scanner_flags_a_planted_recent_literal() -> None:
    today = datetime.date(2026, 10, 12)
    text = 'ENTRY = {"collected_at": "2026-09-01"}\ngenerate_digest(domain="x")\n'
    assert offending_literals(text, today) == [(1, '"2026-09-01"', 41)]


def test_scanner_allows_a_deliberately_old_literal() -> None:
    today = datetime.date(2026, 10, 12)
    text = 'ENTRY = {"collected_at": "2020-01-01T00:00:00+00:00"}\ngenerate_tutorial(domain="x")\n'
    assert offending_literals(text, today) == []


def test_scanner_ignores_files_that_never_reach_the_freshness_filter() -> None:
    today = datetime.date(2026, 10, 12)
    text = 'PAYLOAD = {"published": "2026-09-01"}\n'
    assert offending_literals(text, today) == []
