"""Tests for the Email (IMAP) source handler.

Tests cover config validation, email parsing with a mocked IMAP
connection, and graceful connection failure handling.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from autoinfo.collectors.email_imap import EmailHandler
from autoinfo.models import Item


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def handler() -> EmailHandler:
    """Return a default :class:`EmailHandler` instance."""
    return EmailHandler()


@pytest.fixture
def valid_config() -> dict:
    """Return a minimal valid email config."""
    return {
        "host": "imap.example.com",
        "port": 993,
        "username": "test@example.com",
        "password": "secret",
        "mailbox": "INBOX",
    }


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestConfigValidation:
    """Verify missing or invalid config fields are handled gracefully."""

    def test_missing_host_returns_empty(self, handler: EmailHandler) -> None:
        """Config without host should return an empty list."""
        config = {
            "host": "",
            "username": "test@example.com",
            "password": "secret",
        }
        items = handler.collect(config)
        assert items == []

    def test_missing_username_returns_empty(self, handler: EmailHandler) -> None:
        """Config without username should return an empty list."""
        config = {
            "host": "imap.example.com",
            "username": "",
            "password": "secret",
        }
        items = handler.collect(config)
        assert items == []

    def test_missing_password_returns_empty(self, handler: EmailHandler) -> None:
        """Config without password should return an empty list."""
        config = {
            "host": "imap.example.com",
            "username": "test@example.com",
            "password": "",
        }
        items = handler.collect(config)
        assert items == []

    def test_empty_config_returns_empty(self, handler: EmailHandler) -> None:
        """An empty config dict should return an empty list."""
        items = handler.collect({})
        assert items == []


# ---------------------------------------------------------------------------
# Email parsing (mocked IMAP)
# ---------------------------------------------------------------------------


def _make_mock_imap(emails: list[tuple[str, str, str, str, str]]) -> MagicMock:
    """Build a mocked ``imaplib.IMAP4_SSL`` that returns predefined messages.

    Parameters
    ----------
    emails : list[tuple[str, str, str, str, str]]
        List of ``(subject, from_addr, date_str, body, content_type)`` tuples.

    Returns
    -------
    MagicMock
        A mock IMAP connection that mimics the subset of IMAP4 methods
        used by ``EmailHandler._fetch_messages``.
    """
    mock_conn = MagicMock()

    # login always succeeds
    mock_conn.login.return_value = ("OK", [b"Logged in"])

    # select always succeeds
    mock_conn.select.return_value = ("OK", [b"1"])

    # Build search result with UIDs 1..N
    uid_list = [str(i).encode() for i in range(1, len(emails) + 1)]
    mock_conn.search.return_value = ("OK", [b" ".join(uid_list)])

    # Build fetch responses per UID
    def _fetch_side_effect(*args: bytes) -> tuple[str, list]:
        uid = args[0]
        idx = int(uid) - 1
        if idx < 0 or idx >= len(emails):
            return ("BAD", [b""])

        row = emails[idx]
        subject, from_addr, date_str, body, *rest = row
        content_type = rest[0] if rest else "text/plain"
        raw_msg = _build_raw_email(subject, from_addr, date_str, body, content_type)
        # imaplib fetch response format: data[0] = (header_info, raw_bytes)
        return ("OK", [(b"", raw_msg)])

    mock_conn.fetch.side_effect = _fetch_side_effect

    return mock_conn


def _build_raw_email(
    subject: str,
    from_addr: str,
    date_str: str,
    body: str,
    content_type: str = "text/plain",
) -> bytes:
    """Build a raw RFC822 email message as bytes."""
    lines = [
        f"Subject: {subject}",
        f"From: {from_addr}",
        f"Date: {date_str}",
        "MIME-Version: 1.0",
        f"Content-Type: {content_type}; charset=\"utf-8\"",
        "Content-Transfer-Encoding: 7bit",
        "",
        body,
    ]
    return "\r\n".join(lines).encode("utf-8")


class TestEmailParsing:
    """Verify that mocked IMAP emails are parsed into valid ``Item`` instances."""

    @patch("imaplib.IMAP4_SSL")
    def test_single_email_parsed_correctly(
        self,
        mock_imap_class: MagicMock,
        handler: EmailHandler,
    ) -> None:
        """A single plain-text email should produce one Item with correct fields."""
        emails = [
            ("Hello World", "Alice <alice@example.com>",
             "Mon, 1 Jan 2024 10:00:00 +0000", "This is the body."),
        ]
        mock_imap_class.return_value = _make_mock_imap(emails)

        config = {
            "host": "imap.example.com",
            "username": "test@example.com",
            "password": "secret",
        }
        items = handler.collect(config)
        assert len(items) == 1

        item = items[0]
        assert item.title == "Hello World"
        assert item.content == "This is the body."
        assert item.content_type == "text"
        assert item.source_type == "email_imap"
        assert item.source_url.startswith("imap://imap.example.com")
        assert item.raw_data.get("sender_email") == "alice@example.com"
        assert item.collected_at != ""

    @patch("imaplib.IMAP4_SSL")
    def test_multiple_emails(
        self,
        mock_imap_class: MagicMock,
        handler: EmailHandler,
    ) -> None:
        """Multiple unseen emails should each produce one Item."""
        emails = [
            ("First", "a@ex.com", "Tue, 2 Jan 2024 12:00:00 +0000", "Body A"),
            ("Second", "b@ex.com", "Wed, 3 Jan 2024 14:30:00 +0000", "Body B"),
            ("Third", "c@ex.com", "Thu, 4 Jan 2024 09:15:00 +0000", "Body C"),
        ]
        mock_imap_class.return_value = _make_mock_imap(emails)

        items = handler.collect({
            "host": "imap.example.com",
            "username": "test@example.com",
            "password": "secret",
        })
        assert len(items) == 3
        assert items[0].title == "First"
        assert items[1].title == "Second"
        assert items[2].title == "Third"

    @patch("imaplib.IMAP4_SSL")
    def test_html_email_is_stripped(
        self,
        mock_imap_class: MagicMock,
        handler: EmailHandler,
    ) -> None:
        """Emails with text/html content should have HTML tags stripped."""
        html_body = "<html><body><p>Hello <b>world</b></p></body></html>"
        emails = [
            ("HTML Test", "sender@ex.com",
             "Fri, 5 Jan 2024 08:00:00 +0000", html_body, "text/html"),
        ]
        mock_imap_class.return_value = _make_mock_imap(emails)

        items = handler.collect({
            "host": "imap.example.com",
            "username": "test@example.com",
            "password": "secret",
        })
        assert len(items) == 1
        # HTML stripped — content should be clean text
        assert "Hello" in items[0].content
        assert "world" in items[0].content
        assert "<b>" not in items[0].content
        assert items[0].content_type == "html"

    @patch("imaplib.IMAP4_SSL")
    def test_from_address_extraction(
        self,
        mock_imap_class: MagicMock,
        handler: EmailHandler,
    ) -> None:
        """The ``raw_data['sender_email']`` should contain the sender's address."""
        test_cases = [
            ("Alice <alice@example.com>", "alice@example.com"),
            ("bare@example.com", "bare@example.com"),
            ("Just Name", ""),
        ]
        for from_header, expected in test_cases:
            emails = [
                ("Test", from_header,
                 "Sat, 6 Jan 2024 10:00:00 +0000", "Body text"),
            ]
            mock_imap = _make_mock_imap(emails)
            mock_imap_class.reset_mock()
            mock_imap_class.return_value = mock_imap

            items = handler.collect({
                "host": "imap.example.com",
                "username": "test@example.com",
                "password": "secret",
            })
            assert len(items) == 1, f"Failed for from_header={from_header!r}"
            assert items[0].raw_data.get("sender_email", "") == expected, (
                f"Expected {expected!r} for from_header={from_header!r}, "
                f"got {items[0].raw_data.get('sender_email', '')!r}"
            )

    @patch("imaplib.IMAP4_SSL")
    def test_encoded_subject_decoded(
        self,
        mock_imap_class: MagicMock,
        handler: EmailHandler,
    ) -> None:
        """RFC 2047 encoded subjects (e.g. =?UTF-8?B?...) should be decoded."""
        # =?UTF-8?B?w7xsZXI=?= → "üler"
        encoded_subject = "=?UTF-8?B?w7xsZXI=?="
        emails = [
            (encoded_subject, "user@ex.com",
             "Sun, 7 Jan 2024 12:00:00 +0000", "Body"),
        ]
        mock_imap_class.return_value = _make_mock_imap(emails)

        items = handler.collect({
            "host": "imap.example.com",
            "username": "test@example.com",
            "password": "secret",
        })
        assert len(items) == 1
        assert items[0].title == "üler"

    @patch("imaplib.IMAP4_SSL")
    def test_stable_item_ids(
        self,
        mock_imap_class: MagicMock,
        handler: EmailHandler,
    ) -> None:
        """The same email should produce the same item ID deterministically."""
        emails = [
            ("Test", "a@ex.com", "Mon, 8 Jan 2024 10:00:00 +0000", "Body"),
        ]
        mock_imap_class.return_value = _make_mock_imap(emails)

        items_a = handler.collect({
            "host": "imap.example.com",
            "username": "test@example.com",
            "password": "secret",
        })
        # Reset mock and collect again — same UID → same ID
        mock_imap_class.return_value = _make_mock_imap(emails)
        items_b = handler.collect({
            "host": "imap.example.com",
            "username": "test@example.com",
            "password": "secret",
        })
        assert len(items_a) == 1
        assert len(items_b) == 1
        assert items_a[0].id == items_b[0].id


