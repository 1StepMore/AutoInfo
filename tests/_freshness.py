"""Clock-relative timestamps for KB entry fixtures.

Freshness thresholds are evaluated against the wall clock, so a hardcoded
``collected_at`` quietly ages until every entry in a fixture reads as stale
and the product generator raises ``StaleSourceError`` — a red build that
looks unrelated to whatever change happened to trigger it.

Every helper resolves against a single ``_NOW`` captured at import time, so
two calls with the same offset return byte-identical strings and a fixture can
assert on one against another.

Choosing an offset:

* a fixture that must simply read as **fresh** wants the default, 1 day;
* a fixture converted from a literal keeps the **age it had at conversion**
  (``fresh_iso(89)``), which preserves every ordering and window relationship
  inside that fixture while making it incapable of expiring;
* a date that must read as **old** stays a literal — it only gets older, so it
  is safe forever.

``tests/validation/test_freshness_guards.py`` enforces the first two.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

__all__ = ["fresh_date", "fresh_iso"]

_NOW = datetime.now(timezone.utc)
_TODAY = _NOW.date()


def fresh_iso(days_ago: int = 1) -> str:
    """Timezone-aware ISO-8601 timestamp *days_ago* days before the frozen now."""
    return (_NOW - timedelta(days=days_ago)).isoformat()


def fresh_date(days_ago: int = 1) -> str:
    """``YYYY-MM-DD`` *days_ago* days before the frozen today."""
    return (_TODAY - timedelta(days=days_ago)).isoformat()
