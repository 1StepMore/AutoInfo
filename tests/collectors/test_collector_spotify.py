"""Tests for the Spotify Web API handler.

Uses ``unittest.mock.patch`` to mock HTTP responses for both OAuth2
token flow and Spotify API calls — no real API calls.
"""

from __future__ import annotations

import os
import time
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from autoinfo.collectors.spotify import SpotifyHandler
from autoinfo.models import Item


# ---------------------------------------------------------------------------
# Sample Spotify API response data
# ---------------------------------------------------------------------------

SAMPLE_TOKEN_RESPONSE: dict[str, Any] = {
    "access_token": "mock-spotify-access-token-xyz",
    "token_type": "Bearer",
    "expires_in": 3600,
}

SAMPLE_SHOW_EPISODES_RESPONSE: dict[str, Any] = {
    "href": "https://api.spotify.com/v1/shows/5CfCWKI5pZ28U0uOzXkDHe/episodes?offset=0&limit=10",
    "items": [
        {
            "audio_preview_url": "https://p.scdn.co/mp3-preview/abc123",
            "description": "In this episode we explore the fundamentals of deep learning, from perceptrons to transformers.",
            "duration_ms": 3600000,
            "explicit": False,
            "external_urls": {
                "spotify": "https://open.spotify.com/episode/ep001"
            },
            "href": "https://api.spotify.com/v1/episodes/ep001",
            "id": "ep001",
            "images": [
                {"height": 640, "url": "https://i.scdn.co/image/abc123", "width": 640}
            ],
            "is_externally_hosted": False,
            "is_playable": True,
            "language": "en",
            "languages": ["en"],
            "name": "Deep Learning Fundamentals",
            "release_date": "2026-03-15",
            "release_date_precision": "day",
            "type": "episode",
            "uri": "spotify:episode:ep001",
            "show": {
                "id": "5CfCWKI5pZ28U0uOzXkDHe",
                "name": "AI Frontiers",
                "description": "A podcast about artificial intelligence research and applications.",
                "publisher": "TechMedia Inc.",
                "external_urls": {
                    "spotify": "https://open.spotify.com/show/5CfCWKI5pZ28U0uOzXkDHe"
                },
                "total_episodes": 52,
            },
        },
        {
            "audio_preview_url": "",
            "description": "A discussion with leading researchers about transformer architectures and attention mechanisms.",
            "duration_ms": 2700000,
            "explicit": False,
            "external_urls": {
                "spotify": "https://open.spotify.com/episode/ep002"
            },
            "href": "https://api.spotify.com/v1/episodes/ep002",
            "id": "ep002",
            "images": [],
            "is_externally_hosted": False,
            "is_playable": True,
            "language": "en",
            "languages": ["en", "es"],
            "name": "Understanding Transformers",
            "release_date": "2026-03-08",
            "release_date_precision": "day",
            "type": "episode",
            "uri": "spotify:episode:ep002",
            "show": {
                "id": "5CfCWKI5pZ28U0uOzXkDHe",
                "name": "AI Frontiers",
                "description": "A podcast about artificial intelligence research.",
                "publisher": "TechMedia Inc.",
                "total_episodes": 52,
            },
        },
    ],
    "limit": 10,
    "next": None,
    "offset": 0,
    "previous": None,
    "total": 2,
}

SAMPLE_SEARCH_RESPONSE: dict[str, Any] = {
    "episodes": {
        "href": "https://api.spotify.com/v1/search?query=machine+learning&type=episode&offset=0&limit=10",
        "items": [
            {
                "audio_preview_url": "https://p.scdn.co/mp3-preview/search001",
                "description": "We discuss the latest breakthroughs in machine learning research.",
                "duration_ms": 2400000,
                "explicit": False,
                "external_urls": {
                    "spotify": "https://open.spotify.com/episode/search001"
                },
                "href": "https://api.spotify.com/v1/episodes/search001",
                "id": "search001",
                "languages": ["en"],
                "name": "ML Research Weekly",
                "release_date": "2026-07-20",
                "release_date_precision": "day",
                "type": "episode",
                "uri": "spotify:episode:search001",
                "show": {
                    "id": "show_ml",
                    "name": "Machine Learning Today",
                    "description": "Weekly ML news and research.",
                    "publisher": "DataPod Network",
                },
            },
        ],
        "limit": 10,
        "next": None,
        "offset": 0,
        "total": 1,
    },
}

