"""Collectors package — source-specific fetchers and parsers."""

from autoinfo.collectors.akshare import AKShareHandler
from autoinfo.collectors.ap_api import APAPIHandler
from autoinfo.collectors.apple_podcasts import ApplePodcastsHandler
from autoinfo.collectors.bilibili import BilibiliHandler
from autoinfo.collectors.dblp import DBLPHandler
from autoinfo.collectors.edx_sitemap import EdxSitemapHandler
from autoinfo.collectors.email_imap import EmailHandler
from autoinfo.collectors.gdelt import GDELTHandler
from autoinfo.collectors.huggingface import HuggingFaceHandler
from autoinfo.collectors.nyt import NYTHandler
from autoinfo.collectors.pdf import PDFHandler
from autoinfo.collectors.quandl import QuandlHandler
from autoinfo.collectors.reddit import RedditHandler
from autoinfo.collectors.reuters_mcp import ReutersMCPHandler
from autoinfo.collectors.sec_edgar import SecEdgarHandler
from autoinfo.collectors.semantic_scholar import SemanticScholarHandler
from autoinfo.collectors.spotify import SpotifyHandler
from autoinfo.collectors.ssrn import SSRNHandler
from autoinfo.collectors.unpaywall import UnpaywallHandler
from autoinfo.collectors.uspto import USPTOHandler
from autoinfo.collectors.webhook import WebhookHandler
from autoinfo.collectors.yahoo_finance import YahooFinanceHandler
from autoinfo.collectors.youtube import YouTubeHandler

__all__ = [
    "AKShareHandler",
    "APAPIHandler",
    "ApplePodcastsHandler",
    "BilibiliHandler",
    "DBLPHandler",
    "EdxSitemapHandler",
    "EmailHandler",
    "GDELTHandler",
    "HuggingFaceHandler",
    "NYTHandler",
    "PDFHandler",
    "QuandlHandler",
    "RedditHandler",
    "ReutersMCPHandler",
    "SpotifyHandler",
    "WebhookHandler",
    "SemanticScholarHandler",
    "SecEdgarHandler",
    "SSRNHandler",
    "UnpaywallHandler",
    "USPTOHandler",
    "YahooFinanceHandler",
    "YouTubeHandler",
]