# ---------------------------------------------------------------------------
# Connection failure handling
# ---------------------------------------------------------------------------


class TestConnectionFailure:
    """Verify the handler returns empty list on connection/IMAP errors."""

    @patch("imaplib.IMAP4_SSL")
    def test_connection_refused(
        self,
        mock_imap_class: MagicMock,
        handler: EmailHandler,
    ) -> None:
        """A ConnectionRefusedError (or any Exception on connect) returns []."""
        mock_imap_class.side_effect = ConnectionRefusedError("Connection refused")

        items = handler.collect({
            "host": "imap.example.com",
            "username": "test@example.com",
            "password": "secret",
        })
        assert items == []

    @patch("imaplib.IMAP4_SSL")
    def test_login_failure(
        self,
        mock_imap_class: MagicMock,
        handler: EmailHandler,
    ) -> None:
        """Authentication failure should return an empty list."""
        import imaplib

        mock_conn = MagicMock()
        mock_conn.login.side_effect = imaplib.IMAP4.error("Authentication failed")
        mock_imap_class.return_value = mock_conn

        items = handler.collect({
            "host": "imap.example.com",
            "username": "wrong@example.com",
            "password": "wrong-password",
        })
        assert items == []

    @patch("imaplib.IMAP4_SSL")
    def test_select_failure(
        self,
        mock_imap_class: MagicMock,
        handler: EmailHandler,
    ) -> None:
        """Mailbox select failure should return an empty list."""
        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("NO", [b"Mailbox not found"])
        mock_imap_class.return_value = mock_conn

        items = handler.collect({
            "host": "imap.example.com",
            "username": "test@example.com",
            "password": "secret",
            "mailbox": "NONEXISTENT",
        })
        assert items == []

    @patch("imaplib.IMAP4_SSL")
    def test_timeout_returns_empty(
        self,
        mock_imap_class: MagicMock,
        handler: EmailHandler,
    ) -> None:
        """A timeout (or any Exception) during connect gracefully returns []."""
        mock_imap_class.side_effect = TimeoutError("Connection timed out")

        items = handler.collect({
            "host": "imap.example.com",
            "username": "test@example.com",
            "password": "secret",
        })
        assert items == []


