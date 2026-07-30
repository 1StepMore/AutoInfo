"""Spotify Web API handler.

Fetches podcast episodes from the Spotify Web API using OAuth2
client-credentials flow.  Supports two modes:

* **Show episodes**: ``GET /shows/{show_id}/episodes?limit=N``
* **Search**: ``GET /search?q=QUERY&type=show,episode&limit=N``

Requires ``AUTOINFO_SPOTIFY_CLIENT_ID`` and ``AUTOINFO_SPOTIFY_CLIENT_SECRET``
environment variables (or passed via config dict).
"""

from __future__ import annotations

import base64
import logging
import time
import uuid
from typing import Any
from urllib.parse import urlencode

import httpx

from autoinfo.collectors.base import BaseHandler
from autoinfo.models import Item

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOKEN_URL: str = "https://accounts.spotify.com/api/token"
SHOWS_EPISODES_URL: str = "https://api.spotify.com/v1/shows/{show_id}/episodes"
SEARCH_URL: str = "https://api.spotify.com/v1/search"
DEFAULT_TIMEOUT: int = 30  # seconds
DEFAULT_LIMIT: int = 10
MAX_RETRIES: int = 3
RETRY_DELAYS: list[int] = [2, 4, 8]


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class SpotifyHandler(BaseHandler):
    """Fetch Spotify podcast episodes via OAuth2 client-credentials.

    Usage::

        handler = SpotifyHandler({
            "client_id": "my-client-id",
            "client_secret": "my-secret",
            "show_id": "5CfCWKI5pZ28U0uOzXkDHe",
        })
        episodes = handler.fetch(limit=10)
        items = [handler.to_item(ep) for ep in episodes]

        # Search mode
        handler = SpotifyHandler({
            "client_id": "my-client-id",
            "client_secret": "my-secret",
        })
        episodes = handler.fetch(limit=10, query="machine learning")
    """

    source_type: str = "spotify"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialise handler.

        Args:
            config: Dictionary with keys:
                - ``client_id``: Spotify app client ID (falls back to env
                  var ``AUTOINFO_SPOTIFY_CLIENT_ID``)
                - ``client_secret``: Spotify app secret (falls back to env
                  var ``AUTOINFO_SPOTIFY_CLIENT_SECRET``)
                - ``show_id``: Spotify show ID for episode listing
                  (optional — use with search mode otherwise)
                - ``market``: ISO 3166-1 alpha-2 country code
                  (default ``"US"``)
        """
        import os

        if config is None:
            config = {}
        self.config: dict[str, Any] = config

        self.client_id: str = config.get("client_id", "") or os.environ.get(
            "AUTOINFO_SPOTIFY_CLIENT_ID", ""
        )
        self.client_secret: str = config.get("client_secret", "") or os.environ.get(
            "AUTOINFO_SPOTIFY_CLIENT_SECRET", ""
        )
        self.show_id: str = config.get("show_id", "")
        self.market: str = config.get("market", "US")

        self._access_token: str = ""
        self._token_expiry: float = 0.0
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # OAuth2 authentication
    # ------------------------------------------------------------------

    def _authenticate(self) -> str:
        """Obtain or refresh an OAuth2 access token via client credentials.

        Returns:
            An access token string.

        Raises:
            ValueError: If ``client_id`` or ``client_secret`` is missing.
            httpx.HTTPStatusError: On HTTP 4xx/5xx from the token endpoint.
            httpx.RequestError: On network/timeout errors.
        """
        # Return cached token if still valid (>60s margin)
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Spotify OAuth2 requires client_id and client_secret in config "
                "or AUTOINFO_SPOTIFY_CLIENT_ID / AUTOINFO_SPOTIFY_CLIENT_SECRET env vars."
            )

        auth_str = f"{self.client_id}:{self.client_secret}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()

        headers: dict[str, str] = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data: dict[str, str] = {
            "grant_type": "client_credentials",
        }

        try:
            resp = httpx.post(
                TOKEN_URL,
                headers=headers,
                data=data,
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Spotify OAuth2 token request failed: %s", exc)
            raise

        token_data = resp.json()
        self._access_token = token_data.get("access_token", "")
        expires_in = token_data.get("expires_in", 3600)
        self._token_expiry = time.time() + expires_in

        if not self._access_token:
            raise ValueError("Spotify OAuth2 response missing access_token.")

        return self._access_token

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        """Block until the next request is allowed (Spotify free-tier: ~3 rps)."""
        if self._last_request_time == 0.0:
            self._last_request_time = time.time()
            return

        min_interval = 0.34  # ~3 requests per second
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    # ------------------------------------------------------------------
    # HTTP request with auth and retry
    # ------------------------------------------------------------------

    def _request(self, url: str) -> httpx.Response:
        """Issue a GET request with OAuth2 Bearer auth, rate limiting, and retry.

        Args:
            url: Fully qualified URL to fetch.

        Returns:
            HTTP response object.

        Raises:
            httpx.HTTPStatusError: On 4xx/5xx after retries exhausted.
            httpx.RequestError: On network/timeout after retries.
        """
        last_exc: Exception | None = None

        for attempt in range(MAX_RETRIES):
            self._wait_for_rate_limit()
            try:
                token = self._authenticate()
                headers: dict[str, str] = {
                    "Authorization": f"Bearer {token}",
                }
                response = httpx.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)

                # If token expired during request (401), clear cache and retry
                if response.status_code == 401 and attempt < MAX_RETRIES - 1:
                    logger.debug("Spotify token expired; refreshing and retrying.")
                    self._access_token = ""
                    self._token_expiry = 0.0
                    continue

                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(RETRY_DELAYS[attempt])
            except httpx.HTTPStatusError:
                # Do not retry non-401 4xx/5xx — propagate immediately
                raise

        raise RuntimeError("Unexpected: all retries exhausted") from last_exc

    # ------------------------------------------------------------------
    # Field mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_audio_url(episode: dict[str, Any]) -> str:
        """Extract best available audio URL from an episode's ``audio_preview_url``.

        Falls back to empty string if unavailable.
        """
        return episode.get("audio_preview_url", "") or ""

    @staticmethod
    def _map_episode(episode: dict[str, Any]) -> dict[str, Any]:
        """Map a raw Spotify episode dict to standardised fields.

        Args:
            episode: Raw episode dict from the Spotify API response
                (an item from ``items``).

        Returns:
            Dict with keys: ``id``, ``title``, ``content``, ``author``,
            ``published_date``, ``duration_ms``, ``language``, ``source_url``,
            ``audio_url``, ``show_id``, ``show_name``.
        """
        show: dict[str, Any] = episode.get("show", {})

        # language comes from a list of ISO codes
        languages: list[str] = episode.get("languages", [])
        language: str = languages[0] if languages else ""

        external_urls: dict[str, str] = episode.get("external_urls", {})

        return {
            "id": episode.get("id") or "",
            "title": episode.get("name") or "",
            "content": episode.get("description") or "",
            "author": episode.get("publisher") or show.get("publisher") or "",
            "published_date": episode.get("release_date") or "",
            "duration_ms": episode.get("duration_ms") or 0,
            "language": language,
            "source_url": external_urls.get("spotify") or "",
            "audio_url": SpotifyHandler._extract_audio_url(episode),
            "show_id": show.get("id") or "",
            "show_name": show.get("name") or "",
            "show_description": show.get("description") or "",
            "explicit": episode.get("explicit", False),
            "episode_type": episode.get("type", "episode"),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(
        self,
        limit: int = DEFAULT_LIMIT,
        query: str = "",
        show_id: str = "",
    ) -> list[dict[str, Any]]:
        """Fetch podcast episodes from Spotify.

        When *query* is provided, uses the search endpoint:
        ``GET /search?q=QUERY&type=show,episode&limit=N``.

        Otherwise, when either *show_id* or the configured ``show_id``
        is set, uses the shows endpoint:
        ``GET /shows/{show_id}/episodes?limit=N``.

        Args:
            limit: Maximum number of episodes to return (default 10).
            query: Search term (optional — triggers search mode).
            show_id: Spotify show ID (optional — overrides configured
                ``show_id``; triggers show episodes mode).

        Returns:
            List of parsed episode dicts, each with standardised fields.
            Returns an empty list on error.
        """
        if limit <= 0:
            return []

        effective_show_id = show_id or self.show_id

        if not query and not effective_show_id:
            logger.warning(
                "Spotify fetch requires either a query or show_id "
                "(configured or passed as argument)."
            )
            return []

        # Attempt authentication early for fast failure
        try:
            self._authenticate()
        except Exception:
            logger.exception("Spotify OAuth2 authentication failed.")
            return []

        try:
            if query:
                episodes = self._fetch_search(query, limit)
            else:
                episodes = self._fetch_show_episodes(effective_show_id, limit)
        except Exception:
            logger.exception("Spotify fetch failed.")
            return []

        return episodes[:limit]

    def _fetch_show_episodes(self, show_id: str, limit: int) -> list[dict[str, Any]]:
        """Fetch episodes for a specific show.

        Args:
            show_id: Spotify show ID.
            limit: Maximum episodes to return.

        Returns:
            List of mapped episode dicts.
        """
        url = SHOWS_EPISODES_URL.format(show_id=show_id)
        params: dict[str, Any] = {
            "limit": min(limit, 50),  # Spotify max is 50 per page
            "market": self.market,
        }
        url = f"{url}?{urlencode(params)}"

        resp = self._request(url)
        data = resp.json()
        items: list[dict[str, Any]] = data.get("items") or []

        return [self._map_episode(item) for item in items]

    def _fetch_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Search for shows/episodes matching a query.

        Args:
            query: Search term.
            limit: Maximum episodes to return.

        Returns:
            List of mapped episode dicts.
        """
        all_episodes: list[dict[str, Any]] = []
        page_limit = min(limit, 50)
        offset = 0

        while len(all_episodes) < limit:
            requested = min(page_limit, limit - len(all_episodes))
            params: dict[str, Any] = {
                "q": query,
                "type": "show,episode",
                "limit": requested,
                "market": self.market,
                "offset": offset,
            }
            url = f"{SEARCH_URL}?{urlencode(params)}"

            resp = self._request(url)
            data = resp.json()

            # Search endpoint returns shows and episodes separately under "episodes" key
            episodes_data: dict[str, Any] = data.get("episodes") or {}
            items: list[dict[str, Any]] = episodes_data.get("items") or []
            if not items:
                break

            for item in items:
                all_episodes.append(self._map_episode(item))

            # Check if more results available
            total: int = episodes_data.get("total", 0)
            offset += len(items)
            if offset >= total:
                break

        return all_episodes

    # ------------------------------------------------------------------
    # Conversion to Item
    # ------------------------------------------------------------------

    def to_item(self, episode: dict[str, Any]) -> Item:
        """Convert a parsed episode dict to an :class:`Item` dataclass.

        Args:
            episode: Parsed episode dict as returned by :meth:`fetch`.

        Returns:
            An :class:`Item` instance populated from the episode data.
        """
        ep_id: str = episode.get("id") or ""
        title: str = episode.get("title") or ""

        return Item(
            id=ep_id or str(uuid.uuid4()),
            source_name="spotify",
            source_type="spotify",
            source_platform="spotify",
            source_url=episode.get("source_url") or "",
            title=title,
            content=episode.get("content") or "",
            content_type="text",
            collected_at=episode.get("published_date") or "",
            language=episode.get("language") or "",
            domain="",
            topic_tags=[],
            raw_data={
                "spotify_id": ep_id,
                "author": episode.get("author") or "",
                "published_date": episode.get("published_date") or "",
                "duration_ms": episode.get("duration_ms") or 0,
                "language": episode.get("language") or "",
                "audio_url": episode.get("audio_url") or "",
                "show_id": episode.get("show_id") or "",
                "show_name": episode.get("show_name") or "",
                "show_description": episode.get("show_description") or "",
                "explicit": episode.get("explicit", False),
                "episode_type": episode.get("episode_type", "episode"),
            },
        )