SAMPLE_EMPTY_RESPONSE: dict[str, Any] = {
    "href": "https://api.spotify.com/v1/shows/show123/episodes",
    "items": [],
    "limit": 10,
    "offset": 0,
    "total": 0,
}

SAMPLE_MINIMAL_EPISODE: dict[str, Any] = {
    "audio_preview_url": None,
    "description": "",
    "duration_ms": 0,
    "explicit": False,
    "external_urls": {},
    "id": "min001",
    "languages": [],
    "name": "Minimal Episode",
    "release_date": "",
    "type": "episode",
    "show": {
        "id": "show_min",
        "name": "Minimal Show",
        "publisher": "",
    },
}

SAMPLE_MULTI_PAGE_SEARCH_RESPONSE_PAGE1: dict[str, Any] = {
    "episodes": {
        "items": [
            {
                "id": "page1_ep1",
                "name": "Page 1 Episode",
                "description": "First page result.",
                "duration_ms": 1800000,
                "explicit": False,
                "external_urls": {"spotify": "https://open.spotify.com/episode/page1_ep1"},
                "languages": ["en"],
                "release_date": "2026-06-01",
                "type": "episode",
                "show": {"id": "show_paged", "name": "Paged Show", "publisher": "Test"},
            },
        ],
        "limit": 1,
        "offset": 0,
        "total": 2,
    },
}

SAMPLE_MULTI_PAGE_SEARCH_RESPONSE_PAGE2: dict[str, Any] = {
    "episodes": {
        "items": [
            {
                "id": "page2_ep1",
                "name": "Page 2 Episode",
                "description": "Second page result.",
                "duration_ms": 2100000,
                "explicit": False,
                "external_urls": {"spotify": "https://open.spotify.com/episode/page2_ep1"},
                "languages": ["en"],
                "release_date": "2026-07-01",
                "type": "episode",
                "show": {"id": "show_paged", "name": "Paged Show", "publisher": "Test"},
            },
        ],
        "limit": 1,
        "offset": 1,
        "total": 2,
    },
}


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _mock_response(data: dict[str, Any], status: int = 200) -> MagicMock:
    """Create a mock httpx.Response that returns the given JSON data."""
    mock = MagicMock(spec=httpx.Response)
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    mock.status_code = status
    return mock


def _make_token_response() -> MagicMock:
    """Create a mock httpx.Response for a successful OAuth2 token request."""
    return _mock_response(SAMPLE_TOKEN_RESPONSE)


def _make_401_response() -> MagicMock:
    """Create a mock httpx.Response simulating a 401 Unauthorized."""
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = 401
    mock.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Unauthorized",
        request=MagicMock(),
        response=MagicMock(status_code=401),
    )
    return mock


def _sample_config() -> dict[str, Any]:
    """Return a minimal valid config dict for a SpotifyHandler."""
    return {
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "show_id": "5CfCWKI5pZ28U0uOzXkDHe",
    }


# ---------------------------------------------------------------------------
# Tests: handler existence and construction
# ---------------------------------------------------------------------------


