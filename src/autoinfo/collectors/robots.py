"""Shared robots.txt gate for URL-fetching collectors.

Why this module exists (2026-10-02, after an independent cross-review):

    ``robots_allows`` / ``_parse_robots_rules`` lived **inside**
    ``edx_sitemap.py`` as module-private helpers, so the only collector that
    could respect robots.txt was the one that happened to define them.  Every
    other page-fetching collector (``web``, ``web_playwright``, ``pdf``,
    ``http_api``) crawled with **no robots check at all** — not because anyone
    decided to ignore robots, but because there was no shared place to put it.
    A per-collector helper is not an enforcement point; this module is.

Scope — where robots.txt applies, and where it does not
-------------------------------------------------------
* **Applies**: fetching arbitrary/bulk web pages or feeds (``web``,
  ``web_playwright``, ``pdf``, ``rss``, ``edx_sitemap``, …).  This module is
  for those.
* **Does not apply**: calling a documented, authenticated **API** under its own
  terms of service (PubMed E-utilities, OpenAlex, CrossRef, SEC EDGAR, …).
  robots.txt governs crawlers, not API clients; adding a robots gate there
  would be cargo-culting, not compliance.  Those collectors are out of scope.

Group structure and selection (RFC 9309 §2.2.1 / §2.2.2)
--------------------------------------------------------
A robots.txt is a sequence of **groups**.  Consecutive ``User-agent`` lines
belong to the *same* group and share the ``Allow``/``Disallow`` lines that
follow them; a ``User-agent`` line only opens a **new** group once the current
group already carries at least one rule line.  To decide a fetch, a crawler
selects every group whose agent name matches its user-agent token
(case-insensitive); when **no** group matches exactly, it applies all ``*``
(wildcard) groups instead.  The rules of all selected groups are **unioned** —
there is no "last group wins" rule.  Inside the union the longest matching
path wins, with ``Allow`` preferred over ``Disallow`` at equal length, and an
empty ``Disallow`` is a no-op (§2.2.2).

Failure policy (RFC 9309 §2.3.1)
--------------------------------
An **unreachable** robots.txt implies no rules → the fetch is allowed, but the
failure is logged.  That is the RFC's own default, and it is what
``edx_sitemap`` already did; keeping it here means one policy, not two.

Because one origin serves one robots.txt for every path on that origin, the
fetched file is **cached per origin** (``scheme://netloc``) for the lifetime of
the process: a second check against the same origin never issues a second HTTP
request.  Tests clear the cache with :func:`_clear_robots_cache`.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)

#: Default UA token used when matching robots.txt groups (``*`` = all agents).
DEFAULT_USER_AGENT = "*"

ROBOTS_TIMEOUT = 10.0

#: Per-origin robots.txt cache: ``scheme://netloc`` → file text.
#: ``None`` records an unreachable robots.txt (fail-open), so the second check
#: of a broken origin does not re-issue the request either.  Test-only escape
#: hatches: :func:`_clear_robots_cache` and ``check_url_allowed(...,
#: use_cache=False)``.
_ROBOTS_CACHE: dict[str, str | None] = {}


class RobotsDisallowed(RuntimeError):  # noqa: N818 — name fixed by issue #452
    """robots.txt forbids fetching *url*.

    Raised by the gated collectors (``web``, ``web_playwright``, ``pdf``)
    **before** the target page is requested, so ``collect.py`` can record the
    source as ``status="skipped"`` instead of a generic error.
    """

    def __init__(self, url: str, reason: str) -> None:
        self.url = url
        self.reason = reason
        super().__init__(f"robots.txt disallows {url}: {reason}")


def _clear_robots_cache() -> None:
    """Drop every cached robots.txt (test isolation / manual reset)."""
    _ROBOTS_CACHE.clear()


def parse_robots_rules(
    robots_text: str, user_agent: str = DEFAULT_USER_AGENT
) -> list[tuple[str, str]]:
    """Parse robots.txt into ``(type, path)`` rules for *user_agent*.

    Group boundaries (RFC 9309 §2.2.1): consecutive ``User-agent`` lines
    share the rules that follow them; a ``User-agent`` line starts a new
    group only after the current group already has a rule line
    (``Allow``/``Disallow``).  Rule lines appearing before any
    ``User-agent`` line belong to no group and are ignored.

    Group selection: every group whose agent name equals *user_agent*
    (case-insensitive) contributes its rules — the rules of all matching
    groups are **unioned**, and ``*`` groups are ignored when at least one
    group matches exactly.  When **no** group matches, all ``*`` groups are
    unioned instead.  There is no "last matching group wins" rule.
    ``user_agent="*"`` (the default) therefore selects exactly the wildcard
    groups.

    Returns:
        The selected groups' ``(type, path)`` rules in file order.
    """
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    seen_rule = False

    for raw_line in robots_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "user-agent":
            if seen_rule:
                groups.append((agents, rules))
                agents, rules = [], []
                seen_rule = False
            agents.append(value)
        elif field in ("allow", "disallow"):
            if not agents:
                continue  # rule lines outside a group belong to no group
            rules.append((field, value))
            seen_rule = True
    if agents:
        groups.append((agents, rules))

    target = user_agent.lower()
    exact = [
        group_rules
        for group_agents, group_rules in groups
        if any(agent.lower() == target for agent in group_agents)
    ]
    if exact:
        selected = exact  # exact match(es) win — wildcard groups are ignored
    else:
        selected = [
            group_rules
            for group_agents, group_rules in groups
            if any(agent.lower() == "*" for agent in group_agents)
        ]

    rules_out: list[tuple[str, str]] = []
    for group_rules in selected:
        rules_out.extend(group_rules)
    return rules_out


def robots_allows(robots_text: str, url_path: str, user_agent: str = DEFAULT_USER_AGENT) -> bool:
    """Decide whether *url_path* may be crawled under *robots_text*.

    The rules of every group selected for *user_agent* are unioned first
    (see :func:`parse_robots_rules`); within that union the longest-matching
    rule wins, an ``Allow`` and ``Disallow`` of equal length prefer ``Allow``
    (RFC 9309 §2.2.2), an empty ``Disallow`` means "allow all", and no
    matching rule → allowed.
    """
    rules = parse_robots_rules(robots_text, user_agent)
    best: tuple[int, str] | None = None
    for rule_type, rule_path in rules:
        if rule_type == "disallow" and rule_path == "":
            continue  # empty Disallow is a no-op
        if not url_path.startswith(rule_path):
            continue
        if best is None or len(rule_path) > best[0]:
            best = (len(rule_path), rule_type)
        elif len(rule_path) == best[0] and rule_type == "allow":
            best = (len(rule_path), rule_type)
    if best is None:
        return True
    return best[1] == "allow"


def robots_url_for(url: str) -> str | None:
    """Return the robots.txt URL for *url*'s origin, or ``None`` if unusable."""
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


