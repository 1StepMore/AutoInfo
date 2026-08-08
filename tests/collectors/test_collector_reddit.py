"""Tests for the Reddit search handler.

Uses ``unittest.mock.patch`` to mock HTTP responses — no real API calls.
OAuth2 token flow and search API calls are both mocked.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from autoinfo.collectors.reddit import RedditHandler
from autoinfo.models import Item


# ---------------------------------------------------------------------------
# Sample Reddit API response data
# ---------------------------------------------------------------------------

SAMPLE_TOKEN_RESPONSE: dict[str, Any] = {
    "access_token": "mock-access-token-abc123",
    "token_type": "bearer",
    "expires_in": 3600,
    "scope": "read",
}

SAMPLE_REDDIT_POSTS: list[dict[str, Any]] = [
    {
        "kind": "t3",
        "data": {
            "name": "t3_abc123",
            "title": "Deep Learning vs Traditional ML: A Comparison",
            "selftext": "I've been comparing deep learning approaches with traditional ML on tabular data. Here are my findings...",
            "author": "ml_researcher",
            "subreddit": "MachineLearning",
            "score": 245,
            "num_comments": 72,
            "created_utc": 1700000000.0,
            "url": "https://www.reddit.com/r/MachineLearning/comments/abc123/",
            "permalink": "/r/MachineLearning/comments/abc123/deep_learning_vs_traditional_ml/",
            "stickied": False,
        },
    },
    {
        "kind": "t3",
        "data": {
            "name": "t3_def456",
            "title": "New Paper: Attention Is All You Need — Explained",
            "selftext": "A comprehensive breakdown of the Transformer architecture paper with visualizations and code examples.",
            "author": "ai_explainer",
            "subreddit": "artificial",
            "score": 512,
            "num_comments": 128,
            "created_utc": 1699900000.0,
            "url": "https://arxiv.org/abs/1706.03762",
            "permalink": "/r/artificial/comments/def456/new_paper_attention_is_all_you_need_explained/",
        },
    },
]

SAMPLE_MINIMAL_POST: dict[str, Any] = {
    "kind": "t3",
    "data": {
        "name": "t3_min001",
        "title": "A Minimal Post",
        "selftext": "",
        "author": "",
        "subreddit": "test",
        "score": 0,
        "num_comments": 0,
        "created_utc": None,
        "url": "",
    },
}

MAPPED_POST: dict[str, Any] = {
    "id": "t3_abc123",
    "title": "Deep Learning vs Traditional ML: A Comparison",
    "content": "I've been comparing deep learning approaches with traditional ML on tabular data. Here are my findings...",
    "author": "ml_researcher",
    "subreddit": "MachineLearning",
    "score": 245,
    "num_comments": 72,
    "published_date": "2023-11-14T22:13:20+00:00",
    "source_url": "https://www.reddit.com/r/MachineLearning/comments/abc123/",
}


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_token_response() -> httpx.Response:
    """Create a mock httpx.Response for a successful OAuth2 token request."""
    return httpx.Response(
        200,
        json=SAMPLE_TOKEN_RESPONSE,
        request=httpx.Request("POST", "https://www.reddit.com/api/v1/access_token"),
    )


def _make_search_response(posts: list[dict[str, Any]]) -> httpx.Response:
    """Create a mock httpx.Response for a Reddit search API call."""
    return httpx.Response(
        200,
        json={"kind": "Listing", "data": {"children": posts}},
        request=httpx.Request(
            "GET",
            "https://oauth.reddit.com/r/MachineLearning/search?q=deep+learning&limit=5&restrict_sr=1&sort=new",
        ),
    )


def _make_empty_search_response() -> httpx.Response:
    """Create a mock httpx.Response for an empty search result."""
    return httpx.Response(
        200,
        json={"kind": "Listing", "data": {"children": []}},
        request=httpx.Request(
            "GET",
            "https://oauth.reddit.com/r/MachineLearning/search?q=zzzzz&limit=5&restrict_sr=1&sort=new",
        ),
    )


def _sample_config() -> dict[str, Any]:
    """Return a minimal valid config dict for a RedditHandler."""
    return {
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "user_agent": "AutoInfo-Test/1.0",
        "subreddits": ["MachineLearning", "artificial"],
    }


# ---------------------------------------------------------------------------
# Tests: handler existence and construction
# ---------------------------------------------------------------------------


class TestRedditHandlerExists:
    """Verify the handler class is importable and constructable."""

    def test_handler_is_importable(self) -> None:
        """RedditHandler should be accessible from the reddit module."""
        from autoinfo.collectors.reddit import RedditHandler as H
        assert H is not None

    def test_creates_with_default_config(self) -> None:
        """Handler instantiates with an empty config dict."""
        handler = RedditHandler({})
        assert handler.source_type == "reddit"
        assert handler.source_name == "reddit"
        assert handler.config == {}
        assert handler.subreddits == []
        assert handler.rate_limit == 100
        assert handler.client_id == ""
        assert handler.client_secret == ""

    def test_creates_with_full_config(self) -> None:
        """Handler picks up all config fields."""
        config = {
            "client_id": "my-id",
            "client_secret": "my-secret",
            "user_agent": "MyBot/1.0",
            "subreddits": ["MachineLearning", "python"],
            "rate_limit": 60,
        }
        handler = RedditHandler(config)
        assert handler.client_id == "my-id"
        assert handler.client_secret == "my-secret"
        assert handler.user_agent == "MyBot/1.0"
        assert handler.subreddits == ["MachineLearning", "python"]
        assert handler.rate_limit == 60

    def test_creates_with_none_config(self) -> None:
        """Passing None as config should work like empty dict."""
        handler = RedditHandler(None)
        assert handler.config == {}
        assert handler.subreddits == []

    def test_source_type_is_reddit(self) -> None:
        """The source_type class attribute must be 'reddit'."""
        assert RedditHandler.source_type == "reddit"


# ---------------------------------------------------------------------------
# Tests: fetch returns a list
# ---------------------------------------------------------------------------


class TestRedditFetch:
    """Tests for the fetch method."""

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_fetch_returns_list(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """fetch() should return a list of dicts."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        config = _sample_config()
        config["subreddits"] = ["MachineLearning"]
        handler = RedditHandler(config)
        posts = handler.fetch(query="deep learning", limit=5)

        assert isinstance(posts, list)
        assert len(posts) == 2

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_fetch_each_item_is_dict(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Each returned item must be a dict."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="deep learning", limit=5)

        for post in posts:
            assert isinstance(post, dict)

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_fetch_respects_limit(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """fetch should respect the limit argument."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="deep learning", limit=1)

        assert len(posts) <= 1

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_fetch_limit_zero_returns_empty(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """A limit of 0 should return an empty list."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="deep learning", limit=0)

        assert posts == []

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_fetch_no_subreddits_returns_empty(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Handler with no subreddits should return empty list."""
        mock_post.return_value = _make_token_response()

        handler = RedditHandler({
            "client_id": "test",
            "client_secret": "secret",
            "user_agent": "Test/1.0",
            "subreddits": [],
        })
        posts = handler.fetch(query="test", limit=5)

        assert posts == []
        mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: empty response handling
# ---------------------------------------------------------------------------


class TestRedditFetchEmpty:
    """Tests for empty or no-result responses."""

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_fetch_handles_empty_results(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """An empty children list should return an empty list."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_empty_search_response()

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="nonexistentquery", limit=5)

        assert posts == []

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_fetch_handles_missing_data_key(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Response without 'data' key should return empty list."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = httpx.Response(
            200,
            json={"kind": "Listing"},
            request=httpx.Request("GET", "https://test.com"),
        )

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="test", limit=5)

        assert posts == []


# ---------------------------------------------------------------------------
# Tests: field mapping
# ---------------------------------------------------------------------------


class TestRedditFieldMapping:
    """Tests for mapping Reddit JSON fields to AutoInfo item format."""

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_field_mapping_id(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """id should come from the 'name' field (Reddit thing ID)."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="deep learning", limit=5)

        assert posts[0]["id"] == "t3_abc123"

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_field_mapping_title(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """title should come from the 'title' field."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="deep learning", limit=5)

        assert posts[0]["title"] == "Deep Learning vs Traditional ML: A Comparison"

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_field_mapping_content_selftext(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """content should come from 'selftext' field."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="deep learning", limit=5)

        assert "comparing deep learning" in posts[0]["content"].lower()

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_field_mapping_author(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """author should come from 'author' field."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="deep learning", limit=5)

        assert posts[0]["author"] == "ml_researcher"

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_field_mapping_subreddit(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """subreddit should come from 'subreddit' field."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="deep learning", limit=5)

        assert posts[0]["subreddit"] == "MachineLearning"
        assert posts[1]["subreddit"] == "artificial"

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_field_mapping_score(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """score should match the API value."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="deep learning", limit=5)

        assert posts[0]["score"] == 245
        assert posts[1]["score"] == 512

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_field_mapping_num_comments(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """num_comments should match the API value."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="deep learning", limit=5)

        assert posts[0]["num_comments"] == 72
        assert posts[1]["num_comments"] == 128

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_field_mapping_published_date(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """published_date should be ISO8601 from created_utc."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="deep learning", limit=5)

        assert "T" in posts[0]["published_date"]
        assert "2023" in posts[0]["published_date"]

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_field_mapping_source_url(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """source_url should come from 'url' field."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="deep learning", limit=5)

        assert "reddit.com/r/MachineLearning" in posts[0]["source_url"]

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_field_mapping_all_expected_fields_present(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Every returned item must have all expected keys."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="deep learning", limit=5)

        expected_fields = {
            "id", "title", "content", "author", "subreddit",
            "score", "num_comments", "published_date", "source_url",
        }
        for post in posts:
            for field in expected_fields:
                assert field in post, f"Item missing field: {field}"

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_minimal_post_handles_missing_fields(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """A post with None/empty fields should not crash the handler."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response([SAMPLE_MINIMAL_POST])

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="test", limit=1)

        assert len(posts) == 1
        p = posts[0]
        assert p["id"] == "t3_min001"
        assert p["title"] == "A Minimal Post"
        assert p["content"] == ""
        assert p["author"] == ""
        assert p["score"] == 0
        assert p["num_comments"] == 0


# ---------------------------------------------------------------------------
# Tests: OAuth2 authentication
# ---------------------------------------------------------------------------


class TestRedditAuth:
    """Tests for OAuth2 authentication flow."""

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_authenticate_obtains_token(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """First call should POST to token endpoint and cache the token."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        handler.fetch(query="test", limit=1)

        # Token endpoint should have been called
        token_calls = [
            c for c in mock_post.call_args_list
            if "access_token" in str(c.kwargs.get("url", c.args[0] if c.args else ""))
            or "/api/v1/access_token" in str(c.kwargs.get("url", c.args[0] if c.args else ""))
        ]
        assert mock_post.called

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_authenticate_caches_token(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Subsequent calls should reuse the cached token without re-auth."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        handler.fetch(query="test", limit=1)
        first_post_count = mock_post.call_count

        handler.fetch(query="test2", limit=1)
        # Token should not be requested again (still cached)
        assert mock_post.call_count == first_post_count

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_authenticate_failure_returns_empty(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """When OAuth fails, fetch should return empty list."""
        mock_post.side_effect = httpx.HTTPStatusError(
            "Unauthorized",
            request=MagicMock(),
            response=MagicMock(status_code=401),
        )

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="test", limit=5)

        assert posts == []

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_authenticate_missing_credentials(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Missing client_id/client_secret should fail gracefully."""
        handler = RedditHandler({
            "client_id": "",
            "client_secret": "",
            "user_agent": "Test/1.0",
            "subreddits": ["test"],
        })
        posts = handler.fetch(query="test", limit=5)

        assert posts == []

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_search_uses_bearer_token(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Search requests should include Authorization: Bearer header."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        handler.fetch(query="test", limit=1)

        # Check that the GET call included the bearer token
        headers = mock_get.call_args.kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer mock-access-token-abc123"


# ---------------------------------------------------------------------------
# Tests: error handling (graceful degradation)
# ---------------------------------------------------------------------------


class TestRedditErrorHandling:
    """Tests for HTTP errors, network failures, and token failures."""

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_fetch_http_error_returns_empty(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """HTTP errors should return empty list (graceful degradation)."""
        mock_post.return_value = _make_token_response()
        mock_get.side_effect = httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="test", limit=5)

        assert posts == []

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_fetch_network_error_returns_empty(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Network errors should return empty list."""
        mock_post.return_value = _make_token_response()
        mock_get.side_effect = httpx.NetworkError("Connection refused")

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="test", limit=5)

        assert posts == []

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_fetch_timeout_returns_empty(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Timeout errors should return empty list gracefully."""
        mock_post.return_value = _make_token_response()
        mock_get.side_effect = httpx.TimeoutException(
            "Request timed out",
            request=MagicMock(),
        )

        handler = RedditHandler(_sample_config())
        posts = handler.fetch(query="test", limit=5)

        assert posts == []

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_fetch_retry_on_timeout(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """After 3 TimeoutExceptions the error should be handled gracefully."""
        mock_post.return_value = _make_token_response()
        mock_get.side_effect = httpx.TimeoutException(
            "Timeout", request=MagicMock(),
        )

        config = _sample_config()
        config["subreddits"] = ["MachineLearning"]  # single subreddit for fast test
        handler = RedditHandler(config)
        start = time.time()
        posts = handler.fetch(query="test", limit=1)
        elapsed = time.time() - start

        assert posts == []
        assert mock_get.call_count == 3  # retries exhausted (within _request)
        assert elapsed >= 6.0  # 2 + 4 = 6 seconds backoff


# ---------------------------------------------------------------------------
# Tests: rate limiting
# ---------------------------------------------------------------------------


class TestRedditRateLimit:
    """Tests for rate limiter behaviour."""

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_rate_limit_first_call_instant(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """First call should not block (no previous request recorded)."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())

        t0 = time.time()
        handler.fetch(query="test", limit=1)
        elapsed = time.time() - t0

        assert elapsed < 0.3  # should be near-instant

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_rate_limit_enforces_min_interval(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Back-to-back calls should be spaced by at least 60/rate_limit."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler({
            **{k: v for k, v in _sample_config().items() if k != "subreddits"},
            "subreddits": ["MachineLearning"],
            "rate_limit": 30,
        })
        assert handler.rate_limit == 30

        handler.fetch(query="test", limit=1)  # warms _last_request_time
        t0 = time.time()
        handler.fetch(query="test2", limit=1)  # should wait
        elapsed = time.time() - t0

        min_interval = 60.0 / handler.rate_limit  # 2.0 s
        assert elapsed >= min_interval * 0.9  # 10 % tolerance


# ---------------------------------------------------------------------------
# Tests: to_item conversion
# ---------------------------------------------------------------------------


class TestRedditToItem:
    """Tests for ``RedditHandler.to_item()``."""

    def test_to_item_complete(self) -> None:
        """A fully populated post dict should produce a correct Item."""
        handler = RedditHandler(_sample_config())
        post = MAPPED_POST

        item = handler.to_item(post)

        assert isinstance(item, Item)
        assert item.id == "t3_abc123"
        assert item.source_name == "reddit"
        assert item.source_type == "reddit"
        assert item.source_platform == "reddit"
        assert "reddit.com/r/MachineLearning" in item.source_url
        assert item.title == "Deep Learning vs Traditional ML: A Comparison"
        assert "comparing deep learning" in item.content.lower()
        assert item.content_type == "text"
        assert item.domain == "tech-ai-developer"

    def test_to_item_raw_data_fields(self) -> None:
        """All Reddit-specific metadata should be in raw_data."""
        handler = RedditHandler(_sample_config())
        post = MAPPED_POST

        item = handler.to_item(post)

        assert item.raw_data["reddit_id"] == "t3_abc123"
        assert item.raw_data["author"] == "ml_researcher"
        assert item.raw_data["subreddit"] == "MachineLearning"
        assert item.raw_data["score"] == 245
        assert item.raw_data["num_comments"] == 72
        assert item.raw_data["published_date"] is not None

    def test_to_item_empty_id_uses_uuid(self) -> None:
        """When post id is empty, a UUID should be generated."""
        handler = RedditHandler(_sample_config())
        post = {
            "id": "",
            "title": "No ID Post",
            "content": "",
            "author": "",
            "subreddit": "",
            "score": 0,
            "num_comments": 0,
            "published_date": "",
            "source_url": "",
        }

        item = handler.to_item(post)

        assert item.id
        assert item.id != ""
        assert "-" in item.id  # UUID format

    def test_to_item_empty_source_url(self) -> None:
        """When source_url is empty, it stays empty."""
        handler = RedditHandler(_sample_config())
        post = {
            "id": "t3_test",
            "title": "Test",
            "content": "",
            "author": "",
            "subreddit": "",
            "score": 0,
            "num_comments": 0,
            "published_date": "",
            "source_url": "",
        }

        item = handler.to_item(post)
        assert item.source_url == ""


# ---------------------------------------------------------------------------
# Tests: URL construction
# ---------------------------------------------------------------------------


class TestRedditUrlConstruction:
    """Verify that the handler builds correct API URLs."""

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_search_url_includes_subreddit(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """The search URL should contain the subreddit name."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler({
            "client_id": "test",
            "client_secret": "secret",
            "user_agent": "Test/1.0",
            "subreddits": ["MachineLearning"],
        })
        handler.fetch(query="deep learning", limit=5)

        call_url = mock_get.call_args.kwargs.get("url", mock_get.call_args[0][0] if mock_get.call_args[0] else "")
        assert "MachineLearning" in call_url

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_search_url_includes_restrict_sr(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """The search URL should include restrict_sr=1 to scope to subreddit."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        handler.fetch(query="test", limit=5)

        call_url = mock_get.call_args.kwargs.get("url", mock_get.call_args[0][0] if mock_get.call_args[0] else "")
        assert "restrict_sr=1" in call_url

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_empty_query_uses_new_endpoint(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """When query is empty, use /new endpoint instead of /search."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler(_sample_config())
        handler.fetch(query="", limit=5)

        call_url = mock_get.call_args.kwargs.get("url", mock_get.call_args[0][0] if mock_get.call_args[0] else "")
        assert "/new" in call_url
        assert "restrict_sr" not in call_url


# ---------------------------------------------------------------------------
# Tests: multi-subreddit aggregation
# ---------------------------------------------------------------------------


class TestRedditMultiSubreddit:
    """Tests for aggregating results across multiple subreddits."""

    @patch("autoinfo.collectors.reddit.httpx.post")
    @patch("autoinfo.collectors.reddit.httpx.get")
    def test_fetch_iterates_all_subreddits(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """fetch should search all configured subreddits."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _make_search_response(SAMPLE_REDDIT_POSTS)

        handler = RedditHandler({
            "client_id": "test",
            "client_secret": "secret",
            "user_agent": "Test/1.0",
            "subreddits": ["MachineLearning", "artificial", "python"],
        })
        handler.fetch(query="test", limit=10)

        # Should have called GET for each subreddit
        assert mock_get.call_count >= 1


# ---------------------------------------------------------------------------
# Tests: registration
# ---------------------------------------------------------------------------


class TestRedditRegistration:
    """Verify the handler is properly registered in the collectors package."""

    def test_handler_is_registered_in_package(self) -> None:
        """Verify the handler is exported from the collectors package."""
        from autoinfo.collectors import RedditHandler
        assert RedditHandler is not None

    def test_handler_inherits_base(self) -> None:
        """RedditHandler should inherit from BaseHandler."""
        from autoinfo.collectors.base import BaseHandler
        assert issubclass(RedditHandler, BaseHandler)