class TestSpotifyHandlerExists:
    """Verify the handler class is importable and constructable."""

    def test_handler_is_importable(self) -> None:
        """SpotifyHandler should be accessible from the spotify module."""
        assert SpotifyHandler is not None

    def test_creates_with_default_config(self) -> None:
        """Handler instantiates with empty config dict."""
        handler = SpotifyHandler({})
        assert handler.source_type == "spotify"
        assert handler.config == {}
        assert handler.show_id == ""
        assert handler.client_id == ""
        assert handler.client_secret == ""
        assert handler.market == "US"

    def test_creates_with_full_config(self) -> None:
        """Handler picks up all config fields."""
        config = {
            "client_id": "my-id",
            "client_secret": "my-secret",
            "show_id": "showABC",
            "market": "JP",
        }
        handler = SpotifyHandler(config)
        assert handler.client_id == "my-id"
        assert handler.client_secret == "my-secret"
        assert handler.show_id == "showABC"
        assert handler.market == "JP"

    def test_creates_with_none_config(self) -> None:
        """Passing None as config should work like empty dict."""
        handler = SpotifyHandler(None)
        assert handler.config == {}
        assert handler.show_id == ""

    def test_source_type_is_spotify(self) -> None:
        """The source_type class attribute must be 'spotify'."""
        assert SpotifyHandler.source_type == "spotify"

    def test_subclass_of_base_handler(self) -> None:
        """SpotifyHandler should be a subclass of BaseHandler."""
        from autoinfo.collectors.base import BaseHandler
        assert issubclass(SpotifyHandler, BaseHandler)

    def test_api_credentials_from_env_var(self) -> None:
        """When config has no client_id/secret, fall back to env vars."""
        with patch.dict(os.environ, {
            "AUTOINFO_SPOTIFY_CLIENT_ID": "env-id",
            "AUTOINFO_SPOTIFY_CLIENT_SECRET": "env-secret",
        }, clear=False):
            handler = SpotifyHandler({})
            assert handler.client_id == "env-id"
            assert handler.client_secret == "env-secret"

    def test_config_credentials_take_precedence_over_env(self) -> None:
        """Config dict credentials should take precedence over env vars."""
        with patch.dict(os.environ, {
            "AUTOINFO_SPOTIFY_CLIENT_ID": "env-id",
            "AUTOINFO_SPOTIFY_CLIENT_SECRET": "env-secret",
        }, clear=False):
            handler = SpotifyHandler({
                "client_id": "config-id",
                "client_secret": "config-secret",
            })
            assert handler.client_id == "config-id"
            assert handler.client_secret == "config-secret"


# ---------------------------------------------------------------------------
# Tests: fetch show episodes
# ---------------------------------------------------------------------------


