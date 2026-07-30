"""Collectors package — source-specific fetchers and parsers."""

from autoinfo.collectors.ap_api import APAPIHandler
from autoinfo.collectors.apple_podcasts import ApplePodcastsHandler
from autoinfo.collectors.bilibili import BilibiliHandler
from autoinfo.collectors.dblp import DBLPHandler
from autoinfo.collectors.email_imap import EmailHandler
from autoinfo.collectors.nyt import NYTHandler
from autoinfo.collectors.pdf import PDFHandler
from autoinfo.collectors.reddit import RedditHandler
from autoinfo.collectors.reuters_mcp import ReutersMCPHandler
from autoinfo.collectors.spotify import SpotifyHandler
from autoinfo.collectors.webhook import WebhookHandler
from autoinfo.collectors.semantic_scholar import SemanticScholarHandler
from autoinfo.collectors.uspto import USPTOHandler
from autoinfo.collectors.youtube import YouTubeHandler

__all__ = [
    "APAPIHandler",
    "ApplePodcastsHandler",
    "BilibiliHandler",
    "DBLPHandler",
    "EmailHandler",
    "NYTHandler",
    "PDFHandler",
    "RedditHandler",
    "ReutersMCPHandler",
    "SpotifyHandler",
    "WebhookHandler",
    "SemanticScholarHandler",
    "USPTOHandler",
    "YouTubeHandler",
]