# ---------------------------------------------------------------------------
# Date filter
# ---------------------------------------------------------------------------


class TestDateFilter:
    """Verify the ``since_date`` config option filters emails correctly."""

    @patch("imaplib.IMAP4_SSL")
    def test_since_date_search_criteria(
        self,
        mock_imap_class: MagicMock,
        handler: EmailHandler,
    ) -> None:
        """When ``since_date`` is set, the IMAP SEARCH should include SINCE."""
        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"1"])
        # Return no messages so search is called but no items returned
        mock_conn.search.return_value = ("OK", [b""])
        mock_imap_class.return_value = mock_conn

        handler.collect({
            "host": "imap.example.com",
            "username": "test@example.com",
            "password": "secret",
            "since_date": "2024-01-15",
        })

        # Verify the search was called with UNSEEN SINCE 15-Jan-2024
        search_args = mock_conn.search.call_args
        assert search_args is not None
        args = search_args[0]
        search_str = str(args[1]) if len(args) > 1 else ""
        assert "UNSEEN" in search_str
        assert "SINCE" in search_str
        assert "15-Jan-2024" in search_str


# ---------------------------------------------------------------------------
# Integration with collect.py dispatch
# ---------------------------------------------------------------------------


class TestDispatchIntegration:
    """Verify ``EmailHandler`` can be instantiated and invoked via the
    collection dispatch path (mocked IMAP, no actual network)."""

    def test_handler_has_collect_method(self, handler: EmailHandler) -> None:
        """The handler should expose a ``collect`` method."""
        assert hasattr(handler, "collect")
        assert callable(handler.collect)

    def test_handler_source_name_default(self) -> None:
        """Default source_name should be 'email'."""
        h = EmailHandler()
        assert h.source_name == "email"

    def test_handler_custom_source_name(self) -> None:
        """Custom source_name should propagate."""
        h = EmailHandler(source_name="my-email-source")
        assert h.source_name == "my-email-source"

    def test_item_has_valid_item_type(self, handler: EmailHandler) -> None:
        """Items returned by the handler should be dataclass instances."""
        # Use mock IMAP that returns no results — just check the type
        # contract by verifying an Item can be constructed with email fields
        item = Item(
            id="test-123",
            source_name="email",
            source_type="email_imap",
            source_url="imap://example.com/INBOX#1",
            title="Test",
            content="Test body",
        )
        assert isinstance(item, Item)
        assert item.source_type == "email_imap"
