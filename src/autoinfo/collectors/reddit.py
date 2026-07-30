"""Reddit search handler.

Fetches posts from Reddit subreddits using OAuth2 client-credentials flow
and the Reddit Search API (``/r/{subreddit}/search`` endpoint).
"""

from __future__ import annotations

import base64
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from autoinfo.collectors.base import BaseHandler
from autoinfo.models import Item

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOKEN_URL: str = "https://www.reddit.com/api/v1/access_token"
SEARCH_URL: str = "https://oauth.reddit.com/r/{subreddit}/search"
DEFAULT_TIMEOUT: int = 30  # seconds
DEFAULT_LIMIT: int = 10
RATE_LIMIT_RPM: int = 100  # Reddit's free-tier limit (requests/min)


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class RedditHandler(BaseHandler):
    """Fetch Reddit posts via OAuth2 client-credentials and search API.

    Usage::

        handler = RedditHandler({
            "client_id": "my-client-id",
            "client_secret": "my-secret",
            "user_agent": "AutoInfo/1.0",
            "subreddits": ["MachineLearning", "artificial"],
            "rate_limit": 60,
        })
        posts = handler.fetch(limit=10)
        items = [handler.to_item(p) for p in posts]
    """

    source_type: str = "reddit"
    source_name: str = "reddit"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialise handler.

        Args:
            config: Dictionary with keys:
                - ``client_id``: Reddit app client ID (required)
                - ``client_secret``: Reddit app secret (required)
                - ``user_agent``: User-Agent header string (required)
                - ``subreddits``: List of subreddit names to search
                  (default ``[]``)
                - ``rate_limit``: Custom requests-per-minute cap
                  (default 100)
        """
        if config is None:
            config = {}
        self.config: dict[str, Any] = config
        self.client_id: str = config.get("client_id", "")
        self.client_secret: str = config.get("client_secret", "")
        self.user_agent: str = config.get("user_agent", "AutoInfo/1.0")
        self.subreddits: list[str] = config.get("subreddits", [])
        self.rate_limit: int = config.get("rate_limit", RATE_LIMIT_RPM)
        self._access_token: str = ""
        self._token_expiry: float = 0.0
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # OAuth2 authentication
    # ------------------------------------------------------------------

    def _authenticate(self) -> str:
        """Obtain or refresh an OAuth2 access token using client credentials.

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
                "Reddit OAuth2 requires client_id and client_secret in config."
            )

        auth_str = f"{self.client_id}:{self.client_secret}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()

        headers: dict[str, str] = {
            "Authorization": f"Basic {auth_b64}",
            "User-Agent": self.user_agent,
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
            logger.error("Reddit OAuth2 token request failed: %s", exc)
            raise

        token_data = resp.json()
        self._access_token = token_data.get("access_token", "")
        expires_in = token_data.get("expires_in", 3600)
        self._token_expiry = time.time() + expires_in

        if not self._access_token:
            raise ValueError("Reddit OAuth2 response missing access_token.")

        return self._access_token

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        """Block until the next request is allowed under the rpm cap."""
        if self._last_request_time == 0.0:
            self._last_request_time = time.time()
            return

        min_interval = 60.0 / self.rate_limit
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    # ------------------------------------------------------------------
    # HTTP request with auth and retry
    # ------------------------------------------------------------------

    def _request(self, url: str) -> httpx.Response:
        """Issue a GET request with OAuth2 auth, rate limiting, and retry.

        Args:
            url: Fully qualified URL to fetch.

        Returns:
            HTTP response object.

        Raises:
            httpx.HTTPStatusError: On 4xx/5xx after retries exhausted.
            httpx.RequestError: On network/timeout after retries.
        """
        max_retries = 3
        retry_delays = [2, 4, 8]
        last_exc: Exception | None = None

        for attempt in range(max_retries):
            self._wait_for_rate_limit()
            try:
                token = self._authenticate()
                headers: dict[str, str] = {
                    "Authorization": f"Bearer {token}",
                    "User-Agent": self.user_agent,
                }
                response = httpx.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt == max_retries - 1:
                    raise
                time.sleep(retry_delays[attempt])

        raise RuntimeError("Unexpected: all retries exhausted") from last_exc

    # ------------------------------------------------------------------
    # Field mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _map_post(post: dict[str, Any]) -> dict[str, Any]:
        """Map a raw Reddit post dict to standardised fields.

        Args:
            post: Raw post dict from the Reddit API response (a child of
                ``data.children``).

        Returns:
            Dict with keys: ``id``, ``title``, ``content``, ``author``,
            ``subreddit``, ``score``, ``num_comments``, ``published_date``,
            ``source_url``.
        """
        data: dict[str, Any] = post.get("data", {})
        created_utc: float = data.get("created_utc", 0.0)
        published_date: str = ""
        if created_utc:
            published_date = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()

        return {
            "id": data.get("name") or "",
            "title": data.get("title") or "",
            "content": data.get("selftext") or "",
            "author": data.get("author") or "",
            "subreddit": data.get("subreddit") or "",
            "score": data.get("score") or 0,
            "num_comments": data.get("num_comments") or 0,
            "published_date": published_date,
            "source_url": data.get("url") or "",
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, query: str = "", limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
        """Search configured subreddits and return parsed post dicts.

        Args:
            query: Search term (optional, defaults to empty string which
                returns recent posts).  A query of ``""`` uses the
                subreddit hot listing instead.
            limit: Maximum total posts to return across all subreddits
                (default 10).

        Returns:
            List of parsed post dicts, each with standardised fields.
            Returns an empty list on error.
        """
        if limit <= 0:
            return []

        if not self.subreddits:
            logger.warning("RedditHandler configured with no subreddits.")
            return []

        # Try to authenticate early so we fail fast if credentials are bad.
        try:
            self._authenticate()
        except Exception:
            logger.exception("Reddit OAuth2 authentication failed.")
            return []

        all_posts: list[dict[str, Any]] = []
        per_sub_limit = max(1, limit // len(self.subreddits))

        for subreddit in self.subreddits:
            if len(all_posts) >= limit:
                break

            remaining = limit - len(all_posts)
            actual_limit = min(per_sub_limit, remaining)

            url = SEARCH_URL.format(subreddit=subreddit)
            url += f"?q={query}&limit={actual_limit}&restrict_sr=1&sort=new"
            if not query:
                # No query — use /new endpoint instead
                url = f"https://oauth.reddit.com/r/{subreddit}/new?limit={actual_limit}"

            try:
                resp = self._request(url)
                data = resp.json()
                children = data.get("data", {}).get("children", [])
                for child in children:
                    post = self._map_post(child)
                    if post["id"]:  # skip malformed posts without ID
                        all_posts.append(post)
                        if len(all_posts) >= limit:
                            break
            except Exception:
                logger.warning(
                    "Reddit fetch failed for subreddit '%s'", subreddit, exc_info=True,
                )
                continue

        return all_posts

    # ------------------------------------------------------------------
    # Conversion to Item
    # ------------------------------------------------------------------

    def to_item(self, post: dict[str, Any]) -> Item:
        """Convert a parsed post dict to an :class:`Item` dataclass.

        Args:
            post: Parsed post dict as returned by :meth:`fetch`.

        Returns:
            An :class:`Item` instance populated from the post data.
        """
        post_id: str = post.get("id") or ""
        title: str = post.get("title") or ""

        return Item(
            id=post_id or str(uuid.uuid4()),
            source_name=self.source_name,
            source_type="reddit",
            source_platform="reddit",
            source_url=post.get("source_url") or "",
            title=title,
            content=post.get("content") or "",
            content_type="text",
            collected_at=post.get("published_date") or "",
            domain="tech-ai-developer",
            topic_tags=[],
            raw_data={
                "reddit_id": post_id,
                "author": post.get("author") or "",
                "subreddit": post.get("subreddit") or "",
                "score": post.get("score") or 0,
                "num_comments": post.get("num_comments") or 0,
                "published_date": post.get("published_date") or "",
            },
        )
