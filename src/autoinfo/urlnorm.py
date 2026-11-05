"""URL canonicalization for dedup comparison.

Collection-time dedup compares URLs as raw strings, so the same article
re-surfacing with tracking parameters (``utm_*``, ``fbclid``, ...), a
trailing slash, a different default port or parameter order slips past
every dedup layer and is re-ingested as "new" (goal doc 2026-11-06,
short-term #1 — the mechanism behind "近7天新增" being dominated by old
content).  :func:`canonical_url` gives every comparison site one shared
normal form.

The canonical form is used for *comparison only* — stored URLs keep
their original spelling for provenance.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Query parameters that never change the identity of a content page —
# campaign/attribution trackers appended by feeds, mail clients and
# social platforms.  ``utm_*`` and friends are matched by prefix; the
# rest by exact (case-insensitive) name.
_TRACKING_PARAM_EXACT: frozenset[str] = frozenset(
    {
        "fbclid",
        "gclid",
        "dclid",
        "msclkid",
        "twclid",
        "yclid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "mkt_tok",
        "_hsenc",
        "_hsmi",
        "vero_id",
        "vero_conv",
        "wickedid",
        "trk_contact",
        "trk_msg",
        "trk_module",
        "trk_sid",
        "s_cid",
        "elqtrackid",
        "elqtrack",
    }
)

_TRACKING_PARAM_PREFIXES: tuple[str, ...] = (
    "utm_",
    "pk_",
    "mtm_",
    "matomo_",
    "hsa_",
)

_DEFAULT_PORTS: dict[str, str] = {"http": "80", "https": "443"}


def is_tracking_param(name: str) -> bool:
    """True when query parameter *name* is a known tracking/attribution key."""
    lowered = name.lower()
    return lowered in _TRACKING_PARAM_EXACT or lowered.startswith(_TRACKING_PARAM_PREFIXES)


def canonical_url(url: str) -> str:
    """Return the dedup canonical form of *url* (best effort).

    Normalizes, in order: surrounding whitespace, scheme/host case,
    default ports (80/http, 443/https), the fragment, tracking query
    parameters, remaining query-parameter order (sorted), and the
    trailing slash of a non-root path.  Non-http(s) URLs and unparseable
    input are returned stripped but otherwise unchanged —
    canonicalization must never lose a URL.
    """
    if not url:
        return url or ""
    cleaned = url.strip()
    if not cleaned:
        return cleaned
    try:
        parts = urlsplit(cleaned)
    except ValueError:
        return cleaned
    scheme = parts.scheme.lower()
    if scheme not in _DEFAULT_PORTS:
        # mailto:, ftp:, magnet:, relative refs — nothing to canonicalize.
        return cleaned

    netloc = _strip_default_port(parts.netloc.lower(), scheme)

    try:
        query_pairs = [
            (name, value)
            for name, value in parse_qsl(parts.query, keep_blank_values=True)
            if not is_tracking_param(name)
        ]
    except ValueError:
        query_pairs = []
    query_pairs.sort()

    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/") or "/"

    return urlunsplit((scheme, netloc, path, urlencode(query_pairs), ""))


def _strip_default_port(netloc: str, scheme: str) -> str:
    """Drop ``:80``/``:443`` from *netloc* when present (IPv6-safe)."""
    if ":" not in netloc:
        return netloc
    host, sep, port = netloc.rpartition(":")
    if not sep or not port.isdigit() or not host:
        return netloc
    if _DEFAULT_PORTS.get(scheme) == port:
        return host
    return netloc
