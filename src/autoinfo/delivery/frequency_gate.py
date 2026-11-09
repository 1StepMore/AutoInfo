"""Schedule-frequency gate for named end-users (todo 12 — P1-2 enforcement).

Single enforcement seam for delivery-schedule creation on BOTH the CLI
(``autoinfo cron add-delivery``) and the MCP (``add_delivery_schedule``)
paths: when the schedule carries a named *user_id*, the schedule's trigger
cadence is compared against the subscription's ``max_frequency``.  The MCP
path was wired in #674 (2026-11-05) — the two entry points share this
module's check; neither copies threshold logic.  Since #687 both call sites
pass the cadence **derived from the cron expression** (:func:`derive_cadence`)
instead of the ``period`` field — ``period`` keeps its "content window"
meaning and no longer doubles as the frequency-limit criterion, so a
``0 8 * * *`` + ``period="weekly"`` plan can no longer pass a weekly limit
while actually delivering daily.

``user_id=""`` schedules (unattended/batch) skip the gate — quotas apply
only to named end-users.

Frequency ranking (most→least frequent): ``minutely`` / ``hourly`` /
``daily`` / ``weekly`` / ``monthly`` / ``quarterly``.  A schedule at or
below the subscription ceiling is allowed; anything more frequent is
rejected with the canonical ``FREE_TIER_LIMIT`` error envelope.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from autoinfo.mcp.errors import ErrorCode, error_response
from autoinfo.output.free_tier import (
    FreeTierLimitError,
    _is_limited_subscription,
    _subscription_for_user,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass

logger = logging.getLogger(__name__)

_FREQUENCY_RANK: dict[str, int] = {
    "quarterly": 1,
    "monthly": 2,
    "weekly": 3,
    "daily": 4,
    "hourly": 5,
    "minutely": 6,
}

# --- derive_cadence sampling windows (issue #687) --------------------------
# Real cadence is derived by COUNTING actual fire times (croniter) over a
# fixed window, not by parsing fields: counting is immune to DST gaps (a
# ``0 8 * * *`` cron has a 23 h minimum interval on spring-forward days but
# still fires exactly once per day) and handles multi-slot expressions
# (``0 8 * * 1,4``) and step expressions (``*/5``) without special cases.
_CADENCE_WINDOW_DAYS = 28
# ≥ 672 fires in 28 days ⇒ at least hourly on average; a second, 1-hour
# sample then separates hourly (≤ 1 fire in the sample hour) from anything
# faster, which is conservatively labelled ``minutely``.
_HOURLY_FIRES_IN_WINDOW = _CADENCE_WINDOW_DAYS * 24  # 672
# ≥ 28 fires in 28 days ⇒ at least daily.
_DAILY_FIRES_IN_WINDOW = _CADENCE_WINDOW_DAYS
# ≥ 4 fires in 28 days ⇒ at least weekly; 2-3 fires/week already exceed a
# weekly allowance, so anything below ``daily`` but ≥ 2/week maps to
# ``daily`` (conservative: never understate the delivery rate).
_DAILY_MIN_FIRES_IN_WINDOW = 8
_WEEKLY_FIRES_IN_WINDOW = 4


def frequency_rank(frequency: str) -> int:
    """Rank *frequency* by how often it fires (higher = more frequent).

    Unknown frequencies rank ``0`` — never treated as more frequent than
    a known ceiling (conservative for the *subscription* side, strict
    enough for the *requested* side since unknown requested frequencies
    cannot exceed rank 0 subscriptions).
    """
    return _FREQUENCY_RANK.get(str(frequency or "").strip().lower(), 0)


def derive_cadence(cron_expression: str, *, now: datetime | None = None) -> str:
    """Derive the real trigger cadence of a cron expression (issue #687).

    Counts actual fire times via :class:`croniter` over fixed sample
    windows and maps the counts onto the :data:`_FREQUENCY_RANK` ladder,
    always rounding **up** to the more frequent level (the gate must never
    understate how often a schedule delivers):

    - ≥ 672 fires in 28 days (≥ 1/hour on average): ``minutely`` when more
      than one fire lands in a 1-hour sample, else ``hourly``;
    - ≥ 28 fires in 28 days (≥ 1/day): ``daily``;
    - ≥ 8 fires in 28 days (≥ 2/week): ``daily`` — two or more deliveries
      a week already exceed a weekly allowance;
    - ≥ 4 fires in 28 days: ``weekly``;
    - ≥ 1 fire in 28 days: ``monthly``;
    - no fire in 28 days: ``quarterly`` (or rarer).

    Parameters
    ----------
    cron_expression:
        A cron expression already validated with ``croniter.is_valid`` by
        the caller.  Invalid expressions raise :class:`ValueError` — both
        call sites (CLI ``cron add-delivery`` / MCP ``add_delivery_schedule``)
        validate before consulting the gate.
    now:
        Sample-window base time; defaults to the current local time.
        Pass a fixed ``now`` in tests for determinism.

    Returns
    -------
    str
        One of the :data:`_FREQUENCY_RANK` levels.
    """
    base = now or datetime.now()
    from croniter import croniter  # lazy — same idiom as scheduler.py / cron.py

    if not croniter.is_valid(cron_expression):
        raise ValueError(f"invalid cron expression: {cron_expression!r}")

    def _count_fires(window: timedelta, cap: int) -> int:
        iterator = croniter(cron_expression, base)
        count = 0
        next_fire = iterator.get_next(datetime)
        while next_fire <= base + window:
            count += 1
            if count >= cap:
                break
            next_fire = iterator.get_next(datetime)
        return count

    fires_in_window = _count_fires(timedelta(days=_CADENCE_WINDOW_DAYS), _HOURLY_FIRES_IN_WINDOW)
    if fires_in_window >= _HOURLY_FIRES_IN_WINDOW:
        # Hourly or faster — separate hourly from sub-hourly with a 1 h sample.
        return "minutely" if _count_fires(timedelta(hours=1), 2) >= 2 else "hourly"
    if fires_in_window >= _DAILY_FIRES_IN_WINDOW:
        return "daily"
    if fires_in_window >= _DAILY_MIN_FIRES_IN_WINDOW:
        return "daily"
    if fires_in_window >= _WEEKLY_FIRES_IN_WINDOW:
        return "weekly"
    if fires_in_window >= 1:
        return "monthly"
    return "quarterly"


def _frequency_error_envelope(requested: str, allowed: str) -> dict[str, Any]:
    message = (
        f"Free-tier limit reached: schedule frequency '{requested}' exceeds "
        f"the '{allowed}' allowance of the free plan. Upgrade to a premium "
        "subscription to schedule more frequent deliveries."
    )
    return error_response(
        ErrorCode.FREE_TIER_LIMIT,
        message=message,
        actionable=True,
    )


def check_schedule_frequency(
    user_id: str,
    frequency: str,
    *,
    raise_on_block: bool = False,
) -> dict[str, Any]:
    """Gate a delivery-schedule frequency against the user's subscription.

    Parameters
    ----------
    user_id:
        Named end-user bound to the schedule. ``""`` immediately allows
        (batch/unattended schedules carry no user quota).
    frequency:
        The schedule's **real trigger cadence** — since #687 the call sites
        pass :func:`derive_cadence` over the cron expression, not the
        ``period`` field (which keeps its "content window" meaning).  One
        of the :data:`_FREQUENCY_RANK` levels.
    raise_on_block:
        When ``True``, raise :class:`FreeTierLimitError` on breach.

    Returns
    -------
    dict
        ``{allowed: bool, reason: str}`` plus ``code`` / ``message`` /
        ``actionable`` when blocked (the error-envelope fields).
    """
    # --- Named-user only: unattended schedules skip the gate -------------
    if not user_id:
        return {"allowed": True, "reason": "No user context (batch path)"}

    subscription = _subscription_for_user(user_id)
    if not _is_limited_subscription(subscription):
        return {
            "allowed": True,
            "reason": "User is not on a limited plan",
        }

    max_frequency = str(getattr(subscription, "max_frequency", "") or "weekly").strip().lower()
    requested = str(frequency or "").strip().lower()

    if frequency_rank(requested) > frequency_rank(max_frequency):
        envelope = _frequency_error_envelope(requested, max_frequency)
        if raise_on_block:
            raise FreeTierLimitError(envelope)
        return {
            "allowed": False,
            "reason": "Schedule frequency exceeds plan allowance",
            **envelope["error"],
        }

    return {
        "allowed": True,
        "reason": "Schedule frequency within plan allowance",
    }