class TestSpotifyFetchShowEpisodes:
    """Tests for fetching show episodes."""

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_fetch_returns_list(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """fetch() should return a list of dicts for show episodes."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert isinstance(episodes, list)
        assert len(episodes) == 2

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_fetch_each_item_is_dict(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Each returned item must be a dict."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        for ep in episodes:
            assert isinstance(ep, dict)

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_fetch_respects_limit(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """fetch should respect the limit argument."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=1)

        assert len(episodes) == 1

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_fetch_limit_zero_returns_empty(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """A limit of 0 should return an empty list."""
        mock_post.return_value = _make_token_response()

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=0)

        assert episodes == []

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_fetch_uses_show_episodes_endpoint(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Without a query, fetch should hit the show episodes endpoint."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        handler.fetch(limit=10)

        call_url = mock_get.call_args.kwargs.get("url", mock_get.call_args[0][0] if mock_get.call_args[0] else "")
        assert "shows/5CfCWKI5pZ28U0uOzXkDHe/episodes" in call_url

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_fetch_uses_show_id_argument(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """fetch show_id argument should override configured show_id."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler({"client_id": "test", "client_secret": "secret"})
        handler.fetch(limit=10, show_id="customShowID")

        call_url = mock_get.call_args.kwargs.get("url", mock_get.call_args[0][0] if mock_get.call_args[0] else "")
        assert "shows/customShowID/episodes" in call_url


# ---------------------------------------------------------------------------
# Tests: fetch search
# ---------------------------------------------------------------------------


class TestSpotifyFetchSearch:
    """Tests for search mode."""

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_fetch_search_returns_list(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """fetch with query should return search results."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_RESPONSE)

        handler = SpotifyHandler({
            "client_id": "test",
            "client_secret": "secret",
        })
        episodes = handler.fetch(limit=10, query="machine learning")

        assert isinstance(episodes, list)
        assert len(episodes) == 1

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_fetch_search_uses_search_endpoint(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """With a query, fetch should hit the search endpoint."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_RESPONSE)

        handler = SpotifyHandler({
            "client_id": "test",
            "client_secret": "secret",
        })
        handler.fetch(limit=10, query="machine learning")

        call_url = mock_get.call_args.kwargs.get("url", mock_get.call_args[0][0] if mock_get.call_args[0] else "")
        assert "search" in call_url
        assert "machine+learning" in call_url
        assert "type=show%2Cepisode" in call_url

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_fetch_search_pagination(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Search with multiple pages should aggregate results."""
        mock_post.return_value = _make_token_response()
        mock_get.side_effect = [
            _mock_response(SAMPLE_MULTI_PAGE_SEARCH_RESPONSE_PAGE1),
            _mock_response(SAMPLE_MULTI_PAGE_SEARCH_RESPONSE_PAGE2),
        ]

        handler = SpotifyHandler({
            "client_id": "test",
            "client_secret": "secret",
        })
        episodes = handler.fetch(limit=10, query="podcast")

        assert len(episodes) == 2
        assert episodes[0]["id"] == "page1_ep1"
        assert episodes[1]["id"] == "page2_ep1"
        assert mock_get.call_count == 2


# ---------------------------------------------------------------------------
# Tests: empty / no credentials responses
# ---------------------------------------------------------------------------


class TestSpotifyFetchEmpty:
    """Tests for empty or no-result responses."""

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_fetch_handles_empty_results(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """An empty items list should return an empty list."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_EMPTY_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert episodes == []

    def test_fetch_no_query_and_no_show_id_returns_empty(self) -> None:
        """Without query or show_id, fetch should return empty."""
        handler = SpotifyHandler({
            "client_id": "test",
            "client_secret": "secret",
        })
        episodes = handler.fetch(limit=10)
        assert episodes == []

    @patch("autoinfo.collectors.spotify.httpx.post")
    def test_fetch_auth_failure_returns_empty(self, mock_post: MagicMock) -> None:
        """When OAuth fails, fetch should return empty list."""
        mock_post.side_effect = httpx.HTTPStatusError(
            "Unauthorized",
            request=MagicMock(),
            response=MagicMock(status_code=401),
        )

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert episodes == []

    def test_fetch_missing_credentials_returns_empty(self) -> None:
        """Missing client_id/client_secret should fail gracefully."""
        handler = SpotifyHandler({
            "client_id": "",
            "client_secret": "",
            "show_id": "show123",
        })
        episodes = handler.fetch(limit=10)
        assert episodes == []


# ---------------------------------------------------------------------------
# Tests: field mapping
# ---------------------------------------------------------------------------


class TestSpotifyFieldMapping:
    """Tests for mapping Spotify JSON fields to AutoInfo item format."""

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_field_mapping_id(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """id should come from the episode's 'id' field."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert episodes[0]["id"] == "ep001"

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_field_mapping_title(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """title should come from 'name' field."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert episodes[0]["title"] == "Deep Learning Fundamentals"

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_field_mapping_content(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """content should come from 'description' field."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert "deep learning" in episodes[0]["content"].lower()

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_field_mapping_author(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """author should come from 'publisher' field (episode or show fallback)."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert episodes[0]["author"] == "TechMedia Inc."

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_field_mapping_published_date(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """published_date should come from 'release_date' field."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert episodes[0]["published_date"] == "2026-03-15"

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_field_mapping_duration_ms(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """duration_ms should come from 'duration_ms' field."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert episodes[0]["duration_ms"] == 3600000

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_field_mapping_language(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """language should come from first item in 'languages' list."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert episodes[0]["language"] == "en"
        assert episodes[1]["language"] == "en"  # first of ["en", "es"]

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_field_mapping_source_url(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """source_url should come from external_urls.spotify."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert "open.spotify.com/episode/ep001" in episodes[0]["source_url"]

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_field_mapping_show_id(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """show_id should come from nested show.id."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert episodes[0]["show_id"] == "5CfCWKI5pZ28U0uOzXkDHe"

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_field_mapping_show_name(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """show_name should come from nested show.name."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert episodes[0]["show_name"] == "AI Frontiers"

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_field_mapping_audio_url(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """audio_url should come from audio_preview_url."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert episodes[0]["audio_url"] == "https://p.scdn.co/mp3-preview/abc123"
        assert episodes[1]["audio_url"] == ""  # empty audio_preview_url

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_field_mapping_all_expected_fields_present(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Every returned item must have all expected keys."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        expected_fields = {
            "id", "title", "content", "author", "published_date",
            "duration_ms", "language", "source_url", "audio_url",
            "show_id", "show_name", "show_description",
            "explicit", "episode_type",
        }
        for ep in episodes:
            for field in expected_fields:
                assert field in ep, f"Item missing field: {field}"

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_minimal_episode_handles_missing_fields(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """An episode with None/empty fields should not crash."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response({
            "items": [SAMPLE_MINIMAL_EPISODE],
            "total": 1,
        })

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert len(episodes) == 1
        ep = episodes[0]
        assert ep["id"] == "min001"
        assert ep["title"] == "Minimal Episode"
        assert ep["content"] == ""
        assert ep["author"] == ""
        assert ep["duration_ms"] == 0
        assert ep["language"] == ""
        assert ep["source_url"] == ""
        assert ep["audio_url"] == ""


# ---------------------------------------------------------------------------
# Tests: OAuth2 authentication
# ---------------------------------------------------------------------------


class TestSpotifyAuth:
    """Tests for OAuth2 authentication flow."""

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_authenticate_obtains_token(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """First call should POST to token endpoint and cache the token."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        handler.fetch(limit=10)

        assert mock_post.called

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_authenticate_caches_token(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Subsequent calls should reuse the cached token."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        handler.fetch(limit=10)
        first_post_count = mock_post.call_count

        handler.fetch(limit=10)
        assert mock_post.call_count == first_post_count

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_search_uses_bearer_token(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Search requests should include Authorization: Bearer header."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SEARCH_RESPONSE)

        handler = SpotifyHandler({
            "client_id": "test",
            "client_secret": "secret",
        })
        handler.fetch(limit=10, query="test")

        headers = mock_get.call_args.kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer mock-spotify-access-token-xyz"

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_token_refresh_on_401(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """When API returns 401, token should be refreshed and request retried."""
        mock_post.return_value = _make_token_response()
        # First call returns 401, second succeeds
        mock_get.side_effect = [
            _make_401_response(),
            _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE),
        ]

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert len(episodes) == 2
        assert mock_get.call_count == 2  # 401 + retried request
        assert mock_post.call_count == 2  # initial auth + refresh


# ---------------------------------------------------------------------------
# Tests: error handling (graceful degradation)
# ---------------------------------------------------------------------------


class TestSpotifyErrorHandling:
    """Tests for HTTP errors, network failures."""

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_fetch_http_error_returns_empty(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """HTTP 500 errors should return empty list."""
        mock_post.return_value = _make_token_response()
        mock_get.side_effect = httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert episodes == []

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_fetch_network_error_returns_empty(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Network errors should return empty list."""
        mock_post.return_value = _make_token_response()
        mock_get.side_effect = httpx.NetworkError("Connection refused")

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert episodes == []

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_fetch_timeout_returns_empty(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Timeout errors should return empty list gracefully."""
        mock_post.return_value = _make_token_response()
        mock_get.side_effect = httpx.TimeoutException(
            "Request timed out",
            request=MagicMock(),
        )

        handler = SpotifyHandler(_sample_config())
        episodes = handler.fetch(limit=10)

        assert episodes == []

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_fetch_retries_on_timeout(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """After 3 TimeoutExceptions the error should be handled gracefully."""
        mock_post.return_value = _make_token_response()
        mock_get.side_effect = httpx.TimeoutException(
            "Timeout", request=MagicMock(),
        )

        handler = SpotifyHandler(_sample_config())
        start = time.time()
        episodes = handler.fetch(limit=1)
        elapsed = time.time() - start

        assert episodes == []
        assert mock_get.call_count == 3  # retries exhausted


# ---------------------------------------------------------------------------
# Tests: rate limiting
# ---------------------------------------------------------------------------


class TestSpotifyRateLimit:
    """Tests for rate limiter behaviour."""

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_rate_limit_first_call_instant(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """First call should not block."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())

        t0 = time.time()
        handler.fetch(limit=1)
        elapsed = time.time() - t0

        assert elapsed < 0.3

    @patch("autoinfo.collectors.spotify.httpx.post")
    @patch("autoinfo.collectors.spotify.httpx.get")
    def test_rate_limit_enforces_min_interval(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Back-to-back calls should be spaced by at least ~0.34 s."""
        mock_post.return_value = _make_token_response()
        mock_get.return_value = _mock_response(SAMPLE_SHOW_EPISODES_RESPONSE)

        handler = SpotifyHandler(_sample_config())
        handler.fetch(limit=1)  # warm

        t0 = time.time()
        handler.fetch(limit=1)  # should wait
        elapsed = time.time() - t0

        assert elapsed >= 0.30


# ---------------------------------------------------------------------------
# Tests: to_item conversion
# ---------------------------------------------------------------------------


class TestSpotifyToItem:
    """Tests for ``SpotifyHandler.to_item()``."""

    def test_to_item_complete(self) -> None:
        """A fully populated episode dict converts to a correct Item."""
        handler = SpotifyHandler({"client_id": "dummy", "client_secret": "dummy"})
        episode = {
            "id": "ep001",
            "title": "Deep Learning Fundamentals",
            "content": "Exploring the fundamentals of deep learning.",
            "author": "TechMedia Inc.",
            "published_date": "2026-03-15",
            "duration_ms": 3600000,
            "language": "en",
            "source_url": "https://open.spotify.com/episode/ep001",
            "audio_url": "https://p.scdn.co/mp3-preview/abc123",
            "show_id": "show_ai",
            "show_name": "AI Frontiers",
            "show_description": "A podcast about AI.",
            "explicit": False,
            "episode_type": "episode",
        }

        item = handler.to_item(episode)

        assert isinstance(item, Item)
        assert item.id == "ep001"
        assert item.source_name == "spotify"
        assert item.source_type == "spotify"
        assert item.source_platform == "spotify"
        assert item.source_url == "https://open.spotify.com/episode/ep001"
        assert item.title == "Deep Learning Fundamentals"
        assert "deep learning" in item.content.lower()
        assert item.content_type == "text"
        assert item.collected_at == "2026-03-15"
        assert item.language == "en"
        assert item.raw_data["spotify_id"] == "ep001"
        assert item.raw_data["author"] == "TechMedia Inc."
        assert item.raw_data["duration_ms"] == 3600000
        assert item.raw_data["language"] == "en"
        assert item.raw_data["audio_url"] == "https://p.scdn.co/mp3-preview/abc123"
        assert item.raw_data["show_id"] == "show_ai"
        assert item.raw_data["show_name"] == "AI Frontiers"
        assert item.raw_data["show_description"] == "A podcast about AI."
        assert item.raw_data["explicit"] is False
        assert item.raw_data["episode_type"] == "episode"

    def test_to_item_empty_id_uses_uuid(self) -> None:
        """When episode id is empty, a UUID should be generated."""
        handler = SpotifyHandler({"client_id": "dummy", "client_secret": "dummy"})
        episode = {
            "id": "",
            "title": "No ID Episode",
            "content": "",
            "author": "",
            "published_date": "",
            "duration_ms": 0,
            "language": "",
            "source_url": "",
            "audio_url": "",
            "show_id": "",
            "show_name": "",
            "show_description": "",
            "explicit": False,
            "episode_type": "episode",
        }

        item = handler.to_item(episode)

        assert item.id
        assert item.id != ""
        assert "-" in item.id

    def test_to_item_empty_source_url_stays_empty(self) -> None:
        """When source_url is empty, it stays empty."""
        handler = SpotifyHandler({"client_id": "dummy", "client_secret": "dummy"})
        episode = {
            "id": "ep_test",
            "title": "Test",
            "content": "",
            "author": "",
            "published_date": "",
            "duration_ms": 0,
            "language": "",
            "source_url": "",
            "audio_url": "",
            "show_id": "",
            "show_name": "",
            "show_description": "",
            "explicit": False,
            "episode_type": "episode",
        }

        item = handler.to_item(episode)
        assert item.source_url == ""


# ---------------------------------------------------------------------------
# Tests: registration
# ---------------------------------------------------------------------------


class TestSpotifyRegistration:
    """Verify the handler is properly registered in the collectors package."""

    def test_handler_is_registered_in_package(self) -> None:
        """Verify the handler is exported from the collectors package."""
        from autoinfo.collectors import SpotifyHandler
        assert SpotifyHandler is not None

    def test_handler_inherits_base(self) -> None:
        """SpotifyHandler should inherit from BaseHandler."""
        from autoinfo.collectors.base import BaseHandler
        assert issubclass(SpotifyHandler, BaseHandler)
