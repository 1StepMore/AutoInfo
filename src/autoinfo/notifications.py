"""Automated notification system for AutoInfo.

Provides two notification workflows:

* ``check_expiring_trials()`` — cron-based check that finds trial users
  expiring within 3 days and sends reminder emails.
* ``notify_content_ready()`` — post-generation hook that notifies a user
  their digest or report is ready.

Both use :func:`autoinfo.email_sender.send_notification` as the transport.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


def check_expiring_trials() -> list[dict[str, Any]]:
    """Find trial users expiring within 3 days and send reminder notifications.

    Queries :mod:`autoinfo.user_store` for all users with ``status="trial"``
    and a ``trial_ends_at`` date within the next 3 days.  Each matching user
    receives one reminder email via :func:`autoinfo.email_sender.send_notification`.

    Errors for individual users are caught and logged — one failing
    notification does not abort the loop.

    Returns
    -------
    list[dict]
        One dict per notified user with keys: ``user_id``, ``name``,
        ``email``, ``trial_ends_at``, ``days_remaining``, ``notified``.
    """
    from autoinfo.email_sender import send_notification
    from autoinfo.user_store import list_profiles

    profiles = list_profiles()
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=3)

    results: list[dict[str, Any]] = []

    for profile in profiles:
        if profile.status != "trial":
            continue

        trial_ends = profile.trial_ends_at
        if not trial_ends:
            continue

        try:
            ends_dt = datetime.fromisoformat(trial_ends)
            if ends_dt.tzinfo is None:
                ends_dt = ends_dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            logger.debug("Unparseable trial_ends_at for user '%s': %s", profile.user_id, trial_ends)
            continue

        if ends_dt <= now:
            continue
        if ends_dt > cutoff:
            continue

        days_remaining = (ends_dt - now).days + 1

        try:
            if profile.email:
                _ = send_notification(
                    to=profile.email,
                    subject="Your trial ends soon",
                    body=(
                        f"Hi {profile.name},\n\n"
                        f"Your AutoInfo trial will end on {ends_dt.strftime('%Y-%m-%d')} "
                        f"({days_remaining} day(s) remaining).\n\n"
                        "Subscribe to keep accessing premium content.\n\n"
                        "— The AutoInfo Team"
                    ),
                )
        except Exception:
            logger.exception("Failed to send trial reminder to '%s'", profile.user_id)
            results.append({
                "user_id": profile.user_id,
                "name": profile.name,
                "email": profile.email,
                "trial_ends_at": trial_ends,
                "days_remaining": days_remaining,
                "notified": False,
            })
            continue

        results.append({
            "user_id": profile.user_id,
            "name": profile.name,
            "email": profile.email,
            "trial_ends_at": trial_ends,
            "days_remaining": days_remaining,
            "notified": True,
        })

    return results


def notify_content_ready(
    user_id: str,
    product_type: str,
    title: str,
) -> dict[str, Any]:
    """Send a content-ready notification to a user.

    Loads the user's profile to obtain their email address, then calls
    :func:`autoinfo.email_sender.send_notification` with a content-ready
    subject and body.

    Parameters
    ----------
    user_id:
        The user's unique identifier.
    product_type:
        Human-readable product label, e.g. ``"digest"`` or ``"report"``.
    title:
        Title of the generated product, included in the notification body.

    Returns
    -------
    dict
        ``{success, user_id, email, product_type, title}`` on success,
        or ``{success: False, error: ..., user_id}`` on failure.
    """
    from autoinfo.email_sender import send_notification
    from autoinfo.user_store import get_profile

    profile = get_profile(user_id)
    if profile is None:
        logger.warning("notify_content_ready: user '%s' not found", user_id)
        return {
            "success": False,
            "error": f"User '{user_id}' not found",
            "user_id": user_id,
        }

    if not profile.email:
        logger.warning("notify_content_ready: user '%s' has no email", user_id)
        return {
            "success": False,
            "error": f"User '{user_id}' has no email address",
            "user_id": user_id,
        }

    try:
        _ = send_notification(
            to=profile.email,
            subject=f"Your {product_type} is ready",
            body=(
                f"Hi {profile.name},\n\n"
                f"Your {product_type} '{title}' has been generated "
                "and is ready to view.\n\n"
                "— The AutoInfo Team"
            ),
        )
    except Exception as exc:
        logger.exception("Failed to send content-ready notification to '%s'", user_id)
        return {
            "success": False,
            "error": str(exc),
            "user_id": user_id,
        }

    return {
        "success": True,
        "user_id": user_id,
        "email": profile.email,
        "product_type": product_type,
        "title": title,
    }
