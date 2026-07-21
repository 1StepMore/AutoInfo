"""Email (IMAP) source handler using stdlib ``imaplib``.

Provides the :class:`EmailHandler` class which connects to an IMAP
mailbox via SSL, fetches unseen messages, and converts them into
:class:`Item <autoinfo.models.Item>` instances.
"""

from __future__ import annotations

import email
import hashlib
import logging
import re
from datetime import datetime, timezone
from email.header import decode_header
from email.message import Message
from typing import Any

from autoinfo.models import Item

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class EmailHandler:
    """Fetch unseen emails from an IMAP mailbox and return ``Item`` instances.

    Usage::

        handler = EmailHandler()
        items = handler.collect({
            "host": "imap.gmail.com",
            "port": 993,
            "username": "user@gmail.com",
            "password": "app-password",
            "mailbox": "INBOX",
        })
        for item in items:
            print(item.title, item.source_platform)
    """

    def __init__(self, source_name: str = "email") -> None:
        self.source_name = source_name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(self, config: dict[str, Any]) -> list[Item]:
        """Connect to an IMAP mailbox and return unseen messages as ``Item``.

        Parameters
        ----------
        config : dict
            Keys:

            - ``host`` (str, required) — IMAP server hostname
            - ``port`` (int, optional) — defaults to ``993``
            - ``username`` (str, required) — mailbox login
            - ``password`` (str, required) — mailbox password / app password
            - ``mailbox`` (str, optional) — defaults to ``"INBOX"``
            - ``since_date`` (str, optional) — ISO date ``YYYY-MM-DD``;
              only fetch emails on or after this date

        Returns
        -------
        list[Item]
            Parsed email items.  Returns an empty list on any error
            (connection failure, authentication failure, etc.).
        """
        host = config.get("host", "")
        port = config.get("port", 993)
        username = config.get("username", "")
        password = config.get("password", "")
        mailbox_name = config.get("mailbox", "INBOX")
        since_date = config.get("since_date", "")

        # -- Validate required fields ----------------------------------
        if not host or not username or not password:
            logger.error(
                "EmailHandler: missing required config: host=%s username=%s "
                "password=%s",
                host or "<missing>",
                username or "<missing>",
                "<set>" if password else "<missing>",
            )
            return []

        # -- Connect and fetch ------------------------------------------
        try:
            items = self._fetch_messages(
                host=host,
                port=port,
                username=username,
                password=password,
                mailbox_name=mailbox_name,
                since_date=since_date,
            )
        except Exception as exc:
            logger.warning(
                "EmailHandler: IMAP fetch failed for %s@%s:%d — %s: %s",
                username,
                host,
                port,
                type(exc).__name__,
                exc,
            )
            return []

        logger.info(
            "EmailHandler: collected %d item(s) from %s@%s/%s",
            len(items),
            username,
            host,
            mailbox_name,
        )
        return items

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_messages(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        mailbox_name: str,
        since_date: str,
    ) -> list[Item]:
        """Open an IMAP connection, search for unseen messages, parse them."""
        import imaplib

        conn = imaplib.IMAP4_SSL(host, port)
        try:
            conn.login(username, password)
        except imaplib.IMAP4.error as exc:
            logger.warning(
                "EmailHandler: login failed for %s@%s: %s",
                username,
                host,
                exc,
            )
            conn.logout()
            return []

        # Select the mailbox (read-only)
        typ, _ = conn.select(mailbox_name, readonly=True)
        if typ != "OK":
            logger.warning(
                "EmailHandler: cannot select mailbox '%s' on %s: typ=%s",
                mailbox_name,
                host,
                typ,
            )
            conn.logout()
            return []

        # Build search criteria
        search_criteria = ["UNSEEN"]
        if since_date:
            # Convert ISO date (YYYY-MM-DD) to IMAP format (DD-Mon-YYYY)
            try:
                dt = datetime.strptime(since_date, "%Y-%m-%d").date()
                imap_date = dt.strftime("%d-%b-%Y")
                search_criteria.append(f"SINCE {imap_date}")
            except ValueError:
                logger.warning(
                    "EmailHandler: invalid since_date format '%s', "
                    "expected YYYY-MM-DD; ignoring date filter",
                    since_date,
                )

        # Search for messages (imaplib accepts str criteria)
        search_str = " ".join(search_criteria)
        typ, msg_ids = conn.search(None, search_str)
        if typ != "OK" or not msg_ids[0]:
            # No unseen messages matching criteria
            conn.logout()
            return []

        uid_list = msg_ids[0].split()
        items: list[Item] = []
        for uid in uid_list:
            try:
                item = self._fetch_single_message(conn, uid, host, mailbox_name)
                if item is not None:
                    items.append(item)
            except Exception as exc:
                logger.warning(
                    "EmailHandler: skipping message UID %s on %s: %s",
                    uid.decode(errors="replace"),
                    host,
                    exc,
                )
                continue

        conn.logout()
        return items

    def _fetch_single_message(
        self,
        conn: Any,
        uid: bytes,
        host: str,
        mailbox_name: str,
    ) -> Item | None:
        """Fetch and parse a single email by UID."""
        import imaplib

        typ, msg_data = conn.fetch(uid, "(RFC822)")
        if typ != "OK" or not msg_data or msg_data[0] is None:
            return None

        raw_email = msg_data[0][1]
        if raw_email is None:
            return None

        msg: Message = email.message_from_bytes(raw_email)

        # -- Extract headers ---------------------------------------------
        subject = self._decode_header_value(msg.get("Subject", ""))
        from_addr = self._decode_header_value(msg.get("From", ""))
        date_str = msg.get("Date", "")

        # Normalise date to ISO-8601
        collected_at = self._normalise_date(date_str)

        # Extract email address from From header
        sender_email = self._extract_email(from_addr)
        source_platform = f"email:{sender_email}" if sender_email else "email:unknown"

        # -- Extract body content ----------------------------------------
        body_text, content_type = self._extract_body(msg)

        # -- Build unique ID ---------------------------------------------
        uid_str = uid.decode(errors="replace")
        item_id = self._make_item_id(host, mailbox_name, uid_str)

        return Item(
            id=item_id,
            source_name=self.source_name,
            source_type="email_imap",
            source_url=f"imap://{host}/{mailbox_name}#{uid_str}",
            title=subject or "(no subject)",
            content=body_text,
            content_type=content_type,
            collected_at=collected_at,
            raw_data={
                "from": from_addr,
                "sender_email": sender_email,
                "uid": uid_str,
                "host": host,
                "mailbox": mailbox_name,
            },
        )

    # ------------------------------------------------------------------
    # Body extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_body(msg: Message) -> tuple[str, str]:
        """Extract text content from an email message.

        Returns
        -------
        tuple[str, str]
            ``(body_text, content_type)`` where ``content_type`` is
            ``"text"`` or ``"html"``.
        """
        if msg.is_multipart():
            return EmailHandler._extract_multipart_body(msg)
        return EmailHandler._extract_singlepart_body(msg)

    @staticmethod
    def _extract_singlepart_body(msg: Message) -> tuple[str, str]:
        """Extract body from a non-multipart message."""
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload is None:
            return "", "text"

        charset = msg.get_content_charset() or "utf-8"
        try:
            text = payload.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            text = payload.decode("utf-8", errors="replace")

        if content_type == "text/plain":
            return text, "text"
        if content_type == "text/html":
            return EmailHandler._strip_html(text), "html"
        return "", "text"

    @staticmethod
    def _extract_multipart_body(msg: Message) -> tuple[str, str]:
        """Walk multipart parts; prefer text/plain, fall back to text/html."""
        text_parts: list[str] = []
        html_parts: list[str] = []

        for part in msg.walk():
            # Skip attachments (Content-Disposition: attachment)
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition.lower():
                continue

            content_type = part.get_content_type()
            payload = part.get_payload(decode=True)
            if payload is None:
                continue

            charset = part.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                decoded = payload.decode("utf-8", errors="replace")

            if content_type == "text/plain":
                text_parts.append(decoded)
            elif content_type == "text/html":
                html_parts.append(decoded)

        if text_parts:
            return "\n".join(text_parts), "text"
        if html_parts:
            return EmailHandler._strip_html("\n".join(html_parts)), "html"
        return "", "text"

    @staticmethod
    def _strip_html(html: str) -> str:
        """Remove HTML tags and decode common entities."""
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        # Decode common HTML entities
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")
        text = text.replace("&nbsp;", " ")
        return text

    # ------------------------------------------------------------------
    # Header helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_header_value(value: str | bytes | None) -> str:
        """Decode RFC 2047 encoded header values (e.g. ``=?UTF-8?B?...``)."""
        if not value:
            return ""
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")

        decoded_parts: list[str] = []
        for part, charset in decode_header(value):
            if isinstance(part, bytes):
                if charset:
                    try:
                        decoded_parts.append(part.decode(charset, errors="replace"))
                    except (LookupError, UnicodeDecodeError):
                        decoded_parts.append(part.decode("utf-8", errors="replace"))
                else:
                    decoded_parts.append(part.decode("utf-8", errors="replace"))
            else:
                decoded_parts.append(str(part))
        return " ".join(decoded_parts)

    @staticmethod
    def _extract_email(from_header: str) -> str:
        """Extract the email address from a ``From`` header value.

        Handles both ``"Name <user@example.com>"`` and bare ``user@example.com``.
        """
        match = re.search(r"<([^>]+)>", from_header)
        if match:
            return match.group(1).strip()
        # No angle brackets — check if it looks like an email
        candidate = from_header.strip()
        if "@" in candidate:
            return candidate
        return ""

    # ------------------------------------------------------------------
    # ID and date normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _make_item_id(host: str, mailbox: str, uid: str) -> str:
        """Produce a stable item ID from host + mailbox + UID."""
        raw = f"imap:{host}:{mailbox}:{uid}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @staticmethod
    def _normalise_date(date_str: str) -> str:
        """Try to parse an email date header into ISO-8601 (UTC).

        Returns an empty string if the date cannot be parsed.
        """
        if not date_str:
            return ""

        # Try email.utils.parsedate_to_datetime (stdlib, Python 3.3+)
        try:
            from email.utils import parsedate_to_datetime

            dt = parsedate_to_datetime(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass

        # Fallback: try dateutil
        try:
            from dateutil import parser as dateutil_parser

            dt = dateutil_parser.parse(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass

        # Last resort: return the raw string
        return date_str