def _decide(robots_text: str, path: str, user_agent: str, robots_url: str) -> tuple[bool, str]:
    """Apply the parsed rules to *path*; returns ``(allowed, detail)``."""
    if robots_allows(robots_text, path, user_agent=user_agent):
        return True, f"allowed by {robots_url}"
    return False, f"disallowed by {robots_url} (path {path!r})"


def check_url_allowed(
    url: str,
    *,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: float = ROBOTS_TIMEOUT,
    transport: httpx.BaseTransport | None = None,
    use_cache: bool = True,
) -> tuple[bool, str]:
    """Whether *url* may be fetched, per its origin's robots.txt.

    Returns ``(allowed, detail)``.  ``detail`` is a human-readable reason
    suitable for a log line.

    The robots.txt of an origin is fetched at most once per process: the
    result is cached under ``scheme://netloc`` (both the file text and an
    unreachable outcome), so checking a second path of the same origin never
    re-issues a request.  Pass ``use_cache=False`` (or call
    :func:`_clear_robots_cache`) to bypass that cache — injected
    ``transport=`` requests are cached like any other.

    Fail-open on an unreachable robots.txt (RFC 9309 §2.3.1: an unreachable
    robots.txt implies no rules), but the failure is logged so it is visible.
    A malformed/unusable URL is allowed here — the fetch itself will fail
    with a clearer error.
    """
    robots_url = robots_url_for(url)
    if robots_url is None:
        return True, f"no usable origin for {url!r} — robots gate skipped"

    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"

    if use_cache and origin in _ROBOTS_CACHE:
        cached = _ROBOTS_CACHE[origin]
        if cached is None:
            return True, f"robots.txt unreachable (cached failure) for {origin}"
        return _decide(cached, path, user_agent, robots_url)

    try:
        if transport is not None:
            # httpx.get() 不接受 transport；注入测试用 transport 时必须走 Client。
            with httpx.Client(transport=transport, timeout=timeout) as client:
                resp = client.get(robots_url)
        else:
            resp = httpx.get(robots_url, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:  # unreachable robots.txt implies no rules
        logger.warning("robots.txt unreachable (%s) for %s — proceeding", exc, url)
        if use_cache:
            _ROBOTS_CACHE[origin] = None
        return True, f"robots.txt unreachable: {exc}"

    robots_text = resp.text
    if use_cache:
        _ROBOTS_CACHE[origin] = robots_text
    return _decide(robots_text, path, user_agent, robots_url)
