"""Collectors package — source-specific fetchers and parsers."""

from autoinfo.collectors.email_imap import EmailHandler

__all__ = ["EmailHandler"]

from autoinfo.collectors.pdf import PDFHandler

__all__ = [
    "PDFHandler",
]

from autoinfo.collectors.webhook import WebhookHandler

__all__ = [
    "WebhookHandler",
]
